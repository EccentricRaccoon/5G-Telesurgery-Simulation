import matlab.engine
print("Starting MATLAB engine...")
eng = matlab.engine.start_matlab()
try:
    code = """
    enb = struct('NDLRB', 25, 'CyclicPrefix', 'Normal');
    chcfg = struct('DelayProfile', 'EVA', 'NRxAnts', 2, 'DopplerFreq', 10, 'MIMOCorrelation', 'Low', 'InitTime', 0, 'Seed', 1, 'ModelType', 'GMEDS', 'NTerms', 16, 'NormalizeTxAnts', 'On', 'NormalizePathGains', 'On', 'SamplingRate', 7.68e6);
    txWav = zeros(7680, 1);
    [rxWav, info] = lteFadingChannel(chcfg, txWav);
    disp(info);
    """
    eng.eval(code, nargout=0)
except Exception as e:
    print(f"Error: {e}")
eng.quit()
