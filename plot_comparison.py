"""
plot_comparison.py - Generate publication-quality 5G vs 4G comparison plots.

Creates side-by-side plots comparing 5G NR and 4G LTE performance metrics
(BLER, Throughput, Latency) from MATLAB simulation results, with annotated
telesurgery safety thresholds.
"""

import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for compatibility with pygame
import matplotlib.pyplot as plt
import numpy as np


def plot_5g_vs_4g_comparison(results_5g, results_4g, save_path=None):
    """
    Generate a multi-panel comparison figure for 5G NR vs 4G LTE.
    
    Args:
        results_5g: Nx5 numpy array [SNR, BLER, Throughput, Latency, Jitter]
        results_4g: Nx5 numpy array [SNR, BLER, Throughput, Latency, Jitter]
        save_path: Optional path to save the figure as PNG.
    """
    snr_5g = results_5g[:, 0]
    snr_4g = results_4g[:, 0]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('5G NR vs 4G LTE — Remote Surgery Link Performance\n'
                 '(TDL-A / EVA Urban Channel, 2×2 MIMO)',
                 fontsize=14, fontweight='bold', y=0.98)

    # ── Plot 1: BLER vs SNR ──
    ax1 = axes[0, 0]
    bler_5g = np.clip(results_5g[:, 1], 1e-6, 1.0)
    bler_4g = np.clip(results_4g[:, 1], 1e-6, 1.0)
    
    ax1.semilogy(snr_5g, bler_5g, 'b-o', linewidth=2, markersize=5, label='5G NR (100 MHz, LDPC)')
    ax1.semilogy(snr_4g, bler_4g, 'r-s', linewidth=2, markersize=5, label='4G LTE (20 MHz, Turbo)')
    ax1.axhline(y=1e-5, color='green', linestyle='--', alpha=0.7, label='URLLC Target (10⁻⁵)')
    ax1.fill_between(snr_5g, 1e-6, 1e-5, alpha=0.1, color='green')
    ax1.set_xlabel('SNR (dB)')
    ax1.set_ylabel('Block Error Rate (BLER)')
    ax1.set_title('BLER vs SNR')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([1e-6, 1.5])
    ax1.annotate('Surgery\nSafe Zone', xy=(25, 1e-5), fontsize=8,
                 color='green', ha='center', va='top', fontweight='bold')

    # ── Plot 2: Throughput vs SNR ──
    ax2 = axes[0, 1]
    ax2.plot(snr_5g, results_5g[:, 2], 'b-o', linewidth=2, markersize=5, label='5G NR')
    ax2.plot(snr_4g, results_4g[:, 2], 'r-s', linewidth=2, markersize=5, label='4G LTE')
    ax2.axhline(y=100, color='orange', linestyle='--', alpha=0.7, label='4K Stereo Video (100 Mbps)')
    ax2.set_xlabel('SNR (dB)')
    ax2.set_ylabel('Throughput (Mbps)')
    ax2.set_title('Throughput vs SNR')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # ── Plot 3: Latency vs SNR ──
    ax3 = axes[1, 0]
    ax3.plot(snr_5g, results_5g[:, 3], 'b-o', linewidth=2, markersize=5, label='5G NR')
    ax3.plot(snr_4g, results_4g[:, 3], 'r-s', linewidth=2, markersize=5, label='4G LTE')
    ax3.axhline(y=10, color='green', linestyle='--', alpha=0.7, label='Haptic Feedback Limit (10 ms)')
    ax3.fill_between(snr_5g, 0, 10, alpha=0.1, color='green')
    ax3.set_xlabel('SNR (dB)')
    ax3.set_ylabel('One-Way Latency (ms)')
    ax3.set_title('Latency vs SNR')
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)
    ax3.annotate('Haptic\nSafe Zone', xy=(25, 5), fontsize=8,
                 color='green', ha='center', fontweight='bold')

    # ── Plot 4: Jitter vs SNR ──
    ax4 = axes[1, 1]
    ax4.plot(snr_5g, results_5g[:, 4], 'b-o', linewidth=2, markersize=5, label='5G NR')
    ax4.plot(snr_4g, results_4g[:, 4], 'r-s', linewidth=2, markersize=5, label='4G LTE')
    ax4.axhline(y=1.0, color='green', linestyle='--', alpha=0.7, label='Jitter Limit (1 ms)')
    ax4.set_xlabel('SNR (dB)')
    ax4.set_ylabel('Jitter (ms)')
    ax4.set_title('Jitter vs SNR')
    ax4.legend(fontsize=8)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Comparison plot saved to: {save_path}")
    
    plt.show(block=False)
    plt.pause(0.1)


def plot_summary_table(results_5g, results_4g, snr_point=20):
    """Print a text comparison table at a specific SNR point."""
    idx_5g = np.argmin(np.abs(results_5g[:, 0] - snr_point))
    idx_4g = np.argmin(np.abs(results_4g[:, 0] - snr_point))
    
    r5 = results_5g[idx_5g]
    r4 = results_4g[idx_4g]
    
    print(f"\n{'='*60}")
    print(f"  5G NR vs 4G LTE Comparison @ SNR = {snr_point} dB")
    print(f"{'='*60}")
    print(f"  {'Metric':<25} {'5G NR':>12} {'4G LTE':>12} {'Advantage':>10}")
    print(f"  {'-'*55}")
    print(f"  {'BLER':<25} {r5[1]:>12.6f} {r4[1]:>12.6f} {'5G ✓' if r5[1] < r4[1] else '4G':>10}")
    print(f"  {'Throughput (Mbps)':<25} {r5[2]:>12.2f} {r4[2]:>12.2f} {'5G ✓' if r5[2] > r4[2] else '4G':>10}")
    print(f"  {'Latency (ms)':<25} {r5[3]:>12.2f} {r4[3]:>12.2f} {'5G ✓' if r5[3] < r4[3] else '4G':>10}")
    print(f"  {'Jitter (ms)':<25} {r5[4]:>12.2f} {r4[4]:>12.2f} {'5G ✓' if r5[4] < r4[4] else '4G':>10}")
    print(f"{'='*60}\n")
