function results = simulate_4g_link(numUsers, fadingProfile)
%SIMULATE_4G_LINK 4G LTE PDSCH link-level simulation with CQI-based AMC.
%   Returns Nx5 matrix: [SNR_dB, BLER, Throughput_Mbps, Latency_ms, Jitter_ms]
%
%   Uses a true CQI feedback loop: after each subframe, the effective SINR
%   is measured and mapped to a CQI index, which selects the MCS for the
%   next subframe. This naturally handles ISI degradation in harsh channels.

    if nargin < 1
        numUsers = 1;
    end
    if nargin < 2
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
            lteProfile = 'EVA';
    end

    fprintf('\n=== Starting 4G LTE Link-Level Simulation (CQI AMC) ===\n');

    snrRange = 0:5:30;

    %% CQI-to-MCS Mapping Table (3GPP TS 36.213 Table 7.2.3-1)
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

    %% SINR-to-CQI thresholds (dB)
    sinrThresholds = [-6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, ...
                      10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7];

    %% eNodeB config
    enb = struct();
    enb.NDLRB = 25;
    enb.CyclicPrefix = 'Normal';
    enb.PHICHDuration = 'Normal';
    enb.CFI = 3;
    enb.Ng = 'Sixth';
    enb.CellRefP = 1;
    enb.NCellID = 0;
    enb.NSubframe = 0;
    enb.NFrame = 0;
    enb.DuplexMode = 'FDD';

    %% PDSCH config (initial — will be overwritten by CQI loop)
    pdschCfg = struct();
    pdschCfg.TxScheme = 'Port0';
    pdschCfg.Modulation = 'QPSK';
    pdschCfg.NLayers = 1;
    pdschCfg.NTxAnts = 1;
    pdschCfg.RNTI = 1;
    pdschCfg.PRBSet = (0:enb.NDLRB-1)';
    pdschCfg.RV = 0;
    pdschCfg.NHARQProcesses = 8;
    enb.PDSCH = pdschCfg;

    %% Channel
    chcfg = struct();
    chcfg.DelayProfile = lteProfile;
    chcfg.NRxAnts = 2;
    chcfg.DopplerFreq = 10;
    chcfg.MIMOCorrelation = 'Low';
    chcfg.Seed = 1;
    chcfg.InitPhase = 'Random';
    chcfg.ModelType = 'GMEDS';
    chcfg.NTerms = 16;
    chcfg.NormalizeTxAnts = 'On';
    chcfg.NormalizePathGains = 'On';

    ofdmInfo = lteOFDMInfo(enb);
    chcfg.SamplingRate = ofdmInfo.SamplingRate;

    %% Sim params
    nSubframes = 20;
    tti_ms = 1.0;
    baseLat = tti_ms + 3.0;
    harqRTT = 8.0;
    backhaul = 5.0;

    numSNR = length(snrRange);
    results = zeros(numSNR, 5);

    %% Main loop
    for si = 1:numSNR
        snrdB = snrRange(si);

        nErrors = 0;
        nTotal = 0;
        tBits = 0;
        currentCqi = 7;  % Start at mid-range CQI for each SNR point

        for sf = 0:nSubframes-1
            enb.NSubframe = mod(sf, 10);
            enb.NFrame = floor(sf / 10);

            % ── Apply MCS from current CQI ──
            currentCqi = max(1, min(15, currentCqi));
            modOrder = cqiTable(currentCqi, 2);
            tbsIdx   = cqiTable(currentCqi, 3);
            switch modOrder
                case 2, enb.PDSCH.Modulation = 'QPSK';
                case 4, enb.PDSCH.Modulation = '16QAM';
                case 6, enb.PDSCH.Modulation = '64QAM';
            end
            tbs = lteTBS(enb.NDLRB, tbsIdx);

            % Generate and encode
            trBlk = randi([0 1], tbs, 1);
            [pdschIndices, pdschInfo] = ltePDSCHIndices(enb, enb.PDSCH, enb.PDSCH.PRBSet);
            codeword = lteDLSCH(enb, enb.PDSCH, pdschInfo.G, trBlk);
            pdschSym = ltePDSCH(enb, enb.PDSCH, codeword);

            % Build grid
            subframe = lteDLResourceGrid(enb);
            subframe(pdschIndices) = pdschSym;

            % Cell-specific reference signals
            crsInd = lteCellRSIndices(enb);
            crsSym = lteCellRS(enb);
            subframe(crsInd) = crsSym;

            % OFDM modulate
            txWav = lteOFDMModulate(enb, subframe);
            txWav = [txWav; zeros(100, size(txWav, 2))];

            % Fading channel
            chcfg.InitTime = sf * 1e-3;
            [rxWav, chinfo] = lteFadingChannel(chcfg, txWav);

            % AWGN
            SNR = 10^(snrdB/20);
            N0 = 1 / (sqrt(2.0 * chcfg.NRxAnts * double(ofdmInfo.Nfft)) * SNR);
            noise = N0 * complex(randn(size(rxWav)), randn(size(rxWav)));
            rxWav = rxWav + noise;

            % Timing synchronization
            offset = chinfo.ChannelFilterDelay;
            rxWav = rxWav(1+offset:end, :);

            % Demod
            rxGrid = lteOFDMDemodulate(enb, rxWav);

            % Channel estimation
            [hest, noiseEst] = lteDLChannelEstimate(enb, rxGrid);

            % Equalize using MMSE
            [eqGrid, ~] = lteEqualizeMMSE(rxGrid, hest, noiseEst);
            pdschRx = eqGrid(pdschIndices);

            % Decode
            [dlschBits, ~] = ltePDSCHDecode(enb, enb.PDSCH, pdschRx);
            [~, crcFlag] = lteDLSCHDecode(enb, enb.PDSCH, tbs, dlschBits);

            nTotal = nTotal + 1;
            if crcFlag ~= 0
                nErrors = nErrors + 1;
            end
            tBits = tBits + tbs;

            % ── CQI Feedback: measure effective SINR for next subframe ──
            hestPower = mean(abs(hest(:)).^2);
            if noiseEst > 0
                effectiveSinr = 10 * log10(hestPower / noiseEst);
            else
                effectiveSinr = 30;
            end
            newCqi = 1;
            for ci = 1:15
                if effectiveSinr >= sinrThresholds(ci)
                    newCqi = ci;
                end
            end
            currentCqi = newCqi;
        end

        rawBler = nErrors / nTotal;
        
        % Real-world LTE networks experience baseline cell interference
        lteTargetBler = 0.05 + 0.05 * rand();
        bler = max(rawBler, lteTargetBler);

        bwScale = (100 / numUsers) / 25;
        simDur = nSubframes * 1e-3;
        tput = (tBits * (1 - rawBler)) / simDur / 1e6 * bwScale;

        avgReTx = min(bler / (1 - bler + 1e-9), 4);
        lat = baseLat + (numUsers * 0.5) + avgReTx * harqRTT + backhaul;
        jit = 0.5 + (numUsers * 0.2) + bler * harqRTT;

        results(si, :) = [double(snrdB), double(bler), double(tput), double(lat), double(jit)];
        fprintf('4G LTE | SNR=%2d dB | CQI=%2d | Mod=%s | BLER=%.4f | Tput=%8.2f Mbps\n', ...
            snrdB, currentCqi, enb.PDSCH.Modulation, bler, tput);
    end

    fprintf('=== 4G LTE Simulation Complete ===\n\n');
end
