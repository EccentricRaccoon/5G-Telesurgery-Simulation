"""
Live comparison graphs for 5G vs 4G network metrics.

Runs matplotlib in a separate process (multiprocessing) to avoid
blocking the Pygame main loop or triggering GIL conflicts.

Usage from main.py:
    from live_graphs import LiveGraphWindow
    graph = LiveGraphWindow()
    graph.start()
    ...
    graph.push_data(metrics_5g, metrics_4g)
    ...
    graph.stop()
"""

import multiprocessing
import time

MAX_POINTS = 120


def _graph_process(data_queue, stop_event):
    """
    Entry point for the child process.
    Reads from data_queue and updates matplotlib plots.
    """
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from collections import deque

    # ── Rolling data buffers ──
    timestamps = deque(maxlen=MAX_POINTS)
    bler_5g = deque(maxlen=MAX_POINTS)
    bler_4g = deque(maxlen=MAX_POINTS)
    tput_5g = deque(maxlen=MAX_POINTS)
    tput_4g = deque(maxlen=MAX_POINTS)
    lat_5g = deque(maxlen=MAX_POINTS)
    lat_4g = deque(maxlen=MAX_POINTS)
    jit_5g = deque(maxlen=MAX_POINTS)
    jit_4g = deque(maxlen=MAX_POINTS)

    t0 = time.time()

    # ── Dark-themed figure ──
    plt.rcParams.update({
        'figure.facecolor': '#111111',
        'axes.facecolor': '#111111',
        'axes.edgecolor': '#444444',
        'axes.labelcolor': '#CCCCCC',
        'text.color': '#EEEEEE',
        'xtick.color': '#AAAAAA',
        'ytick.color': '#AAAAAA',
        'grid.color': '#333333',
        'grid.alpha': 0.6,
        'legend.facecolor': '#222222',
        'legend.edgecolor': '#444444',
        'font.family': 'monospace',
        'font.size': 9,
    })

    fig, axes = plt.subplots(2, 2, figsize=(10, 6))
    fig.canvas.manager.set_window_title('5G vs 4G — Live Comparison')
    fig.suptitle('5G vs 4G Live Network Comparison', fontsize=13,
                 fontweight='bold', color='#FFFFFF')
    fig.subplots_adjust(hspace=0.38, wspace=0.30, top=0.90, bottom=0.08,
                        left=0.08, right=0.96)

    ax_bler, ax_tput = axes[0]
    ax_lat, ax_jit = axes[1]

    COLOR_5G = '#00E5FF'
    COLOR_4G = '#FF8C00'

    def _setup_ax(ax, title, ylabel):
        ax.set_title(title, fontsize=10, fontweight='bold', pad=6)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_xlabel('Time (s)', fontsize=8)
        ax.grid(True, linewidth=0.5)

    _setup_ax(ax_bler, 'BLER', 'Block Error Rate')
    _setup_ax(ax_tput, 'Throughput', 'Mbps')
    _setup_ax(ax_lat, 'Latency', 'ms')
    _setup_ax(ax_jit, 'Jitter', 'ms')

    ax_bler.set_yscale('log')
    ax_bler.set_ylim(1e-6, 1.0)

    ln_bler5, = ax_bler.plot([], [], color=COLOR_5G, linewidth=1.4, label='5G NR')
    ln_bler4, = ax_bler.plot([], [], color=COLOR_4G, linewidth=1.4, label='4G LTE')
    ax_bler.legend(loc='upper right', fontsize=7)

    ln_tput5, = ax_tput.plot([], [], color=COLOR_5G, linewidth=1.4, label='5G NR')
    ln_tput4, = ax_tput.plot([], [], color=COLOR_4G, linewidth=1.4, label='4G LTE')
    ax_tput.legend(loc='lower right', fontsize=7)

    ln_lat5, = ax_lat.plot([], [], color=COLOR_5G, linewidth=1.4, label='5G NR')
    ln_lat4, = ax_lat.plot([], [], color=COLOR_4G, linewidth=1.4, label='4G LTE')
    threshold_line = ax_lat.axhline(y=10.0, color='#FF3333',
                                     linestyle='--', alpha=0.7, label='10ms limit')
    ax_lat.legend(loc='upper right', fontsize=7)

    ln_jit5, = ax_jit.plot([], [], color=COLOR_5G, linewidth=1.4, label='5G NR')
    ln_jit4, = ax_jit.plot([], [], color=COLOR_4G, linewidth=1.4, label='4G LTE')
    ax_jit.legend(loc='upper right', fontsize=7)

    def _drain_queue():
        """Drain all pending items from the queue."""
        while not data_queue.empty():
            try:
                item = data_queue.get_nowait()
                if item is None:
                    return False
                m5g, m4g = item
                t = time.time() - t0
                timestamps.append(t)
                bler_5g.append(max(m5g.get('bler', 1e-6), 1e-7))
                bler_4g.append(max(m4g.get('bler', 1e-6), 1e-7))
                tput_5g.append(m5g.get('throughput', 0))
                tput_4g.append(m4g.get('throughput', 0))
                lat_5g.append(m5g.get('latency', 0))
                lat_4g.append(m4g.get('latency', 0))
                jit_5g.append(m5g.get('jitter', 0))
                jit_4g.append(m4g.get('jitter', 0))
            except Exception:
                break
        return True

    def _update(frame):
        if stop_event.is_set():
            plt.close(fig)
            return

        alive = _drain_queue()
        if not alive:
            plt.close(fig)
            return

        if len(timestamps) < 1:
            return

        ts = list(timestamps)

        ln_bler5.set_data(ts, list(bler_5g))
        ln_bler4.set_data(ts, list(bler_4g))

        ln_tput5.set_data(ts, list(tput_5g))
        ln_tput4.set_data(ts, list(tput_4g))

        ln_lat5.set_data(ts, list(lat_5g))
        ln_lat4.set_data(ts, list(lat_4g))

        ln_jit5.set_data(ts, list(jit_5g))
        ln_jit4.set_data(ts, list(jit_4g))

        for ax in [ax_bler, ax_tput, ax_lat, ax_jit]:
            ax.set_xlim(max(0, ts[-1] - 60), ts[-1] + 2)
            ax.relim()

        ax_tput.autoscale_view(scalex=False)
        ax_lat.autoscale_view(scalex=False)
        ax_jit.autoscale_view(scalex=False)

    ani = animation.FuncAnimation(fig, _update, interval=500, cache_frame_data=False)

    try:
        plt.show()
    except Exception:
        pass


class LiveGraphWindow:
    """
    Controller for the live graph process.

    Call start() to spawn the window, push_data() every ~0.5s,
    and stop() on cleanup.
    """

    def __init__(self):
        self._process = None
        self._queue = None
        self._stop_event = None

    @property
    def is_running(self):
        return self._process is not None and self._process.is_alive()

    def start(self):
        """Spawn the graph window in a child process."""
        if self.is_running:
            return
        self._queue = multiprocessing.Queue(maxsize=300)
        self._stop_event = multiprocessing.Event()
        self._process = multiprocessing.Process(
            target=_graph_process,
            args=(self._queue, self._stop_event),
            daemon=True
        )
        self._process.start()

    def push_data(self, metrics_5g, metrics_4g):
        """
        Push a data point to the graph.

        Args:
            metrics_5g: dict with keys 'bler', 'throughput', 'latency', 'jitter'
            metrics_4g: dict with keys 'bler', 'throughput', 'latency', 'jitter'
        """
        if not self.is_running:
            return
        try:
            self._queue.put_nowait((metrics_5g, metrics_4g))
        except Exception:
            pass

    def stop(self):
        """Signal the graph process to exit and clean up."""
        if self._stop_event:
            self._stop_event.set()
        if self._queue:
            try:
                self._queue.put_nowait(None)
            except Exception:
                pass
        if self._process and self._process.is_alive():
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
        self._process = None
        self._queue = None
        self._stop_event = None

    def toggle(self):
        """Toggle the graph window on/off."""
        if self.is_running:
            self.stop()
        else:
            self.start()
