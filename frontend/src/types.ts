export interface AlgorithmResult {
    available: boolean;
    bpm: number;
    peakHz: number;
    snrDb: number;
    confidence: number;
    signal: number[];
    spectrum: {freq: number, mag: number}[];
}

export interface rPPGState {
    face_detected: boolean;
    rois: number[][]; // [x, y, w, h]
    avg_green: number;
    is_ready: boolean;
    progress: number;
    
    config: {
        algorithm: string;
        min_hz: number;
        max_hz: number;
        chrom_alpha_mode: string;
        chrom_alpha: number;
        evm: boolean;
    };
    
    lighting: {
        mode: string;
        color: string;
        state: string;
    };
    
    measurement_active: boolean;
    
    diagnostics: {
        fps: number;
        auto_exposure: number;
        exposure: number;
        auto_focus: number;
        focus: number;
        auto_wb: number;
        white_balance: number;
        gain: number;
    };
    
    results: {
        GREEN: AlgorithmResult;
        CHROM: AlgorithmResult;
        POS: AlgorithmResult;
    } | null;

    frame_original: string | null;
    frame_amplified: string | null;
}
