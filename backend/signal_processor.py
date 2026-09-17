import numpy as np
from scipy.signal import butter, lfilter

class SignalProcessor:
    def __init__(self, fps=30, buffer_size=300):
        self.fps = fps
        self.buffer_size = buffer_size
        self.signal_buffer = []
        
        # Bandpass filter parameters (0.75 Hz to 3.0 Hz corresponds to 45 to 180 BPM)
        self.lowcut = 0.75
        self.highcut = 3.0
        
    def butter_bandpass(self, lowcut, highcut, fs, order=5):
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        return b, a

    def butter_bandpass_filter(self, data, lowcut, highcut, fs, order=5):
        b, a = self.butter_bandpass(lowcut, highcut, fs, order=order)
        y = lfilter(b, a, data)
        return y

    def process(self, new_value):
        """
        Adds a new value to the buffer and computes BPM if buffer is full.
        Returns:
            is_ready (bool): True if we have enough data
            bpm (float): Calculated BPM
            filtered_signal (list): The filtered signal for visualization
            spectrum (list): The FFT spectrum (frequencies, magnitudes)
            confidence (float): Signal confidence
        """
        self.signal_buffer.append(new_value)
        
        if len(self.signal_buffer) > self.buffer_size:
            self.signal_buffer.pop(0)
            
        if len(self.signal_buffer) < self.buffer_size:
            # Not ready
            progress = len(self.signal_buffer) / self.buffer_size
            # Normalize partial signal just for visualization
            partial_data = np.array(self.signal_buffer)
            if len(partial_data) > 1:
                partial_data = partial_data - np.mean(partial_data)
            return False, 0.0, partial_data.tolist(), [], progress
            
        # Buffer is full, process it
        data = np.array(self.signal_buffer)
        
        # Normalize data (detrend)
        data = data - np.mean(data)
        
        # Apply bandpass filter
        filtered_data = self.butter_bandpass_filter(data, self.lowcut, self.highcut, self.fps, order=3)
        
        # Compute FFT
        N = len(filtered_data)
        # Use Hamming window to reduce spectral leakage
        windowed_data = filtered_data * np.hamming(N)
        
        fft_result = np.fft.rfft(windowed_data)
        fft_mag = np.abs(fft_result)
        freqs = np.fft.rfftfreq(N, 1.0 / self.fps)
        
        # Find peak in the valid range (0.75 to 3.0 Hz)
        valid_indices = np.where((freqs >= self.lowcut) & (freqs <= self.highcut))[0]
        if len(valid_indices) == 0:
             return True, 0.0, filtered_data.tolist(), [], 0.0
             
        valid_mags = fft_mag[valid_indices]
        valid_freqs = freqs[valid_indices]
        
        peak_idx = np.argmax(valid_mags)
        peak_freq = valid_freqs[peak_idx]
        peak_mag = valid_mags[peak_idx]
        
        bpm = peak_freq * 60.0
        
        # Calculate confidence
        # Heuristic: ratio of peak magnitude to total magnitude in valid range
        total_mag = np.sum(valid_mags)
        confidence = (peak_mag / total_mag) * 100 if total_mag > 0 else 0
        
        # Prepare spectrum for UI
        spectrum = [{"freq": float(f), "mag": float(m)} for f, m in zip(valid_freqs, valid_mags)]
        
        return True, bpm, filtered_data.tolist(), spectrum, confidence
