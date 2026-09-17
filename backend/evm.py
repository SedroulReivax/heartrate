import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

class EulerianMagnifier:
    """
    Real-time Eulerian Video Magnification for colour/pulse amplification.
    
    Optimized for Real-Time execution:
    Instead of re-filtering a massive ring buffer every frame (O(N*T)), 
    this maintains the internal IIR filter state (zi) to process streams in O(N).
    """

    def __init__(self, fps: float = 30.0, low_hz: float = 0.75,
                 high_hz: float = 3.0, alpha: float = 120,
                 pyramid_levels: int = 3):
        self.fps = fps
        self.alpha = alpha
        self.pyramid_levels = pyramid_levels

        # Build Butterworth coefficients once
        nyq = fps / 2.0
        low = max(low_hz / nyq, 0.01)
        high = min(high_hz / nyq, 0.99)
        self.b, self.a = butter(3, [low, high], btype='band')

        # Compute initial state multiplier for a 1D sequence
        self.zi_1d = lfilter_zi(self.b, self.a)
        
        # Filter state for each pixel/channel (zi) — initialized on first frame
        self._zi = None

    def _pyramid_downsample(self, frame: np.ndarray) -> np.ndarray:
        """Spatially blur and downsample to isolate low-freq colour changes."""
        import cv2
        img = frame.astype(np.float32) / 255.0
        for _ in range(self.pyramid_levels):
            img = cv2.pyrDown(img)
        return img

    @staticmethod
    def _pyrup_to(img: np.ndarray, target_shape: tuple) -> np.ndarray:
        """Upsample until at least as large as target_shape, then crop."""
        import cv2
        h, w = target_shape[:2]
        while img.shape[0] < h or img.shape[1] < w:
            img = cv2.pyrUp(img)
        return img[:h, :w]

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        orig_h, orig_w = frame.shape[:2]

        # 1. Spatial blur / downsample
        small = self._pyramid_downsample(frame)          # float32, [0,1]
        sh, sw = small.shape[:2]
        N = sh * sw * 3

        # Flatten frame to (1, N) for vectorized filtering
        flat = small.reshape(1, N)

        # 2. Initialize filter state on first frame
        if self._zi is None:
            # Broadcast 1D zi to (len_zi, N), scaled by the first frame
            self._zi = self.zi_1d[:, None] * flat

        # 3. Temporal Bandpass (IIR filter stepping 1 frame forward)
        filtered_flat, self._zi = lfilter(self.b, self.a, flat, axis=0, zi=self._zi)
        
        # Reshape back to image shape
        filtered_img = filtered_flat.reshape(sh, sw, 3)

        # 4. Amplify — boost green channel more (hemoglobin signal)
        amplified = filtered_img.copy()
        amplified[:, :, 1] *= self.alpha        # Green 
        amplified[:, :, 0] *= self.alpha * 0.1  # Blue
        amplified[:, :, 2] *= self.alpha * 0.1  # Red

        # 5. Upsample back to original resolution
        amplified_up = self._pyrup_to(amplified, (orig_h, orig_w))

        # 6. Add to original frame
        orig_float = frame.astype(np.float32) / 255.0
        result = orig_float + amplified_up
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)

        return result
