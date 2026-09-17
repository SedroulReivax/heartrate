import { useWebSocket } from './hooks/useWebSocket';
import { Waveform } from './components/Waveform';
import { FFTSpectrum } from './components/FFTSpectrum';

function App() {
    const { data, connected, logs } = useWebSocket('ws://localhost:8000/ws');

    const formatTime = () => new Date().toLocaleTimeString('en-US', { hour12: false });

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-[#00ff41] p-4 font-mono">
            {/* Header */}
            <div className="border border-[#1a4a1a] p-2 mb-4 flex justify-between items-center">
                <div className="font-bold">CAMERAHEART v1.0.0</div>
                <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${connected ? 'bg-[#39ff14] animate-pulse' : 'bg-red-500'}`}></span>
                    <span>{connected ? 'LIVE' : 'OFFLINE'}</span>
                </div>
                <div>{formatTime()}</div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                
                {/* Left Column */}
                <div className="lg:col-span-1 flex flex-col gap-4">
                    {/* Camera Feed Comparison */}
                    <div className="border border-[#1a4a1a] p-2">
                        <h2 className="mb-2 border-b border-[#1a4a1a] pb-1">CAMERA FEEDS (ORIGINAL vs EVM)</h2>
                        <div className="flex flex-col gap-2">
                            <div className="aspect-video bg-black flex items-center justify-center relative overflow-hidden">
                                {data?.frame_original ? (
                                    <img src={data.frame_original} alt="Original Feed" className="w-full h-full object-cover grayscale sepia hue-rotate-50 saturate-200" />
                                ) : (
                                    <div className="text-[#005c18]">WAITING FOR SIGNAL...</div>
                                )}
                                <div className="absolute top-1 left-1 bg-black/50 px-1 text-xs">RAW</div>
                            </div>
                            <div className="aspect-video bg-black flex items-center justify-center relative overflow-hidden">
                                {data?.frame_amplified ? (
                                    <img src={data.frame_amplified} alt="EVM Amplified Feed" className="w-full h-full object-cover" />
                                ) : (
                                    <div className="text-[#005c18]">WAITING FOR SIGNAL...</div>
                                )}
                                <div className="absolute top-1 left-1 bg-black/50 px-1 text-xs">AMPLIFIED</div>
                            </div>
                        </div>
                        <p className="text-xs text-[#00ff41] mt-2 animate-pulse">
                            ALIGN YOUR FACE WITH THE GREEN BOXES
                        </p>
                        <p className="text-xs text-[#005c18] mt-1">
                            Tracking: forehead + upper cheek regions. The amplified feed isolates and enhances subtle green color variations caused by blood flow.
                        </p>
                    </div>

                    {/* Pipeline Status */}
                    <div className="border border-[#1a4a1a] p-2 flex-grow">
                        <h2 className="mb-2 border-b border-[#1a4a1a] pb-1">PIPELINE STATUS</h2>
                        <ul className="text-sm space-y-2 mt-2">
                            <li className={data?.face_detected ? 'text-[#00ff41]' : 'text-[#005c18]'}>
                                [{data?.face_detected ? '✓' : ' '}] 01. STATIC ROI LOCKED
                            </li>
                            <li className={data?.face_detected ? 'text-[#00ff41]' : 'text-[#005c18]'}>
                                [{data?.face_detected ? '✓' : ' '}] 02. EVM SPATIAL BLUR & DOWN-SAMPLING
                            </li>
                            <li className={data?.face_detected ? 'text-[#00ff41]' : 'text-[#005c18]'}>
                                [{data?.face_detected ? '✓' : ' '}] 03. TEMPORAL BUFFERING
                            </li>
                            <li className={data?.is_ready ? 'text-[#00ff41]' : 'text-[#005c18]'}>
                                [{data?.is_ready ? '✓' : ' '}] 04. IIR BANDPASS FILTER & SIGNAL AMPLIFICATION
                            </li>
                            <li className={data?.bpm && data.bpm > 0 ? 'text-[#00ff41]' : 'text-[#005c18]'}>
                                [{data?.bpm && data.bpm > 0 ? '✓' : ' '}] 05. FFT PEAK EXTRACTION
                            </li>
                        </ul>
                        
                        {!data?.is_ready && data?.face_detected && (
                            <div className="mt-4">
                                <div className="flex justify-between text-[#00ff41]">
                                    <span>Buffering signal...</span>
                                    <span>{Math.round((data?.progress || 0) * 100)}%</span>
                                </div>
                                <div className="text-xs text-[#005c18]">We need ~10s of data to build a meaningful waveform.</div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Column */}
                <div className="lg:col-span-2 flex flex-col gap-4">
                    {/* Heart Rate Display */}
                    <div className="border border-[#1a4a1a] p-4 flex justify-between items-center bg-[#050f05]">
                        <div>
                            <h2 className="text-xl mb-1 text-[#005c18]">♥ HEART RATE</h2>
                            <div className="text-6xl font-bold text-[#39ff14]">
                                {data?.is_ready ? data.bpm : '--'} <span className="text-2xl text-[#00ff41]">BPM</span>
                            </div>
                        </div>
                        <div className="text-right flex flex-col gap-1">
                            <div>
                                Confidence: <span className="text-[#39ff14]">{data?.confidence.toFixed(1) || 0}%</span>
                            </div>
                            <div>
                                Status: <span className={data?.is_ready ? (data.confidence > 60 ? 'text-[#39ff14]' : 'text-yellow-500') : 'text-[#005c18]'}>
                                    {data?.is_ready ? (data.confidence > 60 ? 'STABLE' : 'UNSTABLE') : (data?.face_detected ? 'BUFFERING' : 'LOST')}
                                </span>
                            </div>
                        </div>
                    </div>

                    {/* Waveform */}
                    <div className="border border-[#1a4a1a] p-2 h-48">
                        <h2 className="mb-2 border-b border-[#1a4a1a] pb-1 flex justify-between">
                            <span>rPPG WAVEFORM — GREEN CHANNEL</span>
                            <span className="text-[#005c18]">time (10s window)</span>
                        </h2>
                        <div className="h-32">
                            <Waveform data={data?.signal || []} />
                        </div>
                    </div>

                    {/* Spectrum */}
                    <div className="border border-[#1a4a1a] p-2 h-48">
                        <h2 className="mb-2 border-b border-[#1a4a1a] pb-1 flex justify-between">
                            <span>FFT SPECTRUM — FREQUENCY DOMAIN</span>
                            <span className="text-[#005c18]">0.75Hz — 3.0Hz</span>
                        </h2>
                        <div className="h-32">
                            <FFTSpectrum spectrum={data?.spectrum || []} />
                        </div>
                    </div>

                    {/* Terminal Log */}
                    <div className="border border-[#1a4a1a] p-2 h-40 overflow-y-auto flex flex-col-reverse">
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
    );
}

export default App;
