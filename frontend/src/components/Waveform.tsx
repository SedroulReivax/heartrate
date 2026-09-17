import { useEffect, useRef } from 'react';

interface WaveformProps {
    data: number[];
}

export const Waveform = ({ data }: WaveformProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Clear canvas
        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (!data || data.length === 0) return;

        // Draw waveform
        ctx.strokeStyle = '#00ff41';
        ctx.lineWidth = 2;
        ctx.beginPath();

        const padding = 20;
        const width = canvas.width - padding * 2;
        const height = canvas.height - padding * 2;
        
        // Find min and max for scaling
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;

        const step = width / (data.length - 1);

        for (let i = 0; i < data.length; i++) {
            const x = padding + i * step;
            // Invert y so higher value goes up
            const normalized = (data[i] - min) / range;
            const y = padding + height - (normalized * height);
            
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }

        ctx.stroke();
    }, [data]);

    return (
        <canvas 
            ref={canvasRef} 
            width={800} 
            height={200} 
            className="w-full h-full object-contain"
        />
    );
};
