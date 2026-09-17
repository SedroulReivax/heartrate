import { useState, useEffect, useRef } from 'react';
import type { rPPGState } from '../types';

export const useWebSocket = (url: string) => {
    const [data, setData] = useState<rPPGState | null>(null);
    const [connected, setConnected] = useState(false);
    const wsRef = useRef<WebSocket | null>(null);
    const logRef = useRef<string[]>([]);
    const [logs, setLogs] = useState<string[]>([]);
    const lastBpmLogTime = useRef<number>(0);

    const addLog = (msg: string) => {
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
        const entry = `> [${time}] ${msg}`;
        logRef.current = [...logRef.current, entry].slice(-50); // keep last 50
        setLogs(logRef.current);
    };

    useEffect(() => {
        const connect = () => {
            addLog(`Connecting to ${url}...`);
            const ws = new WebSocket(url);
            
            ws.onopen = () => {
                setConnected(true);
                addLog('WebSocket connected');
            };
            
            ws.onmessage = (event) => {
                try {
                    const state = JSON.parse(event.data) as rPPGState;
                    setData(state);
                } catch (e) {
                    console.error("Error parsing message", e);
                }
            };
            
            ws.onclose = () => {
                setConnected(false);
                addLog('WebSocket disconnected. Reconnecting in 2s...');
                setTimeout(connect, 2000);
            };
            
            wsRef.current = ws;
        };
        
        connect();
        
        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [url]);

    const prevDataRef = useRef<rPPGState | null>(null);
    
    useEffect(() => {
        if (!data) return;
        const prev = prevDataRef.current;
        
        if (!prev?.face_detected && data.face_detected) {
            addLog('Face detected. ROI locked.');
        } else if (prev?.face_detected && !data.face_detected) {
            addLog('Face lost. Resetting buffer.');
        }
        
        if (!prev?.is_ready && data.is_ready) {
            addLog('Signal buffer full. First BPM computed.');
        }
        
        if (data.is_ready && data.bpm > 0) {
            const now = Date.now();
            if (now - lastBpmLogTime.current > 2000) {
                addLog(`BPM: ${data.bpm.toFixed(1)} | Confidence: ${data.confidence.toFixed(1)}%`);
                lastBpmLogTime.current = now;
            }
        }
        
        prevDataRef.current = data;
    }, [data]);

    return { data, connected, logs, addLog };
};
