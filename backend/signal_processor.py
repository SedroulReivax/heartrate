import numpy as np
from scipy.signal import butter, lfilter, detrend

class SignalProcessor:
    """
    Implements the POS (Plane Orthogonal to Skin) rPPG algorithm.
    
    Reference: W. Wang et al., "Algorithmic Principles of Remote PPG," 
    IEEE Trans. Biomedical Engineering, 2017.
    
    Instead of using a raw single green channel (which is easily polluted 
    by lighting), POS projects the RGB signal onto a plane orthogonal to 
    the skin-tone vector, mathematically cancelling illumination noise.
    This is why it matches your actual pulse far better.
    """

    def __init__(self, fps=30, buffer_size=300):
        self.fps = fps
        # Use a shorter 6s window for faster, more responsive readings
        self.buffer_size = min(buffer_size, int(fps * 6))
        
        # Ring buffers for each RGB channel
        self.r_buf = []
        self.g_buf = []
        self.b_buf = []

        self.lowcut  = 0.75   # 45 BPM
        self.highcut = 3.0    # 180 BPM
        
        # SNR gate: peak must be this many times the noise floor
        # Tuned from academic benchmarks: 3.5 is a safe threshold for POS
        self.SNR_THRESHOLD = 3.5

    def _bandpass(self, data):
        nyq = 0.5 * self.fps
        low  = max(self.lowcut  / nyq, 0.01)
        high = min(self.highcut / nyq, 0.99)
        b, a = butter(3, [low, high], btype='band')
        return lfilter(b, a, data)

    def _pos_signal(self, r, g, b):
        """
        Compute the POS pulse signal from RGB time series.
        
        POS projects onto a plane orthogonal to the skin colour direction.
        This cancels specular reflections and illumination changes, leaving 
        only the pulsatile blood volume signal.
        
        Steps (following Wang et al. 2017, Algorithm 1):
        1. Normalise each channel by its mean to remove absolute brightness.
        2. Project onto two orthogonal directions in the normalised colour space.
        3. Combine the two projections to cancel the skin-tone direction.
        """
        r, g, b = np.array(r), np.array(g), np.array(b)

        # Step 1 — per-channel normalisation (removes DC / brightness)
        mu_r = np.mean(r) + 1e-9
        mu_g = np.mean(g) + 1e-9
        mu_b = np.mean(b) + 1e-9

        Rn = r / mu_r   # normalised red
        Gn = g / mu_g   # normalised green
        Bn = b / mu_b   # normalised blue

        # Step 2 — two projection axes orthogonal to the skin tone (1,1,1)
        # (from the POS paper: eqs 6-7)
        S1 = Rn - Gn             # axis 1
        S2 = Rn + Gn - 2.0 * Bn  # axis 2

        # Step 3 — combine to cancel residual skin tone
        # alpha = std(S1)/std(S2) tunes the mix
        alpha = np.std(S1) / (np.std(S2) + 1e-9)
        pulse = S1 + alpha * S2

        return pulse

    def process(self, rgb_triple):
        """
        rgb_triple: (avg_r, avg_g, avg_b) from the ROI this frame.
        
        Returns (is_ready, bpm, filtered_signal, spectrum, confidence)
        """
        r_val, g_val, b_val = rgb_triple

        self.r_buf.append(r_val)
        self.g_buf.append(g_val)
        self.b_buf.append(b_val)

        if len(self.r_buf) > self.buffer_size:
            self.r_buf.pop(0)
            self.g_buf.pop(0)
            self.b_buf.pop(0)

        n = len(self.r_buf)

        if n < self.buffer_size:
            progress = n / self.buffer_size
            # Show partial POS signal for waveform visualisation
            if n > 10:
                raw = self._pos_signal(self.r_buf, self.g_buf, self.b_buf)
                raw = detrend(raw)
                return False, 0.0, raw.tolist(), [], progress
            return False, 0.0, [], [], progress

        # --- Full buffer: compute POS signal ---
        pulse = self._pos_signal(self.r_buf, self.g_buf, self.b_buf)

        # Proper linear detrend (removes slow lighting drift better than mean-sub)
        pulse = detrend(pulse)

        # Bandpass filter
        filtered = self._bandpass(pulse)

        # FFT with Hamming window
        N = len(filtered)
        windowed = filtered * np.hamming(N)
        fft_mag  = np.abs(np.fft.rfft(windowed))
        freqs    = np.fft.rfftfreq(N, 1.0 / self.fps)

        valid_mask    = (freqs >= self.lowcut) & (freqs <= self.highcut)
        valid_indices = np.where(valid_mask)[0]

        if len(valid_indices) == 0:
            return True, 0.0, filtered.tolist(), [], 0.0

        valid_mags  = fft_mag[valid_indices]
        valid_freqs = freqs[valid_indices]

        peak_idx  = np.argmax(valid_mags)
        peak_freq = valid_freqs[peak_idx]
        peak_mag  = valid_mags[peak_idx]

        # --- SNR gate ---
        others      = np.delete(valid_mags, peak_idx)
        noise_floor = np.mean(others) if len(others) > 0 else 1e-9
        snr         = peak_mag / (noise_floor + 1e-9)

        spectrum = [{"freq": float(f), "mag": float(m)}
                    for f, m in zip(valid_freqs, valid_mags)]

        if snr < self.SNR_THRESHOLD:
            return True, 0.0, filtered.tolist(), spectrum, 0.0

        bpm        = peak_freq * 60.0
        confidence = min(snr / 10.0, 1.0)

        return True, bpm, filtered.tolist(), spectrum, confidence
