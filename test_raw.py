import matlab.engine
eng = matlab.engine.start_matlab()
res = eng.simulate_4g_link(nargout=1)
print(res)
eng.quit()
