# 5G Telesurgery Network Simulation

This project is a high-fidelity, real-time interactive simulation that compares the performance of 4G LTE and 5G NR networks in the context of remote robotic surgery. It is built using Python (Pygame) for the surgical simulation interface and MATLAB Engine for real-time network physical layer computations.

## Overview

The goal of this simulation is to visually and mechanically demonstrate the strict network requirements for URLLC (Ultra-Reliable Low-Latency Communication) applications like remote surgery. The simulation contrasts the high latency, jitter, and packet loss inherent in 4G networks against the ultra-low latency, high reliability, and smoothness of a 5G network.

### Key Features
*   **Real-time MATLAB Engine Integration:** Live computation of network metrics (BLER, throughput, latency, jitter) via background polling.
*   **Dynamic Jitter Mechanics (Micro-Stutters):** High network jitter causes the robot arm to periodically "freeze" (packet burst delays), making precision tasks organically difficult on 4G.
*   **Tissue Density Force Feedback:** The simulation calculates varying force resistance based on "tissue density". Veering off the surgical path inside dense tissue applies a massive penalty multiplier.
*   **Live Comparison Graphs:** A parallel multiprocessing window displays rolling live plots of BLER, Latency, Throughput, and Jitter, actively comparing 4G and 5G performance.
*   **Strict Precision Requirements:** The surgeon must complete 100% of the complex, serpentine incision path without letting their moving accuracy average drop below 90%.

## Architecture

The project is split into the Python Frontend and the MATLAB Backend.

*   `main.py`: The core Pygame application loop. Handles rendering, input, accuracy tracking, and the micro-stutter networking mechanic.
*   `network.py`: Manages the non-blocking asynchronous MATLAB Engine thread. Handles the simulated network packet queues, latency injection, and polling of live metrics.
*   `live_graphs.py`: Uses Python `multiprocessing` to run a separate `matplotlib` window that visualizes telemetry data without blocking the Pygame UI thread.
*   `robot.py` / `master_console.py`: Handles the physical state of the slave robot arm and the master surgical controller.
*   `simulate_live_step.m`: The primary MATLAB script called continuously by Python. Calculates current channel conditions, scales bandwidth (e.g., 273 PRBs for 5G vs. 100 PRBs for 4G), and determines packet success based on SNR.
*   `simulate_5g_link.m` & `simulate_4g_link.m`: MATLAB scripts containing the physical layer models (TDL-A / EPA channel models) and BLER vs. SNR lookup tables for the respective technologies.

## How to Run

### Prerequisites
*   Python 3.8+
*   MATLAB (R2023a or newer recommended) with the 5G Toolbox and LTE Toolbox.
*   Python `matlabengine` API installed (`pip install matlabengine`).
*   Pygame, NumPy, Matplotlib.

### Execution
Run the simulation by executing:
```bash
python main.py
```

### Controls
*   `1`: Switch to 5G NR (High SNR - 25dB) -> **Ideal Conditions**
*   `2`: Switch to 5G NR (Low SNR - 15dB) -> **Edge of Cell**
*   `3`: Switch to 4G LTE (High SNR - 25dB)
*   `4`: Switch to 4G LTE (Low SNR - 15dB)
*   `G`: Toggle Live Metrics Graph Window
*   `C`: Toggle In-Game HUD Comparison Mode
*   `R`: Manually restart the surgical procedure

## Gameplay Mechanics

Your objective is to trace the glowing green surgical path from start to finish with the highest possible precision. 
*   **Safe Zone:** You have a 5-pixel safe radius. Staying within this radius incurs no penalties.
*   **Dense Tissue (Red Zones):** If you stray outside the safe radius while inside a dense tissue zone, the accuracy penalty is amplified by up to 4x based on force resistance.
*   **4G vs 5G Impact:** If you attempt the surgery on 4G, high latency will cause your scalpel to lag behind your cursor, and high jitter will cause unpredictable "Signal Stalled" micro-freezes. This combination makes navigating the tight switchbacks without failing nearly impossible. Switching to 5G eliminates the lag and stutter, providing a 1:1 control experience.
