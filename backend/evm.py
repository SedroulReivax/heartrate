import numpy as np
from scipy.signal import butter, lfilter

class EulerianMagnifier:
    """
    Real-time Eulerian Video Magnification for colour/pulse amplification.

    Pipeline per frame:
      1. Spatially blur (Gaussian downsample) to isolate low-freq colour bands.
      2. Accumulate frames in a ring buffer.
      3. Once buffer is full: apply IIR Butterworth bandpass along the time axis
         to isolate the cardiac-frequency colour oscillation (0.75–3 Hz).
      4. Scale the filtered signal by `alpha` (amplification factor).
      5. Upsample back and add onto the original frame.
    """

    def __init__(self, fps: float = 30.0, low_hz: float = 0.75,
                 high_hz: float = 3.0, alpha: float = 60,
                 pyramid_levels: int = 3, buffer_seconds: float = 3.0):
        self.fps = fps
        self.low_hz = low_hz
        self.high_hz = high_hz
        self.alpha = alpha
        self.pyramid_levels = pyramid_levels
        self.buffer_size = max(int(fps * buffer_seconds), 6)

        # Build Butterworth coefficients once
        nyq = fps / 2.0
        low = low_hz / nyq
        high = high_hz / nyq
        # Clamp to avoid instability near Nyquist
        low = max(low, 0.01)
        high = min(high, 0.99)
        self.b, self.a = butter(3, [low, high], btype='band')

        # Ring buffer (list of small frames, dtype float32)
        self.buffer: list[np.ndarray] = []
        # Filter state for each pixel/channel (zi) — initialised lazily
        self._zi = None
        self._frame_shape_small: tuple | None = None

    def _pyramid_downsample(self, frame: np.ndarray) -> np.ndarray:
        """
        Build a quick Gaussian pyramid and return the coarsest level.
        This blurs spatially so we only track low-spatial-freq colour changes.
        """
        img = frame.astype(np.float32) / 255.0
        for _ in range(self.pyramid_levels):
            img = self._pyrdown(img)
        return img

    @staticmethod
    def _pyrdown(img: np.ndarray) -> np.ndarray:
        """Simple 2× downsample with a 5×5 Gaussian kernel."""
        import cv2
        return cv2.pyrDown(img)

    @staticmethod
    def _pyrup_to(img: np.ndarray, target_shape: tuple) -> np.ndarray:
        """Upsample until at least as large as target_shape, then crop."""
        import cv2
        h, w = target_shape[:2]
        while img.shape[0] < h or img.shape[1] < w:
            img = cv2.pyrUp(img)
        return img[:h, :w]

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Returns the EVM-amplified version of `frame` (uint8 BGR).
        Returns the original frame unchanged until the buffer is full.
        """
        orig_h, orig_w = frame.shape[:2]

        # 1. Spatial blur / downsample
        small = self._pyramid_downsample(frame)          # float32, [0,1]
        sh, sw = small.shape[:2]

        self.buffer.append(small)

        # 2. Trim ring buffer
        if len(self.buffer) > self.buffer_size:
            self.buffer.pop(0)

        # Not enough data yet → return original
        if len(self.buffer) < self.buffer_size:
            return frame.copy()

        # 3. Stack → (T, H, W, C)
        video = np.stack(self.buffer, axis=0)   # (T, sh, sw, 3)

        # Reshape to (T, N) where N = sh*sw*3 for vectorised filtering
        T = video.shape[0]
        N = sh * sw * 3
        flat = video.reshape(T, N)              # (T, N)

        # 4. Bandpass filter along time axis (axis=0)
        filtered = lfilter(self.b, self.a, flat, axis=0)  # (T, N)

        # Take the last filtered frame
        last_filtered = filtered[-1].reshape(sh, sw, 3)   # float32

        # 5. Amplify — boost green channel more (hemoglobin signal)
        amplified = last_filtered.copy()
        amplified[:, :, 1] *= self.alpha        # Green  (BGR index 1)
        amplified[:, :, 0] *= self.alpha * 0.3  # Blue   (creates purple tint)
        amplified[:, :, 2] *= self.alpha * 0.1  # Red    (minimal)

        # 6. Upsample back to original resolution
        amplified_up = self._pyrup_to(amplified, (orig_h, orig_w))

        # 7. Add to original frame (convert back from [0,1] range)
        orig_float = frame.astype(np.float32) / 255.0
        result = orig_float + amplified_up
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)

        return result
