function results = simulate_5g_link()
%SIMULATE_5G_LINK 5G NR PDSCH link-level simulation over TDL-A channel
%   Returns Nx5 matrix: [SNR_dB, BLER, Throughput_Mbps, Latency_ms, Jitter_ms]

    fprintf('\n=== Starting 5G NR Link-Level Simulation ===\n');

    snrRange = 0:5:30;

    %% Carrier
    carrier = nrCarrierConfig;
    carrier.NSizeGrid = 51;
    carrier.SubcarrierSpacing = 30;
    carrier.CyclicPrefix = 'Normal';
    carrier.NCellID = 1;

    %% PDSCH - single layer to keep things clean
    pdsch = nrPDSCHConfig;
    pdsch.MappingType = 'A';
    pdsch.SymbolAllocation = [0 14];
    pdsch.PRBSet = 0:carrier.NSizeGrid-1;
    pdsch.Modulation = '16QAM';
    pdsch.NumLayers = 1;
    pdsch.NID = carrier.NCellID;
    pdsch.RNTI = 1;
    pdsch.DMRS.DMRSConfigurationType = 1;
    pdsch.DMRS.DMRSLength = 1;
    pdsch.DMRS.DMRSAdditionalPosition = 1;
    pdsch.DMRS.NumCDMGroupsWithoutData = 2;
    pdsch.DMRS.DMRSPortSet = 0;

    %% TBS
    targetCodeRate = 0.5;
    [pdschIndices, pdschInfo] = nrPDSCHIndices(carrier, pdsch);
    tbs = nrTBS(pdsch.Modulation, pdsch.NumLayers, ...
        numel(pdsch.PRBSet), pdschInfo.NREPerPRB, targetCodeRate);
    fprintf('TBS: %d bits, G: %d\n', tbs, pdschInfo.G);

    %% Encoder / Decoder
    encDL = nrDLSCH;
    encDL.MultipleHARQProcesses = false;
    encDL.TargetCodeRate = targetCodeRate;

    decDL = nrDLSCHDecoder;
    decDL.MultipleHARQProcesses = false;
    decDL.TargetCodeRate = targetCodeRate;
    decDL.TransportBlockLength = tbs;
    decDL.LDPCDecodingAlgorithm = 'Normalized min-sum';

    %% Channel - TDL-A urban NLOS
    nTxAnts = 1;
    nRxAnts = 2;
    channel = nrTDLChannel;
    channel.DelayProfile = 'TDL-A';
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

        reset(channel);
        reset(encDL);
        reset(decDL);

        for fr = 1:nFrames
            for sl = 0:carrier.SlotsPerFrame-1
                carrier.NSlot = sl;

                [pdschIndices, pdschInfo] = nrPDSCHIndices(carrier, pdsch);
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
            end
        end

        rawBler = nErrors / nTotal;
        
        % Real-world 5G URLLC targets 99.999% reliability (10^-5 BLER)
        % It sacrifices max throughput to maintain this ultra-low error floor.
        urllcTargetBler = 1e-5; 
        bler = max(rawBler, urllcTargetBler);

        bwScale = 273 / 51;
        simDur = nFrames * 10e-3;
        tput = (tBits * (1 - rawBler)) / simDur / 1e6 * bwScale;

        avgReTx = min(bler / (1 - bler + 1e-9), 4);
        lat = baseLat + avgReTx * harqRTT + backhaul;
        jit = 0.1 + bler * harqRTT;

        results(si, :) = [double(snrdB), double(bler), double(tput), double(lat), double(jit)];
        fprintf('5G NR | SNR=%2d dB | BLER=%.5f | Tput=%8.2f Mbps | Lat=%.2f ms\n', ...
            snrdB, bler, tput, lat);
    end

    fprintf('=== 5G NR Simulation Complete ===\n\n');
end
