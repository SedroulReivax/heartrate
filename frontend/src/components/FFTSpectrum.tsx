import { useEffect, useRef } from 'react';

interface FFTSpectrumProps {
    spectrum: {freq: number, mag: number}[];
}

export const FFTSpectrum = ({ spectrum }: FFTSpectrumProps) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (!spectrum || spectrum.length === 0) return;

        const paddingX = 40;
        const paddingY = 20;
        const width = canvas.width - paddingX * 2;
        const height = canvas.height - paddingY * 2;

        const maxMag = Math.max(...spectrum.map(s => s.mag)) || 1;
        const barWidth = width / spectrum.length;

        ctx.fillStyle = '#00ff41';

        spectrum.forEach((s, i) => {
            const barHeight = (s.mag / maxMag) * height;
            const x = paddingX + i * barWidth;
            const y = canvas.height - paddingY - barHeight;
            
            // Highlight the peak
            if (s.mag === maxMag && maxMag > 0) {
                ctx.fillStyle = '#39ff14'; // brighter green
                ctx.fillRect(x, y, barWidth - 1, barHeight);
                ctx.fillStyle = '#00ff41'; // restore
                
                // Draw frequency text
                ctx.fillStyle = '#39ff14';
                ctx.font = '12px monospace';
                ctx.fillText(`${s.freq.toFixed(2)}Hz`, x - 10, y - 5);
                ctx.fillStyle = '#00ff41';
            } else {
                ctx.fillRect(x, y, barWidth - 1, barHeight);
            }
        });

        // Draw axes
        ctx.strokeStyle = '#1a4a1a';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(paddingX, paddingY);
        ctx.lineTo(paddingX, canvas.height - paddingY);
        ctx.lineTo(canvas.width - paddingX, canvas.height - paddingY);
        ctx.stroke();

    }, [spectrum]);

    return (
        <canvas 
            ref={canvasRef} 
            width={400} 
            height={200} 
            className="w-full h-full object-contain"
        />
    );
};
