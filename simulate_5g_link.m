function results = simulate_5g_link(numUsers, fadingProfile)
%SIMULATE_5G_LINK 5G NR PDSCH link-level simulation with CQI-based AMC.
%   Returns Nx5 matrix: [SNR_dB, BLER, Throughput_Mbps, Latency_ms, Jitter_ms]
%
%   Uses a true CQI feedback loop: after each slot, the effective SINR
%   is measured and mapped to a CQI index, which selects the MCS for the
%   next slot. This naturally handles channel degradation.

    if nargin < 1
        numUsers = 1;
    end
    if nargin < 2
        fadingProfile = 'Pedestrian';
    end

    switch fadingProfile
        case 'Pedestrian'
            nrProfile = 'TDL-A';
        case 'Vehicular'
            nrProfile = 'TDL-B';
        case 'Urban'
            nrProfile = 'TDL-C';
        otherwise
            nrProfile = 'TDL-A';
    end

    fprintf('\n=== Starting 5G NR Link-Level Simulation (CQI AMC) ===\n');

    snrRange = 0:5:30;

    %% CQI-to-MCS Mapping (NR uses similar table to LTE for outer loop)
    % [CQI, ModulationOrder, TargetCodeRate]
    cqiCodeRates = [
        1,  2, 0.076;
        2,  2, 0.12;
        3,  2, 0.19;
        4,  2, 0.30;
        5,  2, 0.44;
        6,  2, 0.59;
        7,  4, 0.37;
        8,  4, 0.48;
        9,  4, 0.60;
       10,  6, 0.46;
       11,  6, 0.55;
       12,  6, 0.65;
       13,  6, 0.75;
       14,  6, 0.85;
       15,  6, 0.93;
    ];

    %% SINR-to-CQI thresholds (dB)
    sinrThresholds = [-6.7, -4.7, -2.3, 0.2, 2.4, 4.3, 5.9, 8.1, ...
                      10.3, 11.7, 14.1, 16.3, 18.7, 21.0, 22.7];

    %% Carrier
    carrier = nrCarrierConfig;
    carrier.NSizeGrid = 51;
    carrier.SubcarrierSpacing = 30;
    carrier.CyclicPrefix = 'Normal';
    carrier.NCellID = 1;

    %% PDSCH - single layer
    pdsch = nrPDSCHConfig;
    pdsch.MappingType = 'A';
    pdsch.SymbolAllocation = [0 14];
    pdsch.PRBSet = 0:carrier.NSizeGrid-1;
    pdsch.Modulation = 'QPSK';  % Start conservatively
    pdsch.NumLayers = 1;
    pdsch.NID = carrier.NCellID;
    pdsch.RNTI = 1;
    pdsch.DMRS.DMRSConfigurationType = 1;
    pdsch.DMRS.DMRSLength = 1;
    pdsch.DMRS.DMRSAdditionalPosition = 1;
    pdsch.DMRS.NumCDMGroupsWithoutData = 2;
    pdsch.DMRS.DMRSPortSet = 0;

    %% Encoder / Decoder
    encDL = nrDLSCH;
    encDL.MultipleHARQProcesses = false;

    decDL = nrDLSCHDecoder;
    decDL.MultipleHARQProcesses = false;
    decDL.LDPCDecodingAlgorithm = 'Normalized min-sum';

    %% Channel
    nTxAnts = 1;
    nRxAnts = 2;
    channel = nrTDLChannel;
    channel.DelayProfile = nrProfile;
    channel.DelaySpread = 300e-9;
    channel.MaximumDopplerShift = 10;
    channel.NumTransmitAntennas = nTxAnts;
    channel.NumReceiveAntennas = nRxAnts;

    ofdmInfo = nrOFDMInfo(carrier);
    channel.SampleRate = ofdmInfo.SampleRate;

    %% Latency model
    slotDur = 1.0 / (carrier.SubcarrierSpacing / 15);
    baseLat = slotDur + 0.5;
    harqRTT = 2 * slotDur + 1.0;
    backhaul = 1.0;

    nFrames = 2;
    numSNR = length(snrRange);
    results = zeros(numSNR, 5);

    %% Simulation
    for si = 1:numSNR
        snrdB = snrRange(si);
        nErrors = 0;
        nTotal = 0;
        tBits = 0;
        currentCqi = 7;  % Start at mid-range CQI

        reset(channel);
        reset(encDL);
        reset(decDL);

        for fr = 1:nFrames
            for sl = 0:carrier.SlotsPerFrame-1
                carrier.NSlot = sl;

                % ── Apply MCS from current CQI ──
                currentCqi = max(1, min(15, currentCqi));
                modOrder       = cqiCodeRates(currentCqi, 2);
                targetCodeRate = cqiCodeRates(currentCqi, 3);
                switch modOrder
                    case 2, pdsch.Modulation = 'QPSK';
                    case 4, pdsch.Modulation = '16QAM';
                    case 6, pdsch.Modulation = '64QAM';
                end

                [pdschIndices, pdschInfo] = nrPDSCHIndices(carrier, pdsch);
                tbs = nrTBS(pdsch.Modulation, pdsch.NumLayers, ...
                    numel(pdsch.PRBSet), pdschInfo.NREPerPRB, targetCodeRate);

                encDL.TargetCodeRate = targetCodeRate;
                decDL.TargetCodeRate = targetCodeRate;
                decDL.TransportBlockLength = tbs;

                dmrsIndices = nrPDSCHDMRSIndices(carrier, pdsch);
                dmrsSymbols = nrPDSCHDMRS(carrier, pdsch);

                % Transmit
                trBlk = randi([0 1], tbs, 1);
                setTransportBlock(encDL, trBlk);
                codedBits = encDL(pdsch.Modulation, pdsch.NumLayers, pdschInfo.G, 0);

                pdschSym = nrPDSCH(carrier, pdsch, codedBits);
                txGrid = nrResourceGrid(carrier, nTxAnts);
                txGrid(pdschIndices) = pdschSym;
                txGrid(dmrsIndices) = dmrsSymbols;
                txWav = nrOFDMModulate(carrier, txGrid);

                % Channel
                chInfo = info(channel);
                maxDelay = ceil(max(chInfo.PathDelays * channel.SampleRate)) + chInfo.ChannelFilterDelay;
                txWav = [txWav; zeros(maxDelay, nTxAnts)];
                [rxWav, pathGains, sampleTimes] = channel(txWav);

                % Noise
                SNR = 10^(snrdB/20);
                N0 = 1 / (sqrt(2.0 * nRxAnts * double(ofdmInfo.Nfft)) * SNR);
                noise = N0 * complex(randn(size(rxWav)), randn(size(rxWav)));
                rxWav = rxWav + noise;

                % Timing
                pathFilters = getPathFilters(channel);
                offset = nrPerfectTimingEstimate(pathGains, pathFilters);
                rxWav = rxWav(1+offset:end, :);

                % Demod
                rxGrid = nrOFDMDemodulate(carrier, rxWav);

                % Channel estimation
                [hest, nVar] = nrChannelEstimate(carrier, rxGrid, dmrsIndices, dmrsSymbols);

                % Equalize
                [pdschRx, pdschHest] = nrExtractResources(pdschIndices, rxGrid, hest);
                [pdschEq, csi] = nrEqualizeMMSE(pdschRx, pdschHest, nVar);

                % Decode PDSCH
                [dlschLLRs, rxSym] = nrPDSCHDecode(carrier, pdsch, pdschEq, nVar);

                % CSI scaling
                csi = nrLayerDemap(csi);
                Qm = length(dlschLLRs{1}) / length(rxSym{1});
                csi{1} = repmat(csi{1}(:,1), 1, Qm);
                dlschLLRs{1} = dlschLLRs{1} .* csi{1}(:);

                % Decode DL-SCH
                decDL.TransportBlockLength = tbs;
                [~, crcFlag] = decDL(dlschLLRs, pdsch.Modulation, pdsch.NumLayers, 0);

                nTotal = nTotal + 1;
                if crcFlag ~= 0
                    nErrors = nErrors + 1;
                end
                tBits = tBits + tbs;

                % ── CQI Feedback: measure effective SINR for next slot ──
                hestPower = mean(abs(hest(:)).^2);
                if nVar > 0
                    effectiveSinr = 10 * log10(hestPower / nVar);
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
        end

        rawBler = nErrors / nTotal;
        
        % Real-world 5G URLLC targets 99.999% reliability (10^-5 BLER)
        urllcTargetBler = 1e-5; 
        bler = max(rawBler, urllcTargetBler);

        bwScale = (273 / numUsers) / 51;
        simDur = nFrames * 10e-3;
        tput = (tBits * (1 - rawBler)) / simDur / 1e6 * bwScale;

        avgReTx = min(bler / (1 - bler + 1e-9), 4);
        lat = baseLat + (numUsers * 0.5) + avgReTx * harqRTT + backhaul;
        jit = 0.1 + (numUsers * 0.05) + bler * harqRTT;

        results(si, :) = [double(snrdB), double(bler), double(tput), double(lat), double(jit)];
        fprintf('5G NR | SNR=%2d dB | CQI=%2d | Mod=%s | BLER=%.5f | Tput=%8.2f Mbps\n', ...
            snrdB, currentCqi, pdsch.Modulation, bler, tput);
    end

    fprintf('=== 5G NR Simulation Complete ===\n\n');
end
