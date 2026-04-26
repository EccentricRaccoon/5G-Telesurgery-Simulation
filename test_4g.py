import matlab.engine
print("Starting MATLAB engine...")
eng = matlab.engine.start_matlab()
try:
    print("Running simulate_4g_link...")
    res = eng.simulate_4g_link()
    print("Success")
except Exception as e:
    print(f"Error: {e}")
eng.quit()
