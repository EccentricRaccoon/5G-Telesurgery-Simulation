import matlab.engine
eng = matlab.engine.start_matlab()
res = eng.simulate_4g_link(nargout=1)
print(f"Res type: {type(res)}")
if len(res) > 2:
    print(f"Row 2: {res[2]}")
eng.quit()
