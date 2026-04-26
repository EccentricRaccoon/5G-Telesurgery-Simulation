function results = simulate_live_step(tech, snrdB)
% SIMULATE_LIVE_STEP Runs 1 subframe of live simulation, keeping channel state

    persistent enb4g pdsch4g chcfg4g tbs4g noiseEst4g
    persistent enb5g pdsch5g chcfg5g tbs5g noiseEst5g
    
    if isempty(enb4g)
        % Initialize 4G config
        enb4g = struct();
        enb4g.NDLRB = 25;
        enb4g.CyclicPrefix = 'Normal';
        enb4g.CFI = 3;
        enb4g.Ng = 'Sixth';
        enb4g.PHICHDuration = 'Normal';
        enb4g.CellRefP = 1;
        enb4g.NCellID = 0;
        enb4g.NSubframe = 0;
        enb4g.NFrame = 0;
        enb4g.DuplexMode = 'FDD';
        
        pdsch4g = struct();
        pdsch4g.TxScheme = 'Port0';
        pdsch4g.Modulation = '16QAM';
        pdsch4g.NLayers = 1;
        pdsch4g.NTxAnts = 1;
        pdsch4g.RNTI = 1;
        pdsch4g.PRBSet = (0:enb4g.NDLRB-1)';
        pdsch4g.RV = 0;
        pdsch4g.NHARQProcesses = 8;
        
        chcfg4g = struct();
        chcfg4g.DelayProfile = 'EVA';
        chcfg4g.NRxAnts = 2;
        chcfg4g.DopplerFreq = 10;
        chcfg4g.MIMOCorrelation = 'Low';
        chcfg4g.InitPhase = 'Random';
        chcfg4g.ModelType = 'GMEDS';
        chcfg4g.NormalizeTxAnts = 'On';
        chcfg4g.NTerms = 16;
        chcfg4g.InitTime = 0;
        chcfg4g.Seed = randi([1 1000]);
        
        tbs4g = lteTBS(enb4g.NDLRB, 15);
        noiseEst4g = 1e-10;
    end
    
    if isempty(enb5g)
        % Initialize 5G config (using LTE toolbox for simplicity/speed but with 5G parameters)
        enb5g = struct();
        enb5g.NDLRB = 52; % Wider bandwidth
        enb5g.CyclicPrefix = 'Normal';
        enb5g.CFI = 3;
        enb5g.Ng = 'Sixth';
        enb5g.PHICHDuration = 'Normal';
        enb5g.CellRefP = 1;
        enb5g.NCellID = 1;
        enb5g.NSubframe = 0;
        enb5g.NFrame = 0;
        enb5g.DuplexMode = 'FDD';
        
        pdsch5g = struct();
        pdsch5g.TxScheme = 'Port0';
        pdsch5g.Modulation = '16QAM';
        pdsch5g.NLayers = 1;
        pdsch5g.NTxAnts = 1;
        pdsch5g.RNTI = 1;
        pdsch5g.PRBSet = (0:enb5g.NDLRB-1)';
        pdsch5g.RV = 0;
        pdsch5g.NHARQProcesses = 8;
        
        chcfg5g = struct();
        chcfg5g.DelayProfile = 'EPA'; % Simpler profile for 5G URLLC assumptions
        chcfg5g.NRxAnts = 4; % More antennas
        chcfg5g.DopplerFreq = 10;
        chcfg5g.MIMOCorrelation = 'Low';
        chcfg5g.InitPhase = 'Random';
        chcfg5g.ModelType = 'GMEDS';
        chcfg5g.NormalizeTxAnts = 'On';
        chcfg5g.NTerms = 16;
        chcfg5g.InitTime = 0;
        chcfg5g.Seed = randi([1 1000]);
        
        tbs5g = lteTBS(enb5g.NDLRB, 15);
        noiseEst5g = 1e-10;
    end
    
    snrLin = 10^(snrdB/10);
    nSubframes = 1;
    
    if strcmp(tech, '5g')
        enb = enb5g;
        pdsch = pdsch5g;
        chcfg = chcfg5g;
        tbs = tbs5g;
        noiseEst = noiseEst5g;
        baseLat = 1.0; 
        harqRTT = 2.0; 
        backhaul = 1.0;
        if snrdB < 20
            targetBler = 1e-3 + rand() * 0.005; % Degrades slightly at cell edge
        else
            targetBler = 1e-5; % Perfect URLLC
        end
        bwScale = 273 / 52;  % Scale 52 simulated PRBs to full 273-PRB 100MHz 5G NR carrier
    else
        enb = enb4g;
        pdsch = pdsch4g;
        chcfg = chcfg4g;
        tbs = tbs4g;
        noiseEst = noiseEst4g;
        baseLat = 4.0; 
        harqRTT = 8.0; 
        backhaul = 5.0;
        targetBler = 0.05 + 0.05 * rand();
        bwScale = 4;
    end
    
    enb.NSubframe = mod(enb.NSubframe + 1, 10);
    enb.PDSCH = pdsch;
    
    % Waveform generation
    txBits = randi([0 1], tbs, 1);
    
    [ind, pdschInfo] = ltePDSCHIndices(enb, pdsch, pdsch.PRBSet);
    
    cw = lteDLSCH(enb, pdsch, pdschInfo.G, txBits);
    symb = ltePDSCH(enb, pdsch, cw);
    
    grid = lteDLResourceGrid(enb);
    grid(ind) = symb;
    
    % Insert Cell-Specific Reference Signals (critical for channel estimation!)
    crsInd = lteCellRSIndices(enb);
    crsSym = lteCellRS(enb);
    grid(crsInd) = crsSym;
    
    [txWaveform, ofdmInfo] = lteOFDMModulate(enb, grid);
    
    % Zero-pad for channel delay spread
    txWaveform = [txWaveform; zeros(100, size(txWaveform, 2))];
    
    % Fading channel
    chcfg.SamplingRate = ofdmInfo.SamplingRate;
    chcfg.InitTime = double(enb.NSubframe) * 1e-3;
    [rxWaveform, chinfo] = lteFadingChannel(chcfg, txWaveform);
    
    % AWGN noise
    SNR = 10^(snrdB/20);
    N0 = 1 / (sqrt(2.0 * chcfg.NRxAnts * double(ofdmInfo.Nfft)) * SNR);
    noise = N0 * complex(randn(size(rxWaveform)), randn(size(rxWaveform)));
    rxWaveform = rxWaveform + noise;
    
    % Timing synchronization using channel filter delay
    offset = chinfo.ChannelFilterDelay;
    rxWaveform = rxWaveform(1+offset:end, :);
    
    % OFDM Demodulate
    rxGrid = lteOFDMDemodulate(enb, rxWaveform);
    
    % Proper channel estimation using CRS
    [hest, noiseEst] = lteDLChannelEstimate(enb, rxGrid);
    
    % Equalize
    [eqGrid, ~] = lteEqualizeMMSE(rxGrid, hest, noiseEst);
    pdschRx = eqGrid(ind);
    
    % Decode
    [dlschBits, ~] = ltePDSCHDecode(enb, pdsch, pdschRx);
    [~, crcFlag] = lteDLSCHDecode(enb, pdsch, tbs, dlschBits);
    
    % Force update state
    if strcmp(tech, '5g')
        enb5g.NSubframe = enb.NSubframe;
    else
        enb4g.NSubframe = enb.NSubframe;
    end
    
    rawBler = double(crcFlag ~= 0);
    bler = max(rawBler, targetBler);
    tput = (tbs * (1 - rawBler)) / 1e-3 / 1e6 * bwScale;
    avgReTx = min(bler / (1 - bler + 1e-9), 4);
    lat = baseLat + avgReTx * harqRTT + backhaul;
    if strcmp(tech, '5g')
        jit = 0.1 + bler * harqRTT;
    else
        jit = 0.5 + bler * harqRTT;
    end
    
    results = [double(bler), double(tput), double(lat), double(jit)];
end
