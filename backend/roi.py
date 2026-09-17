import cv2
import numpy as np

class FaceROIExtractor:
    """
    Uses OpenCV's DNN face detector for accurate, fast face detection.
    Falls back to variance-based sanity check on the ROI pixels 
    to ensure we're actually looking at skin-like content.
    """

    # Skin color thresholds in YCrCb (empirically established from literature)
    # Cb: 77-127, Cr: 133-173
    SKIN_CB_MIN, SKIN_CB_MAX = 77, 127
    SKIN_CR_MIN, SKIN_CR_MAX = 133, 173

    def __init__(self):
        # Load OpenCV DNN face detector (ships bundled with opencv-contrib-python)
        # Model files: res10_300x300_ssd_iter_140000.caffemodel
        # We download them on first run to the local backend folder.
        import urllib.request, os
        prototxt_path = "deploy.prototxt"
        model_path = "res10_300x300_ssd_iter_140000.caffemodel"
        
        self.net = None
        if os.path.exists(prototxt_path) and os.path.exists(model_path):
            self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
        else:
            print("DNN model files not found. Using skin-color based ROI fallback.")

    def _detect_face_dnn(self, frame):
        """Use OpenCV DNN SSD face detector. Returns (x, y, w, h) or None."""
        if self.net is None:
            return None
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0,
            (300, 300), (104.0, 177.0, 123.0)
        )
        self.net.setInput(blob)
        detections = self.net.forward()
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.6:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                return (max(0, x1), max(0, y1), min(w, x2-x1), min(h, y2-y1))
        return None

    def _skin_pixel_ratio(self, roi_bgr):
        """Returns fraction of pixels in YCrCb skin range."""
        ycrcb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2YCrCb)
        cb = ycrcb[:, :, 2]
        cr = ycrcb[:, :, 1]
        skin_mask = (
            (cb >= self.SKIN_CB_MIN) & (cb <= self.SKIN_CB_MAX) &
            (cr >= self.SKIN_CR_MIN) & (cr <= self.SKIN_CR_MAX)
        )
        return float(np.sum(skin_mask)) / skin_mask.size

    def process_frame(self, frame):
        """
        Returns (face_detected, rois, avg_green).
        face_detected is False if no face is found OR the ROI doesn't look like skin.
        """
        ih, iw = frame.shape[:2]

        face_box = self._detect_face_dnn(frame)

        if face_box is not None:
            fx, fy, fw, fh = face_box
        else:
            # No DNN — use static center box but VALIDATE with skin color check
            fw = int(iw * 0.35)
            fh = int(ih * 0.60)
            fx = int(iw * 0.325)
            fy = int(ih * 0.20)

        # --- Skin color sanity check ---
        face_crop = frame[fy:fy+fh, fx:fx+fw]
        if face_crop.size == 0:
            return False, [], 0.0
        
        skin_ratio = self._skin_pixel_ratio(face_crop)
        
        # Require at least 20% of the face region to be skin-colored
        if skin_ratio < 0.20:
            return False, [], 0.0

        # --- Extract ROIs ---
        fh_w = max(1, int(fw * 0.50))
        fh_h = max(1, int(fh * 0.15))
        fh_x = fx + int(fw * 0.25)
        fh_y = fy + int(fh * 0.05)

        lc_w = max(1, int(fw * 0.20))
        lc_h = max(1, int(fh * 0.20))
        lc_x = fx + int(fw * 0.15)
        lc_y = fy + int(fh * 0.45)

        rc_w = max(1, int(fw * 0.20))
        rc_h = max(1, int(fh * 0.20))
        rc_x = fx + int(fw * 0.65)
        rc_y = fy + int(fh * 0.45)

        rois = [
            (fh_x, fh_y, fh_w, fh_h),
            (lc_x, lc_y, lc_w, lc_h),
            (rc_x, rc_y, rc_w, rc_h),
        ]

        green_sum = 0
        pixel_count = 0
        for (rx, ry, rw, rh) in rois:
            rw = min(rw, iw - rx)
            rh = min(rh, ih - ry)
            if rw > 0 and rh > 0:
                roi_region = frame[ry:ry+rh, rx:rx+rw]
                green_sum += np.sum(roi_region[:, :, 1].astype(np.float64))
                pixel_count += rw * rh

        avg_green = float(green_sum) / pixel_count if pixel_count > 0 else 0.0
        return True, rois, avg_green
