import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { Waveform } from './components/Waveform';
import { FFTSpectrum } from './components/FFTSpectrum';

function App() {
    const { data, connected, logs, sendMessage } = useWebSocket('ws://localhost:8000/ws');

    const [uiAlgo, setUiAlgo] = useState('POS');
    const [minHz, setMinHz] = useState(0.75);
    const [maxHz, setMaxHz] = useState(3.0);
    const [chromMode, setChromMode] = useState('AUTO');
    const [chromAlpha, setChromAlpha] = useState(1.0);
    const [evm, setEvm] = useState(false);
    const [showRawSpectrum, setShowRawSpectrum] = useState(false);

    // Sync UI state from backend config when it first arrives or changes (optional, but good for stability)
    useEffect(() => {
        if (data?.config) {
            setUiAlgo(data.config.algorithm);
            setMinHz(data.config.min_hz);
            setMaxHz(data.config.max_hz);
            setChromMode(data.config.chrom_alpha_mode);
            setChromAlpha(data.config.chrom_alpha);
            setEvm(data.config.evm);
        }
    }, [data?.config?.algorithm, data?.config?.min_hz, data?.config?.max_hz, data?.config?.chrom_alpha_mode, data?.config?.chrom_alpha, data?.config?.evm]);

    const formatTime = () => new Date().toLocaleTimeString('en-US', { hour12: false });

    const sendConfigUpdate = (updates: any) => {
        sendMessage({
            type: 'set_processing',
            ...updates
        });
    };

    const handleBandpassReset = () => {
        sendConfigUpdate({ bandpass: { low: 0.75, high: 3.0 } });
    };

    const handleChromReset = () => {
        sendConfigUpdate({ chrom: { alphaMode: 'AUTO', alpha: 1.0 } });
    };

    const handleLighting = (mode: string, color: string) => {
        if (mode === 'OFF') {
            sendMessage({ type: 'lighting', action: 'off' });
        } else {
            sendMessage({ type: 'lighting', action: 'on', mode, color });
        }
    };

    const handleMeasurement = (action: string) => {
        sendMessage({ type: 'measurement', action });
    };

    const renderCard = (title: string, res: any) => {
        if (!res || !res.available) return (
            <div className="border border-[#1a4a1a] p-2 bg-[#050f05]">
                <h3 className="text-[#005c18] font-bold">{title}</h3>
                <div className="text-xl text-[#005c18]">-- BPM</div>
            </div>
        );
        return (
            <div className="border border-[#1a4a1a] p-2 bg-[#050f05]">
                <h3 className="text-[#39ff14] font-bold">{title}</h3>
                <div className="text-2xl font-bold text-[#39ff14]">{res.bpm.toFixed(1)} <span className="text-sm">BPM</span></div>
                <div className="text-xs">SNR: {res.snrDb.toFixed(1)} dB</div>
                <div className="text-xs">Conf: {(res.confidence * 100).toFixed(1)}%</div>
            </div>
        );
    };

    const activeResult = data?.results ? (uiAlgo === 'ALL' ? (data.results as any)['POS'] : (data.results as any)[uiAlgo]) : null;

    return (
        <div className={`min-h-screen ${data?.lighting?.mode === 'SCREEN' && data?.lighting?.state === 'MEASURING' ? (data.lighting.color === 'GREEN' ? 'bg-[#00ff00]' : 'bg-white') : 'bg-[#0a0a0a]'} text-[#00ff41] p-4 font-mono transition-colors duration-200`}>
            {/* Header */}
            <div className="border border-[#1a4a1a] p-2 mb-4 flex justify-between items-center bg-[#0a0a0a]">
                <div className="font-bold">CAMERAHEART v2.0.0 — EXPERIMENTAL PLATFORM</div>
                <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${connected ? 'bg-[#39ff14] animate-pulse' : 'bg-red-500'}`}></span>
                    <span>{connected ? 'LIVE' : 'OFFLINE'}</span>
                </div>
                <div>{formatTime()}</div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 bg-[#0a0a0a]">
                
                {/* Left Column - Controls & Diagnostics */}
                <div className="lg:col-span-1 flex flex-col gap-4">
                    
                    {/* Experiment Control Panel */}
                    <div className="border border-[#1a4a1a] p-2">
                        <h2 className="mb-2 border-b border-[#1a4a1a] pb-1 font-bold">EXPERIMENT CONTROL</h2>
                        
                        {/* Algorithm Selector */}
                        <div className="mb-4">
                            <div className="text-xs text-[#005c18] mb-1">ALGORITHM</div>
                            <div className="flex flex-wrap gap-2">
                                {['GREEN', 'CHROM', 'POS', 'ALL'].map(alg => (
                                    <button 
                                        key={alg}
                                        onClick={() => sendConfigUpdate({ algorithm: alg })}
                                        className={`px-2 py-1 text-sm border ${uiAlgo === alg ? 'border-[#39ff14] text-[#39ff14] bg-[#1a4a1a]' : 'border-[#1a4a1a] text-[#005c18] hover:border-[#00ff41]'}`}
                                    >
                                        {alg}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Bandpass Control */}
                        <div className="mb-4">
                            <div className="text-xs text-[#005c18] mb-1 flex justify-between">
                                <span>BANDPASS (Hz)</span>
                                <span>{(minHz * 60).toFixed(0)} - {(maxHz * 60).toFixed(0)} BPM</span>
                            </div>
                            <div className="flex gap-2 items-center mb-1">
                                <input type="number" step="0.1" value={minHz} onChange={(e) => sendConfigUpdate({ bandpass: { low: parseFloat(e.target.value), high: maxHz } })} className="w-16 bg-black border border-[#1a4a1a] text-center text-sm" />
                                <span>-</span>
                                <input type="number" step="0.1" value={maxHz} onChange={(e) => sendConfigUpdate({ bandpass: { low: minHz, high: parseFloat(e.target.value) } })} className="w-16 bg-black border border-[#1a4a1a] text-center text-sm" />
                            </div>
                            <button onClick={handleBandpassReset} className="text-xs border border-[#1a4a1a] px-2 py-1 hover:border-[#00ff41]">RESET BANDPASS</button>
                        </div>

                        {/* CHROM Control */}
                        <div className="mb-4">
                            <div className="text-xs text-[#005c18] mb-1">CHROM ALPHA</div>
                            <div className="flex gap-2 mb-1">
                                <button onClick={() => sendConfigUpdate({ chrom: { alphaMode: 'AUTO', alpha: chromAlpha } })} className={`text-xs px-2 py-1 border ${chromMode === 'AUTO' ? 'border-[#39ff14] text-[#39ff14]' : 'border-[#1a4a1a] text-[#005c18]'}`}>AUTO</button>
                                <button onClick={() => sendConfigUpdate({ chrom: { alphaMode: 'MANUAL', alpha: chromAlpha } })} className={`text-xs px-2 py-1 border ${chromMode === 'MANUAL' ? 'border-[#39ff14] text-[#39ff14]' : 'border-[#1a4a1a] text-[#005c18]'}`}>MANUAL</button>
                            </div>
                            <div className="flex gap-2 items-center mb-1">
                                <input 
                                    type="number" step="0.05" value={chromAlpha.toFixed(2)} 
                                    onChange={(e) => sendConfigUpdate({ chrom: { alphaMode: 'MANUAL', alpha: parseFloat(e.target.value) } })} 
                                    disabled={chromMode === 'AUTO'}
                                    className="w-20 bg-black border border-[#1a4a1a] text-center text-sm disabled:opacity-50" 
                                />
                            </div>
                            <button onClick={handleChromReset} className="text-xs border border-[#1a4a1a] px-2 py-1 hover:border-[#00ff41]">RESET CHROM</button>
                        </div>

                        {/* EVM */}
                        <div className="mb-4 flex items-center justify-between border-t border-[#1a4a1a] pt-2">
                            <div className="text-xs">EVM PREVIEW</div>
                            <button onClick={() => sendConfigUpdate({ evm: !evm })} className={`text-xs px-2 py-1 border ${evm ? 'border-[#39ff14] text-[#39ff14]' : 'border-[#1a4a1a] text-[#005c18]'}`}>
                                {evm ? 'ON' : 'OFF'}
                            </button>
                        </div>

                        {/* Illumination */}
                        <div className="mb-2 border-t border-[#1a4a1a] pt-2">
                            <div className="text-xs text-[#005c18] mb-1 flex justify-between">
                                <span>ILLUMINATION</span>
                                <span className={data?.lighting?.state === 'MEASURING' ? 'text-[#39ff14]' : 'text-yellow-500'}>{data?.lighting?.state}</span>
                            </div>
                            <div className="flex flex-wrap gap-2 mb-2">
                                <button onClick={() => handleLighting('OFF', 'WHITE')} className={`text-xs px-2 py-1 border ${data?.lighting?.mode === 'OFF' ? 'border-[#39ff14]' : 'border-[#1a4a1a]'}`}>OFF</button>
                                <button onClick={() => handleLighting('SCREEN', 'WHITE')} className={`text-xs px-2 py-1 border ${data?.lighting?.mode === 'SCREEN' && data?.lighting?.color === 'WHITE' ? 'border-white text-white' : 'border-[#1a4a1a]'}`}>WHITE</button>
                                <button onClick={() => handleLighting('SCREEN', 'GREEN')} className={`text-xs px-2 py-1 border ${data?.lighting?.mode === 'SCREEN' && data?.lighting?.color === 'GREEN' ? 'border-[#39ff14]' : 'border-[#1a4a1a]'}`}>GREEN</button>
                            </div>
                            
                            <div className="flex gap-2">
                                <button onClick={() => handleMeasurement('start')} className={`w-full py-2 border font-bold ${data?.measurement_active ? 'border-[#39ff14] bg-[#1a4a1a]' : 'border-[#1a4a1a] hover:border-[#00ff41]'}`}>
                                    {data?.measurement_active ? 'MEASURING...' : 'START MEASUREMENT'}
                                </button>
                                <button onClick={() => handleMeasurement('stop')} className="px-2 py-2 border border-red-900 text-red-500 hover:bg-red-900/30">STOP</button>
                            </div>
                        </div>

                    </div>

                    {/* Camera Diagnostics Panel */}
                    <div className="border border-[#1a4a1a] p-2 text-xs">
                        <h2 className="mb-2 border-b border-[#1a4a1a] pb-1 font-bold">CAMERA DIAGNOSTICS</h2>
                        <div className="grid grid-cols-2 gap-1 text-[#005c18]">
                            <div>FPS: <span className="text-[#00ff41]">{data?.diagnostics?.fps?.toFixed(1) || '--'}</span></div>
                            <div>Gain: <span className="text-[#00ff41]">{data?.diagnostics?.gain !== -1 ? data?.diagnostics?.gain : 'UNSUP'}</span></div>
                            <div>AutoExp: <span className="text-[#00ff41]">{data?.diagnostics?.auto_exposure}</span></div>
                            <div>Exp: <span className="text-[#00ff41]">{data?.diagnostics?.exposure}</span></div>
                            <div>AutoAF: <span className="text-[#00ff41]">{data?.diagnostics?.auto_focus}</span></div>
                            <div>Focus: <span className="text-[#00ff41]">{data?.diagnostics?.focus}</span></div>
                            <div>AutoWB: <span className="text-[#00ff41]">{data?.diagnostics?.auto_wb}</span></div>
                            <div>WB: <span className="text-[#00ff41]">{data?.diagnostics?.white_balance}</span></div>
                        </div>
                    </div>

                </div>

                {/* Right Column */}
                <div className="lg:col-span-3 flex flex-col gap-4">
                    
                    {/* Header display */}
                    <div className="border border-[#1a4a1a] p-4 flex flex-col md:flex-row justify-between items-center bg-[#050f05]">
                        <div>
                            <h2 className="text-xl mb-1 text-[#005c18]">♥ HEART RATE {uiAlgo !== 'ALL' && `(${uiAlgo})`}</h2>
                            <div className="text-6xl font-bold text-[#39ff14]">
                                {data?.is_ready && activeResult?.available ? activeResult.bpm.toFixed(1) : '--'} <span className="text-2xl text-[#00ff41]">BPM</span>
                            </div>
                            {!data?.is_ready && data?.face_detected && data?.measurement_active && (
                                <div className="text-xs text-[#005c18] mt-1">
                                    Buffering signal... {Math.round((data?.progress || 0) * 100)}%
                                </div>
                            )}
                        </div>
                        
                        {uiAlgo === 'ALL' && data?.results ? (
                            <div className="flex gap-2 mt-4 md:mt-0">
                                {renderCard('GREEN', data.results.GREEN)}
                                {renderCard('CHROM', data.results.CHROM)}
                                {renderCard('POS', data.results.POS)}
                            </div>
                        ) : (
                            <div className="text-right flex flex-col gap-1 mt-4 md:mt-0">
                                <div>
                                    Confidence: <span className="text-[#39ff14]">{((activeResult?.confidence || 0) * 100).toFixed(1)}%</span>
                                </div>
                                <div>
                                    Status: <span className={data?.is_ready ? (activeResult && activeResult.confidence > 0.6 ? 'text-[#39ff14]' : 'text-yellow-500') : 'text-[#005c18]'}>
                                        {data?.is_ready ? (activeResult && activeResult.confidence > 0.6 ? 'STABLE' : 'UNSTABLE') : (data?.face_detected ? 'BUFFERING' : 'LOST')}
                                    </span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Waveform */}
                        <div className="border border-[#1a4a1a] p-2 h-48">
                            <h2 className="mb-2 border-b border-[#1a4a1a] pb-1 flex justify-between">
                                <span>rPPG WAVEFORM — {uiAlgo === 'ALL' ? 'POS' : uiAlgo}</span>
                                <span className="text-[#005c18]">time (window)</span>
                            </h2>
                            <div className="h-32">
                                <Waveform data={activeResult?.signal || []} />
                            </div>
                        </div>

                        {/* Spectrum */}
                        <div className="border border-[#1a4a1a] p-2 h-48">
                            <h2 className="mb-2 border-b border-[#1a4a1a] pb-1 flex justify-between items-center">
                                <span>FFT SPECTRUM — {uiAlgo === 'ALL' ? 'POS' : uiAlgo}</span>
                                <div className="flex items-center gap-2">
                                    <button onClick={() => setShowRawSpectrum(!showRawSpectrum)} className={`text-xs px-1 border ${showRawSpectrum ? 'border-[#39ff14] text-[#39ff14]' : 'border-[#1a4a1a] text-[#005c18]'}`}>
                                        RAW
                                    </button>
                                    <span className="text-[#005c18]">{showRawSpectrum ? `0 - ${((data?.diagnostics?.fps || 30) / 2).toFixed(1)}Hz` : `${minHz} - ${maxHz}Hz`}</span>
                                </div>
                            </h2>
                            <div className="h-32">
                                <FFTSpectrum spectrum={showRawSpectrum ? (activeResult as any)?.raw_spectrum || [] : activeResult?.spectrum || []} />
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Camera Feeds */}
                        <div className="border border-[#1a4a1a] p-2 flex gap-2">
                            <div className="w-1/2 aspect-video bg-black relative flex items-center justify-center">
                                {data?.frame_original ? (
                                    <img src={data.frame_original} alt="Raw" className="w-full h-full object-cover" />
                                ) : <span className="text-xs text-[#005c18]">NO SIGNAL</span>}
                                <div className="absolute top-1 left-1 bg-black/50 px-1 text-xs">RAW</div>
                            </div>
                            <div className="w-1/2 aspect-video bg-black relative flex items-center justify-center">
                                {evm && data?.frame_amplified ? (
                                    <img src={data.frame_amplified} alt="EVM" className="w-full h-full object-cover" />
                                ) : <span className="text-xs text-[#005c18]">EVM OFF</span>}
                                <div className="absolute top-1 left-1 bg-black/50 px-1 text-xs">AMPLIFIED</div>
                            </div>
                        </div>

                        {/* Terminal Log */}
                        <div className="border border-[#1a4a1a] p-2 h-full min-h-32 overflow-y-auto flex flex-col-reverse text-xs">
                            <div className="flex flex-col">
                                {logs.map((log, i) => (
                                    <div key={i}>{log}</div>
                                ))}
                                <div className="animate-pulse">_</div>
                            </div>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    );
}

export default App;
