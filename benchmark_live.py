import matlab.engine
import time

print("Starting MATLAB...")
eng = matlab.engine.start_matlab()

import os
eng.addpath(os.path.dirname(os.path.abspath(__file__)), nargout=0)

print("Warming up (first call initializes persistent state)...")
res = eng.simulate_live_step('4g', 15.0, nargout=1)
print(f"4G warmup result: {res}")

print("\nBenchmarking 10 live steps for 4G...")
start = time.time()
for i in range(10):
    res = eng.simulate_live_step('4g', 15.0, nargout=1)
elapsed = time.time() - start
print(f"4G: {elapsed:.2f}s total, {elapsed/10*1000:.0f}ms per step")
print(f"  Last result: BLER={res[0][0]:.5f}, Tput={res[0][1]:.1f}, Lat={res[0][2]:.1f}, Jit={res[0][3]:.2f}")

print("\nBenchmarking 10 live steps for 5G...")
start = time.time()
for i in range(10):
    res = eng.simulate_live_step('5g', 15.0, nargout=1)
elapsed = time.time() - start
print(f"5G: {elapsed:.2f}s total, {elapsed/10*1000:.0f}ms per step")
print(f"  Last result: BLER={res[0][0]:.5f}, Tput={res[0][1]:.1f}, Lat={res[0][2]:.1f}, Jit={res[0][3]:.2f}")

eng.quit()
print("\nDone!")
