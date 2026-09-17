import numpy as np
from scipy.signal import butter, lfilter

class SignalProcessor:
    def __init__(self, fps=30, buffer_size=300):
        self.fps = fps
        self.buffer_size = buffer_size
        self.signal_buffer = []

        # Bandpass filter parameters (0.75 Hz to 3.0 Hz = 45 to 180 BPM)
        self.lowcut = 0.75
        self.highcut = 3.0

        # SNR threshold — the peak must be this many times stronger than
        # the average noise floor to be considered a real heartbeat signal.
        # A flat/noisy signal (wall, random noise) will have SNR ~1.0.
        # A real pulse will have a clear dominant peak with SNR > 2.5
        self.SNR_THRESHOLD = 2.5

    def _butter_bandpass_filter(self, data):
        nyq = 0.5 * self.fps
        low = self.lowcut / nyq
        high = self.highcut / nyq
        b, a = butter(3, [low, high], btype='band')
        return lfilter(b, a, data)

    def process(self, new_value):
        """
        Adds a new value to the buffer and computes BPM if buffer is full.
        Returns:
            is_ready (bool): True if we have a confident, valid heartbeat signal
            bpm (float): Calculated BPM (0 if not ready or signal not confident)
            filtered_signal (list): The filtered signal for visualization
            spectrum (list): The FFT spectrum
            confidence (float 0-1): Progress while filling buffer, SNR confidence after
        """
        self.signal_buffer.append(new_value)

        if len(self.signal_buffer) > self.buffer_size:
            self.signal_buffer.pop(0)

        if len(self.signal_buffer) < self.buffer_size:
            progress = len(self.signal_buffer) / self.buffer_size
            partial_data = np.array(self.signal_buffer, dtype=np.float64)
            if len(partial_data) > 1:
                partial_data = partial_data - np.mean(partial_data)
            return False, 0.0, partial_data.tolist(), [], progress

        # Buffer is full — process it
        data = np.array(self.signal_buffer, dtype=np.float64)

        # Detrend
        data = data - np.mean(data)

        # Apply bandpass filter
        filtered_data = self._butter_bandpass_filter(data)

        # FFT with Hamming window
        N = len(filtered_data)
        windowed = filtered_data * np.hamming(N)
        fft_mag = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(N, 1.0 / self.fps)

        # Restrict to valid heart-rate band
        valid_mask = (freqs >= self.lowcut) & (freqs <= self.highcut)
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) == 0:
            return True, 0.0, filtered_data.tolist(), [], 0.0

        valid_mags = fft_mag[valid_indices]
        valid_freqs = freqs[valid_indices]

        peak_idx = np.argmax(valid_mags)
        peak_freq = valid_freqs[peak_idx]
        peak_mag = valid_mags[peak_idx]

        # --- SNR GATE ---
        # SNR = peak power / mean power of remaining bins
        # This distinguishes a real rhythmic signal from flat noise
        other_mags = np.delete(valid_mags, peak_idx)
        noise_floor = np.mean(other_mags) if len(other_mags) > 0 else 1e-9
        snr = peak_mag / (noise_floor + 1e-9)

        # Reject if signal is not convincingly dominant
        if snr < self.SNR_THRESHOLD:
            spectrum = [{"freq": float(f), "mag": float(m)} for f, m in zip(valid_freqs, valid_mags)]
            return True, 0.0, filtered_data.tolist(), spectrum, 0.0

        bpm = peak_freq * 60.0

        # Normalize confidence to 0-1 range, capped at SNR=10
        confidence = min(snr / 10.0, 1.0)

        spectrum = [{"freq": float(f), "mag": float(m)} for f, m in zip(valid_freqs, valid_mags)]

        return True, bpm, filtered_data.tolist(), spectrum, confidence
