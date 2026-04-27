function results = simulate_live_step(tech, snrdB, numUsers, fadingProfile)
% SIMULATE_LIVE_STEP Runs 1 subframe of live simulation with true CQI feedback.
%
% Implements a real Link Adaptation loop:
%   1. Transmit using the MCS selected by the PREVIOUS subframe's CQI report.
%   2. At the receiver, estimate the channel and compute Effective SINR.
%   3. Map the Effective SINR to a CQI index (1-15).
%   4. Map the CQI to Modulation + TBS Index for the NEXT subframe.
%   5. Persist the CQI so the next call uses it.

    if nargin < 3
        numUsers = 1;
    end
    if nargin < 4
        fadingProfile = 'Pedestrian';
    end
    
    switch fadingProfile
        case 'Pedestrian'
            lteProfile = 'EPA';
        case 'Vehicular'
            lteProfile = 'EVA';
        case 'Urban'
            lteProfile = 'ETU';
        otherwise
            lteProfile = 'EPA';
    end

    % Persistent state across calls
    persistent enb4g pdsch4g chcfg4g tbs4g noiseEst4g cqi4g
    persistent enb5g pdsch5g chcfg5g tbs5g noiseEst5g cqi5g
    
    % ── CQI-to-MCS Mapping Table (3GPP TS 36.213 Table 7.2.3-1) ──
    % Each row: [CQI, Modulation Order, TBS Index]
    % Modulation Order: 2=QPSK, 4=16QAM, 6=64QAM
    cqiTable = [
        1,  2,  0;
        2,  2,  1;
        3,  2,  3;
        4,  2,  5;
        5,  2,  7;
        6,  2,  9;
        7,  4, 11;
        8,  4, 13;
        9,  4, 15;
       10,  6, 18;
       11,  6, 20;
       12,  6, 22;
       13,  6, 24;
       14,  6, 25;
       15,  6, 26;
    ];
    
    % ── SINR-to-CQI Mapping Thresholds (dB) ──
    % Based on 3GPP link-level performance curves for 10% BLER target.
    % sinrThresholds(i) is the minimum SINR required for CQI index i.
    sinrThresholds = [-6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, ...
                      10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7];

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
        pdsch4g.Modulation = 'QPSK';  % Start conservatively
        pdsch4g.NLayers = 1;
        pdsch4g.NTxAnts = 1;
        pdsch4g.RNTI = 1;
        pdsch4g.PRBSet = (0:enb4g.NDLRB-1)';
        pdsch4g.RV = 0;
        pdsch4g.NHARQProcesses = 8;
        
        chcfg4g = struct();
        chcfg4g.DelayProfile = lteProfile;
        chcfg4g.NRxAnts = 2;
        chcfg4g.DopplerFreq = 10;
        chcfg4g.MIMOCorrelation = 'Low';
        chcfg4g.InitPhase = 'Random';
        chcfg4g.ModelType = 'GMEDS';
        chcfg4g.NormalizeTxAnts = 'On';
        chcfg4g.NTerms = 16;
        chcfg4g.InitTime = 0;
        chcfg4g.Seed = randi([1 1000]);
        
        tbs4g = lteTBS(enb4g.NDLRB, 0);
        noiseEst4g = 1e-10;
        cqi4g = 7;  % Start at mid-range CQI
    end
    
    if isempty(enb5g)
        % Initialize 5G config (using LTE toolbox for speed with 5G parameters)
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
        pdsch5g.Modulation = 'QPSK';  % Start conservatively
        pdsch5g.NLayers = 1;
        pdsch5g.NTxAnts = 1;
        pdsch5g.RNTI = 1;
        pdsch5g.PRBSet = (0:enb5g.NDLRB-1)';
        pdsch5g.RV = 0;
        pdsch5g.NHARQProcesses = 8;
        
        chcfg5g = struct();
        chcfg5g.DelayProfile = lteProfile; % Dynamic profile
        chcfg5g.NRxAnts = 4; % More antennas for 5G
        chcfg5g.DopplerFreq = 10;
        chcfg5g.MIMOCorrelation = 'Low';
        chcfg5g.InitPhase = 'Random';
        chcfg5g.ModelType = 'GMEDS';
        chcfg5g.NormalizeTxAnts = 'On';
        chcfg5g.NTerms = 16;
        chcfg5g.InitTime = 0;
        chcfg5g.Seed = randi([1 1000]);
        
        tbs5g = lteTBS(enb5g.NDLRB, 0);
        noiseEst5g = 1e-10;
        cqi5g = 7;  % Start at mid-range CQI
    end
    
    % Dynamically update fading profile if it changed
    if ~strcmp(chcfg4g.DelayProfile, lteProfile)
        chcfg4g.DelayProfile = lteProfile;
    end
    if ~strcmp(chcfg5g.DelayProfile, lteProfile)
        chcfg5g.DelayProfile = lteProfile;
    end
    
    % ══════════════════════════════════════════════════════════════════════
    % STEP 1: Use the PREVIOUS subframe's CQI to select MCS for THIS frame
    % ══════════════════════════════════════════════════════════════════════
    if strcmp(tech, '5g')
        currentCqi = cqi5g;
    else
        currentCqi = cqi4g;
    end
    
    % Clamp CQI to valid range
    currentCqi = max(1, min(15, currentCqi));
    
    % Look up MCS from CQI table
    modOrder = cqiTable(currentCqi, 2);
    tbsIdx   = cqiTable(currentCqi, 3);
    
    switch modOrder
        case 2
            targetMod = 'QPSK';
        case 4
            targetMod = '16QAM';
        case 6
            targetMod = '64QAM';
        otherwise
            targetMod = 'QPSK';
    end
    
    % Apply MCS to selected technology
    if strcmp(tech, '5g')
        pdsch5g.Modulation = targetMod;
        tbs5g = lteTBS(enb5g.NDLRB, tbsIdx);
        
        enb = enb5g;
        pdsch = pdsch5g;
        chcfg = chcfg5g;
        tbs = tbs5g;
        noiseEst = noiseEst5g;
        baseLat = 1.0; 
        harqRTT = 2.0; 
        backhaul = 1.0;
        bwScale = (273 / numUsers) / 52;
    else
        pdsch4g.Modulation = targetMod;
        tbs4g = lteTBS(enb4g.NDLRB, tbsIdx);
        
        enb = enb4g;
        pdsch = pdsch4g;
        chcfg = chcfg4g;
        tbs = tbs4g;
        noiseEst = noiseEst4g;
        baseLat = 4.0 + (numUsers * 0.5);
        harqRTT = 8.0; 
        backhaul = 5.0;
        bwScale = (100 / numUsers) / 25;
    end
    
    enb.NSubframe = mod(enb.NSubframe + 1, 10);
    enb.PDSCH = pdsch;
    
    % ══════════════════════════════════════════════════════════════════════
    % STEP 2: Transmit the subframe through the fading channel
    % ══════════════════════════════════════════════════════════════════════
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
    
    % ══════════════════════════════════════════════════════════════════════
    % STEP 3: Channel estimation and equalization
    % ══════════════════════════════════════════════════════════════════════
    [hest, noiseEst] = lteDLChannelEstimate(enb, rxGrid);
    
    [eqGrid, ~] = lteEqualizeMMSE(rxGrid, hest, noiseEst);
    pdschRx = eqGrid(ind);
    
    % Decode
    [dlschBits, ~] = ltePDSCHDecode(enb, pdsch, pdschRx);
    [~, crcFlag] = lteDLSCHDecode(enb, pdsch, tbs, dlschBits);
    
    % ══════════════════════════════════════════════════════════════════════
    % STEP 4: Compute Effective SINR from the channel estimate (CQI feedback)
    % ══════════════════════════════════════════════════════════════════════
    % Calculate per-subcarrier SINR from the channel estimate and noise.
    % This SINR inherently includes ISI degradation because the channel
    % estimator sees the interference as additional noise/distortion.
    hestPower = mean(abs(hest(:)).^2);
    if noiseEst > 0
        effectiveSinr = 10 * log10(hestPower / noiseEst);
    else
        effectiveSinr = 30; % Cap at 30dB if noise estimate is zero
    end
    
    % Map Effective SINR to CQI index
    newCqi = 1;
    for ci = 1:15
        if effectiveSinr >= sinrThresholds(ci)
            newCqi = ci;
        end
    end
    
    % ══════════════════════════════════════════════════════════════════════
    % STEP 5: Persist the CQI for the NEXT call (simulates CQI reporting delay)
    % ══════════════════════════════════════════════════════════════════════
    if strcmp(tech, '5g')
        cqi5g = newCqi;
        enb5g.NSubframe = enb.NSubframe;
    else
        cqi4g = newCqi;
        enb4g.NSubframe = enb.NSubframe;
    end
    
    % ══════════════════════════════════════════════════════════════════════
    % STEP 6: Compute output metrics
    % ══════════════════════════════════════════════════════════════════════
    rawBler = double(crcFlag ~= 0);
    
    % For 5G URLLC, enforce a minimum reliability floor
    if strcmp(tech, '5g')
        if currentCqi >= 10
            targetBler = 1e-5;
        else
            targetBler = 1e-3 + rand() * 0.005;
        end
    else
        targetBler = 0.05 + 0.05 * rand();
    end
    bler = max(rawBler, targetBler);
    
    tput = (tbs * (1 - rawBler)) / 1e-3 / 1e6 * bwScale;
    avgReTx = min(bler / (1 - bler + 1e-9), 4);
    lat = baseLat + avgReTx * harqRTT + backhaul;
    if strcmp(tech, '5g')
        jit = 0.1 + (numUsers * 0.05) + bler * harqRTT;
    else
        jit = 0.5 + (numUsers * 0.2) + bler * harqRTT;
    end
    
    results = [double(bler), double(tput), double(lat), double(jit)];
end
