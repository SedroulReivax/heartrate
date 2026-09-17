import numpy as np
import scipy.signal as signal
from scipy.interpolate import interp1d

class SignalProcessor:
    """
    Robust rPPG Signal Processor implementing SOTA practices:
    1. Cubic Spline Interpolation for exact 30Hz resampling (fixes webcam FPS jitter).
    2. POS (Plane Orthogonal to Skin) algorithm for lighting noise cancellation.
    3. Zero-phase filtering (filtfilt) to avoid time-domain edge artifacts.
    4. Zero-padded FFT with Hann window to prevent spectral leakage.
    5. De Haan's SNR peak selection (including harmonics) to avoid false BPM spikes.
    """

    def __init__(self, target_fps=30.0, buffer_seconds=6):
        self.target_fps = float(target_fps)
        self.buffer_size = int(self.target_fps * buffer_seconds)
        
        self.times = []
        self.r_buf = []
        self.g_buf = []
        self.b_buf = []

        self.min_hz = 0.75  # 45 BPM
        self.max_hz = 3.0   # 180 BPM
        
        self.SNR_THRESHOLD_DB = 2.0 # Minimum SNR in dB to report a confident BPM

    def _pos_signal(self, r, g, b):
        r, g, b = np.array(r), np.array(g), np.array(b)
        mu_r = np.mean(r) + 1e-9
        mu_g = np.mean(g) + 1e-9
        mu_b = np.mean(b) + 1e-9

        Rn = r / mu_r
        Gn = g / mu_g
        Bn = b / mu_b

        S1 = Rn - Gn
        S2 = Rn + Gn - 2.0 * Bn

        alpha = np.std(S1) / (np.std(S2) + 1e-9)
        pulse = S1 + alpha * S2
        return pulse

    def _extract_robust_bpm(self, rppg_signal):
        # 1. Detrend to remove slow physiological drift
        sig_detrended = signal.detrend(rppg_signal)
        
        # 2. Zero-phase Bandpass (no edge shift artifacts like lfilter)
        nyq = 0.5 * self.target_fps
        b, a = signal.butter(3, [self.min_hz / nyq, self.max_hz / nyq], btype='bandpass')
        # Use filtfilt (applies filter forward and backward to cancel phase delay)
        # padding bounds to prevent edge artifacts
        sig_filtered = signal.filtfilt(b, a, sig_detrended, padlen=min(len(sig_detrended)-1, 15))
        
        # 3. Apply Hann window to reduce spectral leakage
        window = np.hanning(len(sig_filtered))
        sig_windowed = sig_filtered * window
        
        # 4. Zero-padded Periodogram (nfft=2048 for smooth sub-Hz interpolation)
        freqs, psd = signal.periodogram(sig_windowed, fs=self.target_fps, nfft=2048, window=None)
        
        # 5. Isolate physiological range
        valid_idx = np.where((freqs >= self.min_hz) & (freqs <= self.max_hz))[0]
        if len(valid_idx) == 0:
            return 0.0, 0.0, sig_filtered, freqs, psd

        valid_freqs = freqs[valid_idx]
        valid_psd = psd[valid_idx]
        
        peaks, _ = signal.find_peaks(valid_psd)
        
        if len(peaks) == 0:
            best_freq = valid_freqs[np.argmax(valid_psd)]
            return best_freq * 60.0, 0.0, sig_filtered, valid_freqs, valid_psd

        candidate_freqs = valid_freqs[peaks]
        
        # 6. Evaluate De Haan SNR for each candidate peak (including its harmonic)
        best_snr_linear = -np.inf
        best_freq = None
        window_hz = 0.1 # +/- 0.1 Hz window around peak
        
        physio_mask = (freqs >= self.min_hz) & (freqs <= self.max_hz)
        p_total = np.sum(psd[physio_mask])
        
        for fc in candidate_freqs:
            mask_fundamental = (freqs >= (fc - window_hz)) & (freqs <= (fc + window_hz))
            mask_harmonic = (freqs >= (2*fc - window_hz)) & (freqs <= (2*fc + window_hz))
            
            signal_mask = mask_fundamental | mask_harmonic
            p_signal = np.sum(psd[signal_mask & physio_mask])
            
            p_noise = p_total - p_signal
            p_noise = max(p_noise, 1e-10)
                
            snr_linear = p_signal / p_noise
            if snr_linear > best_snr_linear:
                best_snr_linear = snr_linear
                best_freq = fc
                
        snr_db = 10 * np.log10(best_snr_linear) if best_snr_linear > 0 else 0
        bpm = best_freq * 60.0
        
        return bpm, snr_db, sig_filtered, valid_freqs, valid_psd

    def process(self, rgb_triple, timestamp):
        """
        rgb_triple: (r, g, b) floats
        timestamp: Exact arrival time in seconds (e.g. time.perf_counter())
        """
        self.r_buf.append(rgb_triple[0])
        self.g_buf.append(rgb_triple[1])
        self.b_buf.append(rgb_triple[2])
        self.times.append(timestamp)

        # We keep data by time, not strict frame count
        # Ensure we have at least 6 seconds of data
        while len(self.times) > 10 and (self.times[-1] - self.times[0]) > (self.buffer_size / self.target_fps) + 1.0:
            self.r_buf.pop(0)
            self.g_buf.pop(0)
            self.b_buf.pop(0)
            self.times.pop(0)

        duration = self.times[-1] - self.times[0] if len(self.times) > 0 else 0
        target_duration = self.buffer_size / self.target_fps

        if duration < target_duration * 0.95:
            progress = duration / target_duration
            return False, 0.0, [], [], progress

        # --- Interpolate to strict target_fps grid ---
        t_start, t_end = self.times[0], self.times[-1]
        uniform_t = np.arange(t_start, t_end, 1.0 / self.target_fps)
        
        # Need at least 4 points for cubic interpolation
        if len(self.times) < 4:
            return False, 0.0, [], [], 0.0

        try:
            interp_r = interp1d(self.times, self.r_buf, kind='cubic', fill_value='extrapolate')(uniform_t)
            interp_g = interp1d(self.times, self.g_buf, kind='cubic', fill_value='extrapolate')(uniform_t)
            interp_b = interp1d(self.times, self.b_buf, kind='cubic', fill_value='extrapolate')(uniform_t)
        except ValueError:
            # Fallback to linear if cubic fails (e.g., duplicate timestamps)
            interp_r = interp1d(self.times, self.r_buf, kind='linear', fill_value='extrapolate')(uniform_t)
            interp_g = interp1d(self.times, self.g_buf, kind='linear', fill_value='extrapolate')(uniform_t)
            interp_b = interp1d(self.times, self.b_buf, kind='linear', fill_value='extrapolate')(uniform_t)

        # Ensure we have enough interpolated points
        if len(uniform_t) < self.target_fps * 3:
            return False, 0.0, [], [], 1.0

        # Compute POS on strictly uniform grid
        pulse = self._pos_signal(interp_r, interp_g, interp_b)

        # Extract BPM robustly
        bpm, snr_db, sig_filtered, valid_freqs, valid_psd = self._extract_robust_bpm(pulse)

        spectrum = [{"freq": float(f), "mag": float(m)} for f, m in zip(valid_freqs, valid_psd)]

        if snr_db < self.SNR_THRESHOLD_DB:
            return True, 0.0, sig_filtered.tolist(), spectrum, 0.0

        # Confidence scaled roughly 0 to 1 based on SNR dB (2dB to ~8dB max)
        confidence = min(max((snr_db - self.SNR_THRESHOLD_DB) / 6.0, 0.0), 1.0)

        return True, bpm, sig_filtered.tolist(), spectrum, confidence
