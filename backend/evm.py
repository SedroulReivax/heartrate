import numpy as np
import cv2
from scipy.signal import butter, lfilter, lfilter_zi

class EulerianMagnifier:
    """
    ULTRA-FAST Real-time Eulerian Video Magnification.
    
    Optimizations:
    1. Only processes a cropped center region (where the face is supposed to be).
    2. Only processes the GREEN channel (hemoglobin absorption is highest here).
    3. Uses 1D IIR filter state (zi) to process streams in O(N) without buffering frames.
    """

    def __init__(self, fps: float = 30.0, low_hz: float = 0.75,
                 high_hz: float = 3.0, alpha: float = 150,
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
        
        # Filter state for the pixels
        self._zi = None

    def _pyramid_downsample(self, frame_single_channel: np.ndarray) -> np.ndarray:
        """Spatially blur and downsample."""
        img = frame_single_channel.astype(np.float32) / 255.0
        for _ in range(self.pyramid_levels):
            img = cv2.pyrDown(img)
        return img

    @staticmethod
    def _pyrup_to(img: np.ndarray, target_shape: tuple) -> np.ndarray:
        """Upsample until at least as large as target_shape, then crop."""
        h, w = target_shape[:2]
        while img.shape[0] < h or img.shape[1] < w:
            img = cv2.pyrUp(img)
        return img[:h, :w]

    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        ih, iw = frame.shape[:2]
        
        # 1. Crop to face region (matches the static ROI area roughly)
        # We process a box taking up 40% width and 60% height in the center
        cw, ch = int(iw * 0.4), int(ih * 0.6)
        cx, cy = int(iw * 0.3), int(ih * 0.2)
        
        # Extract the cropped region
        crop = frame[cy:cy+ch, cx:cx+cw]
        
        # 2. Extract ONLY the Green channel (index 1 in BGR)
        green_channel = crop[:, :, 1]

        # 3. Spatial blur / downsample
        small_green = self._pyramid_downsample(green_channel)  # float32, [0,1]
        sh, sw = small_green.shape[:2]
        N = sh * sw

        # Flatten frame to (1, N) for vectorized filtering
        flat = small_green.reshape(1, N)

        # 4. Initialize filter state on first frame
        if self._zi is None or self._zi.shape[1] != N:
            # Broadcast 1D zi to (len_zi, N), scaled by the first frame
            self._zi = self.zi_1d[:, None] * flat

        # 5. Temporal Bandpass (IIR filter stepping 1 frame forward)
        filtered_flat, self._zi = lfilter(self.b, self.a, flat, axis=0, zi=self._zi)
        
        # Reshape back to image shape
        filtered_img = filtered_flat.reshape(sh, sw)

        # 6. Amplify the filtered signal
        amplified_signal = filtered_img * self.alpha

        # 7. Upsample back to crop resolution
        amplified_up = self._pyrup_to(amplified_signal, (ch, cw))

        # 8. Add amplified signal back to the original frame copy
        result = frame.copy()
        
        # We only add the signal to the Green channel of the crop
        # (Optionally subtract slightly from Red/Blue to increase contrast, but let's keep it simple)
        crop_float_green = crop[:, :, 1].astype(np.float32) / 255.0
        new_green = crop_float_green + amplified_up
        
        # Convert back and replace in the result frame
        result[cy:cy+ch, cx:cx+cw, 1] = np.clip(new_green * 255.0, 0, 255).astype(np.uint8)
        
        # Add a subtle dark purple tint to the other channels in the amplified region to make it stand out
        # Since green goes up, if we drop R and B slightly it enhances the "flashing" effect
        # Wait, the user said "purple", so amplifying Green + dropping R/B works.
        # Actually, let's subtract the amplified signal from Red and Blue
        crop_float_red = crop[:, :, 2].astype(np.float32) / 255.0
        new_red = crop_float_red - (amplified_up * 0.5)
        result[cy:cy+ch, cx:cx+cw, 2] = np.clip(new_red * 255.0, 0, 255).astype(np.uint8)
        
        crop_float_blue = crop[:, :, 0].astype(np.float32) / 255.0
        new_blue = crop_float_blue - (amplified_up * 0.5)
        result[cy:cy+ch, cx:cx+cw, 0] = np.clip(new_blue * 255.0, 0, 255).astype(np.uint8)

        # Draw a faint border around the EVM processed region so the user knows where it is
        cv2.rectangle(result, (cx, cy), (cx+cw, cy+ch), (50, 50, 50), 1)

        return result
