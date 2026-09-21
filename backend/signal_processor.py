import numpy as np
import scipy.signal as signal
from scipy.interpolate import interp1d

class ProcessingConfig:
    def __init__(self):
        self.algorithm = "POS"  # GREEN, CHROM, POS, ALL
        self.min_hz = 0.75
        self.max_hz = 3.0
        self.chrom_alpha_mode = "AUTO"  # AUTO, MANUAL
        self.chrom_alpha = 1.0

class SignalProcessor:
    def __init__(self, target_fps=30.0, buffer_seconds=6):
        self.target_fps = float(target_fps)
        self.buffer_size = int(self.target_fps * buffer_seconds)
        
        self.times = []
        self.r_buf = []
        self.g_buf = []
        self.b_buf = []

        self.SNR_THRESHOLD_DB = 2.0 

    def reset(self):
        self.times = []
        self.r_buf = []
        self.g_buf = []
        self.b_buf = []

    def _chrom_signal(self, r, g, b, config: ProcessingConfig):
        r, g, b = np.array(r), np.array(g), np.array(b)
        N = len(r)
        
        L = int(1.6 * self.target_fps)
        if N <= L:
            L = N
            
        H = np.zeros(N)
        
        for n in range(N - L + 1):
            rw = r[n:n+L]
            gw = g[n:n+L]
            bw = b[n:n+L]
            
            mu_r = np.mean(rw) + 1e-9
            mu_g = np.mean(gw) + 1e-9
            mu_b = np.mean(bw) + 1e-9

            Rn = rw / mu_r
            Gn = gw / mu_g
            Bn = bw / mu_b

            # CHROM (De Haan and Jeanne, 2013)
            # x_s = 3 * Rn - 2 * Gn
            # y_s = 1.5 * Rn + Gn - 1.5 * Bn
            X = 3 * Rn - 2 * Gn
            Y = 1.5 * Rn + Gn - 1.5 * Bn
            
            if config.chrom_alpha_mode == "AUTO":
                alpha = np.std(X) / (np.std(Y) + 1e-9)
            else:
                alpha = config.chrom_alpha
                
            pulse_window = X - alpha * Y
            
            pulse_window -= np.mean(pulse_window)
            H[n:n+L] += pulse_window
            
        return H

    def _pos_signal(self, r, g, b):
        r, g, b = np.array(r), np.array(g), np.array(b)
        N = len(r)
        
        L = int(1.6 * self.target_fps)
        if N <= L:
            L = N
            
        H = np.zeros(N)
        
        for n in range(N - L + 1):
            rw = r[n:n+L]
            gw = g[n:n+L]
            bw = b[n:n+L]
            
            mu_r = np.mean(rw) + 1e-9
            mu_g = np.mean(gw) + 1e-9
            mu_b = np.mean(bw) + 1e-9

            Rn = rw / mu_r
            Gn = gw / mu_g
            Bn = bw / mu_b

            S1 = Gn - Bn
            S2 = Gn + Bn - 2.0 * Rn

            alpha = np.std(S1) / (np.std(S2) + 1e-9)
            pulse_window = S1 + alpha * S2
            
            pulse_window -= np.mean(pulse_window)
            H[n:n+L] += pulse_window
            
        return H

    def _green_signal(self, g):
        g = np.array(g)
        mu_g = np.mean(g) + 1e-9
        Gn = g / mu_g
        # Normalize and zero-mean (inverted since absorption increases with pulse)
        # Using -Gn or just Gn. Usually we invert, so -Gn
        Gn = - (Gn - 1.0)
        return Gn

    def _extract_robust_bpm(self, rppg_signal, config: ProcessingConfig):
        N = len(rppg_signal)
        if N > 4:
            lam = 150.0 
            import scipy.sparse as sp
            from scipy.sparse.linalg import spsolve
            I = sp.eye(N, format='csc')
            D2 = sp.diags([1, -2, 1], [0, 1, 2], shape=(N - 2, N), format='csc')
            A = I + (lam ** 2) * (D2.T @ D2)
            trend = spsolve(A, rppg_signal)
            sig_detrended = rppg_signal - trend
        else:
            sig_detrended = signal.detrend(rppg_signal)
        
        nyq = 0.5 * self.target_fps
        b, a = signal.butter(3, [config.min_hz / nyq, config.max_hz / nyq], btype='bandpass')
        sig_filtered = signal.filtfilt(b, a, sig_detrended, padlen=min(len(sig_detrended)-1, 15))
        
        window = np.hanning(len(sig_filtered))
        sig_windowed = sig_filtered * window
        
        freqs, psd = signal.periodogram(sig_windowed, fs=self.target_fps, nfft=2048, window=None)
        
        valid_idx = np.where((freqs >= config.min_hz) & (freqs <= config.max_hz))[0]
        if len(valid_idx) == 0:
            return 0.0, 0.0, sig_filtered, freqs, psd, freqs, psd

        valid_freqs = freqs[valid_idx]
        valid_psd = psd[valid_idx]
        
        peaks, _ = signal.find_peaks(valid_psd)
        
        if len(peaks) == 0:
            best_freq = valid_freqs[np.argmax(valid_psd)]
            return best_freq * 60.0, 0.0, sig_filtered, valid_freqs, valid_psd, freqs, psd

        candidate_freqs = valid_freqs[peaks]
        
        best_snr_linear = -np.inf
        best_freq = None
        window_hz = 0.1
        
        p_total = np.sum(psd)
        
        for fc in candidate_freqs:
            mask_fundamental = (freqs >= (fc - window_hz)) & (freqs <= (fc + window_hz))
            mask_harmonic = (freqs >= (2*fc - window_hz)) & (freqs <= (2*fc + window_hz))
            
            signal_mask = mask_fundamental | mask_harmonic
            p_signal = np.sum(psd[signal_mask])
            
            p_noise = p_total - p_signal
            p_noise = max(p_noise, 1e-10)
                
            snr_linear = p_signal / p_noise
            if snr_linear > best_snr_linear:
                best_snr_linear = snr_linear
                best_freq = fc
                
        snr_db = 10 * np.log10(best_snr_linear) if best_snr_linear > 0 else 0
        bpm = best_freq * 60.0
        
        return bpm, snr_db, sig_filtered, valid_freqs, valid_psd, freqs, psd

    def _package_result(self, bpm, snr_db, sig_filtered, valid_freqs, valid_psd, freqs_full, psd_full):
        spectrum = [{"freq": float(f), "mag": float(m)} for f, m in zip(valid_freqs, valid_psd)]
        raw_spectrum = [{"freq": float(f), "mag": float(m)} for f, m in zip(freqs_full, psd_full)]
        
        if snr_db < self.SNR_THRESHOLD_DB:
            return {
                "available": True, "bpm": 0.0, "peakHz": float(bpm / 60.0), 
                "snrDb": float(snr_db), "confidence": 0.0,
                "signal": sig_filtered.tolist(), "spectrum": spectrum, "raw_spectrum": raw_spectrum
            }
        confidence = min(max((snr_db - self.SNR_THRESHOLD_DB) / 6.0, 0.0), 1.0)
        return {
            "available": True, "bpm": round(float(bpm), 1), "peakHz": float(bpm / 60.0), 
            "snrDb": float(snr_db), "confidence": float(confidence),
            "signal": sig_filtered.tolist(), "spectrum": spectrum, "raw_spectrum": raw_spectrum
        }

    def process(self, rgb_triple, timestamp, config: ProcessingConfig, compute_results=True):
        """
        rgb_triple: (r, g, b) floats or None if just reprocessing
        timestamp: time
        """
        if rgb_triple is not None and timestamp is not None:
            self.r_buf.append(rgb_triple[0])
            self.g_buf.append(rgb_triple[1])
            self.b_buf.append(rgb_triple[2])
            self.times.append(timestamp)

        target_duration = self.buffer_size / self.target_fps
        while len(self.times) > 1 and (self.times[-1] - self.times[0]) > target_duration:
            self.r_buf.pop(0)
            self.g_buf.pop(0)
            self.b_buf.pop(0)
            self.times.pop(0)

        duration = self.times[-1] - self.times[0] if len(self.times) > 0 else 0
        progress = min(duration / target_duration, 1.0)

        empty_res = {"available": False, "bpm": 0.0, "peakHz": 0.0, "snrDb": 0.0, "confidence": 0.0, "signal": [], "spectrum": []}

        if duration < target_duration * 0.95 or len(self.times) < 4:
            return False, progress, empty_res, empty_res, empty_res

        if not compute_results:
            return True, progress, empty_res, empty_res, empty_res

        t_start, t_end = self.times[0], self.times[-1]
        uniform_t = np.arange(t_start, t_end, 1.0 / self.target_fps)
        
        interpolator = interp1d(self.times, np.column_stack((self.r_buf, self.g_buf, self.b_buf)), axis=0, kind='linear')
        uniform_rgb = interpolator(uniform_t)

        r_res = empty_res
        c_res = empty_res
        p_res = empty_res

        algos_to_run = []
        if config.algorithm == "ALL":
            algos_to_run = ["GREEN", "CHROM", "POS"]
        else:
            algos_to_run = [config.algorithm]

        for algo in algos_to_run:
            if algo == "GREEN":
                pulse = self._green_signal(uniform_rgb[:, 1])
                bpm, snr_db, sig_filt, freqs, psd, freqs_full, psd_full = self._extract_robust_bpm(pulse, config)
                r_res = self._package_result(bpm, snr_db, sig_filt, freqs, psd, freqs_full, psd_full)
            elif algo == "CHROM":
                pulse = self._chrom_signal(uniform_rgb[:, 0], uniform_rgb[:, 1], uniform_rgb[:, 2], config)
                bpm, snr_db, sig_filt, freqs, psd, freqs_full, psd_full = self._extract_robust_bpm(pulse, config)
                c_res = self._package_result(bpm, snr_db, sig_filt, freqs, psd, freqs_full, psd_full)
            elif algo == "POS":
                pulse = self._pos_signal(uniform_rgb[:, 0], uniform_rgb[:, 1], uniform_rgb[:, 2])
                bpm, snr_db, sig_filt, freqs, psd, freqs_full, psd_full = self._extract_robust_bpm(pulse, config)
                p_res = self._package_result(bpm, snr_db, sig_filt, freqs, psd, freqs_full, psd_full)

        return True, progress, r_res, c_res, p_res
