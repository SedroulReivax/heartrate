export interface rPPGState {
    face_detected: boolean;
    rois: number[][]; // [x, y, w, h]
    avg_green: number;
    is_ready: boolean;
    progress: number;
    bpm: number;
    signal: number[];
    spectrum: {freq: number, mag: number}[];
    confidence: number;
    frame: string | null;
}
