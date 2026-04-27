import time
import random
import os
import csv
import numpy as np

class Matlab5GNetwork:
    """
    Network simulator backed by live MATLAB link-level simulation.
    
    Uses a non-blocking polling pattern: each frame, the main loop calls
    poll_live_step() which checks if the last async MATLAB call completed.
    If so, it consumes the result and fires a new one. No background threads.
    
    Falls back to pre-generated CSV files if MATLAB engine is unavailable.
    """

    def __init__(self, use_matlab=True):
        """
        Initialize the network simulator.
        
        Args:
            use_matlab: If True, attempt to start MATLAB engine and run simulations.
                       If False (or if MATLAB unavailable), use fallback CSV files.
        """
        self.results_5g = None
        self.results_4g = None
        self.matlab_engine = None
        self.using_matlab = False
        self.live_mode = False
        
        self.active_tech = '5g'
        self.active_snr = 20
        self.num_users = 1
        self.fading_profile = 'Pedestrian'
        
        self.current_bler = 0.0
        self.current_throughput = 0.0
        self.current_latency = 2.0
        self.current_jitter = 0.1
        
        self.master_to_slave_queue = []
        self.slave_to_master_queue = []
        
        self.packets_sent = 0
        self.packets_dropped = 0
        
        self.compare_bler = 0.0
        self.compare_throughput = 0.0
        self.compare_latency = 10.0
        self.compare_jitter = 1.0
        
        self._pending_future = None
        self._compare_future = None
        self._poll_paused = False
        
        if use_matlab:
            self._try_matlab_simulation()
        
        if not self.using_matlab:
            self._load_fallback_csv()
        
        self._update_metrics()

    def _try_matlab_simulation(self):
        """Attempt to start MATLAB engine for live simulation."""
        try:
            import matlab.engine
            print("Starting MATLAB engine (this may take 10-15 seconds)...")
            self.matlab_engine = matlab.engine.start_matlab()
            
            project_dir = os.path.dirname(os.path.abspath(__file__))
            self.matlab_engine.addpath(project_dir, nargout=0)
            
            try:
                self._load_fallback_csv()
                print("  (CSV data loaded for comparison panel)")
            except Exception:
                print("  (No CSV found — comparison panel will use live data)")
            
            self.using_matlab = True
            self.live_mode = True
            
            self._fire_live_step()
            print(">>> Live MATLAB simulation ready! <<<")
            
        except ImportError:
            print("MATLAB Engine not available. Using fallback CSV data.")
        except Exception as e:
            print(f"MATLAB error: {e}")
            print("Falling back to CSV data.")
            self.using_matlab = False
            self.live_mode = False
            if self.matlab_engine:
                try:
                    self.matlab_engine.quit()
                except:
                    pass
                self.matlab_engine = None

    def _fire_live_step(self):
        """Fire async MATLAB calls for both active and comparison techs."""
        if not self.matlab_engine or self._poll_paused:
            return
        try:
            self._pending_future = self.matlab_engine.simulate_live_step(
                self.active_tech, float(self.active_snr),
                float(self.num_users), self.fading_profile,
                nargout=1, background=True
            )
        except Exception as e:
            print(f"Live fire error: {e}")
            self._pending_future = None

    def _fire_compare_step(self):
        """Fire an async MATLAB call for the comparison (other) technology."""
        if not self.matlab_engine or self._poll_paused:
            return
        compare_tech = '4g' if self.active_tech == '5g' else '5g'
        try:
            self._compare_future = self.matlab_engine.simulate_live_step(
                compare_tech, float(self.active_snr),
                float(self.num_users), self.fading_profile,
                nargout=1, background=True
            )
        except Exception as e:
            print(f"Compare fire error: {e}")
            self._compare_future = None

    def poll_live_step(self):
        """Call every frame from the main loop. Non-blocking.
        Polls both the active and comparison MATLAB futures."""
        if not self.live_mode or self._poll_paused:
            return
        
        if self._pending_future is not None:
            try:
                if self._pending_future.done():
                    res = self._pending_future.result()
                    metrics = res[0]
                    self.current_bler = float(metrics[0])
                    self.current_throughput = float(metrics[1])
                    self.current_latency = float(metrics[2])
                    self.current_jitter = float(metrics[3])
                    self._pending_future = None
                    self._fire_compare_step()
            except Exception as e:
                print(f"Live poll error: {e}")
                self._pending_future = None
                self._fire_live_step()
        
        if self._compare_future is not None:
            try:
                if self._compare_future.done():
                    res = self._compare_future.result()
                    metrics = res[0]
                    self.compare_bler = float(metrics[0])
                    self.compare_throughput = float(metrics[1])
                    self.compare_latency = float(metrics[2])
                    self.compare_jitter = float(metrics[3])
                    self._compare_future = None
                    self._fire_live_step()
            except Exception as e:
                print(f"Compare poll error: {e}")
                self._compare_future = None
                self._fire_live_step()

    def _matlab_to_numpy(self, matlab_array):
        """Convert MATLAB double array to numpy array."""
        return np.array(matlab_array)

    def _load_fallback_csv(self):
        """Load pre-generated results from CSV files."""
        project_dir = os.path.dirname(os.path.abspath(__file__))
        
        csv_5g = os.path.join(project_dir, '5g_nr_results.csv')
        csv_4g = os.path.join(project_dir, '4g_lte_results.csv')
        
        self.results_5g = self._read_csv(csv_5g)
        self.results_4g = self._read_csv(csv_4g)
        
        print(f"Loaded fallback CSV data (5G: {len(self.results_5g)} points, 4G: {len(self.results_4g)} points)")

    def _read_csv(self, filepath):
        """Read a results CSV file into a numpy array."""
        rows = []
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append([
                    float(row['SNR_dB']),
                    float(row['BLER']),
                    float(row['Throughput_Mbps']),
                    float(row['Latency_ms']),
                    float(row['Jitter_ms'])
                ])
        return np.array(rows)

    def _save_results_csv(self, results, filename):
        """Save simulation results to CSV for future use."""
        project_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(project_dir, filename)
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['SNR_dB', 'BLER', 'Throughput_Mbps', 'Latency_ms', 'Jitter_ms'])
            for row in results:
                writer.writerow([f"{row[0]:.0f}", f"{row[1]:.2e}", 
                               f"{row[2]:.2f}", f"{row[3]:.2f}", f"{row[4]:.2f}"])

    def _interpolate_metric(self, table, snr_db, col_idx):
        """Linearly interpolate a metric from the results table for a given SNR."""
        snr_col = table[:, 0]
        metric_col = table[:, col_idx]
        
        snr_db = max(snr_col[0], min(snr_col[-1], snr_db))
        
        return float(np.interp(snr_db, snr_col, metric_col))

    def _update_metrics(self):
        """Update current network metrics based on active technology and SNR."""
        table = self.results_5g if self.active_tech == '5g' else self.results_4g
        
        if table is not None and len(table) > 0:
            self.current_bler = self._interpolate_metric(table, self.active_snr, 1)
            self.current_throughput = self._interpolate_metric(table, self.active_snr, 2)
            self.current_latency = self._interpolate_metric(table, self.active_snr, 3)
            self.current_jitter = self._interpolate_metric(table, self.active_snr, 4)

    def set_technology(self, tech):
        """Switch between '5g' and '4g' network technology."""
        if tech in ('5g', '4g'):
            self.active_tech = tech
            if not self.live_mode:
                self._update_metrics()

    def set_snr(self, snr_db):
        """Set the SNR operating point."""
        self.active_snr = snr_db
        if not self.live_mode:
            self._update_metrics()

    def set_num_users(self, count):
        """Set the number of active users in the network."""
        self.num_users = max(1, count)
        if not self.live_mode:
            self._update_metrics()

    def cycle_fading_profile(self):
        """Cycle through the available fading profiles."""
        profiles = ['Pedestrian', 'Vehicular', 'Urban']
        idx = profiles.index(self.fading_profile)
        self.fading_profile = profiles[(idx + 1) % len(profiles)]
        if not self.live_mode:
            self._update_metrics()

    def get_current_metrics(self):
        """Return current network metrics as a dictionary."""
        return {
            'technology': '5G NR' if self.active_tech == '5g' else '4G LTE',
            'snr_db': self.active_snr,
            'num_users': self.num_users,
            'fading_profile': self.fading_profile,
            'bler': self.current_bler,
            'throughput_mbps': self.current_throughput,
            'latency_ms': self.current_latency,
            'jitter_ms': self.current_jitter,
            'packets_sent': self.packets_sent,
            'packets_dropped': self.packets_dropped,
            'using_matlab': self.using_matlab,
            'live_mode': self.live_mode
        }

    def get_comparison_metrics(self, snr_db=None):
        """Return live metrics for both 5G and 4G."""
        if self.live_mode:
            active = {
                'bler': self.current_bler,
                'throughput': self.current_throughput,
                'latency': self.current_latency,
                'jitter': self.current_jitter,
            }
            compare = {
                'bler': self.compare_bler,
                'throughput': self.compare_throughput,
                'latency': self.compare_latency,
                'jitter': self.compare_jitter,
            }
            if self.active_tech == '5g':
                return active, compare
            else:
                return compare, active
        
        if snr_db is None:
            snr_db = self.active_snr
        metrics_5g = {
            'bler': self._interpolate_metric(self.results_5g, snr_db, 1),
            'throughput': self._interpolate_metric(self.results_5g, snr_db, 2),
            'latency': self._interpolate_metric(self.results_5g, snr_db, 3),
            'jitter': self._interpolate_metric(self.results_5g, snr_db, 4),
        }
        metrics_4g = {
            'bler': self._interpolate_metric(self.results_4g, snr_db, 1),
            'throughput': self._interpolate_metric(self.results_4g, snr_db, 2),
            'latency': self._interpolate_metric(self.results_4g, snr_db, 3),
            'jitter': self._interpolate_metric(self.results_4g, snr_db, 4),
        }
        return metrics_5g, metrics_4g

    def _calculate_delay(self):
        """Calculate packet delay from MATLAB-derived latency + jitter."""
        jitter_val = random.gauss(0, self.current_jitter / 1000.0)
        delay = (self.current_latency / 1000.0) + jitter_val
        return max(0.001, delay)

    def _should_drop_packet(self):
        """Determine if packet should be dropped based on BLER."""
        return random.random() < self.current_bler

    def send_to_slave(self, payload):
        """Master sends a command to the Slave (robot) over the network."""
        self.packets_sent += 1
        
        if self._should_drop_packet():
            self.packets_dropped += 1
            return
        
        delivery_time = time.time() + self._calculate_delay()
        self.master_to_slave_queue.append((delivery_time, payload))

    def send_to_master(self, payload):
        """Slave sends feedback to the Master over the network."""
        self.packets_sent += 1
        
        if self._should_drop_packet():
            self.packets_dropped += 1
            return
        
        delivery_time = time.time() + self._calculate_delay()
        self.slave_to_master_queue.append((delivery_time, payload))

    def receive_from_master(self):
        """Slave receives commands that have arrived from Master."""
        current_time = time.time()
        arrived = []
        pending = []
        
        for delivery_time, payload in self.master_to_slave_queue:
            if current_time >= delivery_time:
                arrived.append(payload)
            else:
                pending.append((delivery_time, payload))
        
        self.master_to_slave_queue = pending
        return arrived

    def receive_from_slave(self):
        """Master receives feedback that has arrived from Slave."""
        current_time = time.time()
        arrived = []
        pending = []
        
        for delivery_time, payload in self.slave_to_master_queue:
            if current_time >= delivery_time:
                arrived.append(payload)
            else:
                pending.append((delivery_time, payload))
        
        self.slave_to_master_queue = pending
        return arrived

    def get_results_tables(self):
        """Return raw results tables for plotting."""
        return self.results_5g, self.results_4g

    def cleanup(self):
        """Shut down MATLAB engine."""
        self.live_mode = False
        if self._pending_future is not None:
            try:
                self._pending_future.cancel()
            except:
                pass
            self._pending_future = None
        if self.matlab_engine:
            try:
                self.matlab_engine.quit()
                print("MATLAB engine shut down.")
            except:
                pass
