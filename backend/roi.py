import cv2
import numpy as np

class FaceROIExtractor:
    """
    Uses Lucas-Kanade Optical Flow to physically track skin tissue.
    This eliminates 'bounding box sliding' noise that ruins rPPG signals.
    """

    SKIN_CB_MIN, SKIN_CB_MAX = 77, 127
    SKIN_CR_MIN, SKIN_CR_MAX = 133, 173

    def __init__(self):
        import urllib.request, os
        prototxt_path = "deploy.prototxt"
        model_path = "res10_300x300_ssd_iter_140000.caffemodel"
        self.net = None
        if os.path.exists(prototxt_path) and os.path.exists(model_path):
            self.net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)
            
        self.feature_params = dict(maxCorners=150, qualityLevel=0.01, minDistance=5, blockSize=7)
        self.lk_params = dict(winSize=(15, 15), maxLevel=2,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
                              
        self.p0 = None
        self.old_gray = None
        self.tracking_bbox = None

    def _detect_face_dnn(self, frame):
        if self.net is None:
            return None
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0))
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
        ycrcb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2YCrCb)
        cb, cr = ycrcb[:, :, 2], ycrcb[:, :, 1]
        skin_mask = ((cb >= self.SKIN_CB_MIN) & (cb <= self.SKIN_CB_MAX) &
                     (cr >= self.SKIN_CR_MIN) & (cr <= self.SKIN_CR_MAX))
        return float(np.sum(skin_mask)) / skin_mask.size if skin_mask.size > 0 else 0

    def process_frame(self, frame):
        ih, iw = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. LK Tracking Update
        if self.p0 is not None and self.old_gray is not None and self.tracking_bbox is not None:
            p1, st, err = cv2.calcOpticalFlowPyrLK(self.old_gray, gray, self.p0, None, **self.lk_params)
            if p1 is not None and st is not None:
                good_new = p1[st == 1]
                good_old = self.p0[st == 1]
                if len(good_new) > 10:
                    # Calculate median translation
                    dx = np.median(good_new[:, 0] - good_old[:, 0])
                    dy = np.median(good_new[:, 1] - good_old[:, 1])
                    
                    x, y, w, h = self.tracking_bbox
                    self.tracking_bbox = (int(x + dx), int(y + dy), w, h)
                    self.p0 = good_new.reshape(-1, 1, 2)
                    self.old_gray = gray.copy()
                    
                    # Verify skin ratio to ensure we haven't drifted off the face
                    nx, ny, nw, nh = self.tracking_bbox
                    # clamp
                    nx, ny = max(0, nx), max(0, ny)
                    nw, nh = min(nw, iw - nx), min(nh, ih - ny)
                    crop = frame[ny:ny+nh, nx:nx+nw]
                    if crop.size > 0 and self._skin_pixel_ratio(crop) > 0.2:
                        return self._extract_signals(frame, (nx, ny, nw, nh))
            
            # Tracking failed or lost too many points, force re-init
            self.p0 = None
            self.tracking_bbox = None

        # 2. Re-initialization (Detection)
        face_box = self._detect_face_dnn(frame)
        if face_box is None:
            # Fallback to static center
            fw, fh = int(iw * 0.35), int(ih * 0.60)
            fx, fy = int(iw * 0.325), int(ih * 0.20)
            face_box = (fx, fy, fw, fh)
            
        fx, fy, fw, fh = face_box
        crop = frame[fy:fy+fh, fx:fx+fw]
        if crop.size == 0 or self._skin_pixel_ratio(crop) < 0.20:
            return False, [], (0.0, 0.0, 0.0)
            
        self.tracking_bbox = (fx, fy, fw, fh)
        
        # Find points to track strictly within the skin region
        roi_gray = gray[fy:fy+fh, fx:fx+fw]
        pts = cv2.goodFeaturesToTrack(roi_gray, mask=None, **self.feature_params)
        if pts is not None:
            self.p0 = pts + np.array([[[fx, fy]]], dtype=np.float32)
            self.old_gray = gray.copy()

        return self._extract_signals(frame, self.tracking_bbox)
        
    def _extract_signals(self, frame, face_box):
        ih, iw = frame.shape[:2]
        fx, fy, fw, fh = face_box
        
        # Clamp to frame bounds
        fx, fy = max(0, fx), max(0, fy)
        fw, fh = min(fw, iw - fx), min(fh, ih - fy)
        
        fh_w, fh_h = max(1, int(fw * 0.50)), max(1, int(fh * 0.15))
        fh_x, fh_y = fx + int(fw * 0.25), fy + int(fh * 0.05)

        lc_w, lc_h = max(1, int(fw * 0.20)), max(1, int(fh * 0.20))
        lc_x, lc_y = fx + int(fw * 0.15), fy + int(fh * 0.45)

        rc_w, rc_h = max(1, int(fw * 0.20)), max(1, int(fh * 0.20))
        rc_x, rc_y = fx + int(fw * 0.65), fy + int(fh * 0.45)

        rois = [(fh_x, fh_y, fh_w, fh_h), (lc_x, lc_y, lc_w, lc_h), (rc_x, rc_y, rc_w, rc_h)]

        r_sum = g_sum = b_sum = 0.0
        pixel_count = 0
        
        for (rx, ry, rw, rh) in rois:
            rx, ry = max(0, rx), max(0, ry)
            rw = min(rw, iw - rx)
            rh = min(rh, ih - ry)
            if rw > 0 and rh > 0:
                roi_region = frame[ry:ry+rh, rx:rx+rw]
                b_sum += np.sum(roi_region[:, :, 0].astype(np.float64))
                g_sum += np.sum(roi_region[:, :, 1].astype(np.float64))
                r_sum += np.sum(roi_region[:, :, 2].astype(np.float64))
                pixel_count += rw * rh

        if pixel_count == 0:
            return True, rois, (0.0, 0.0, 0.0)

        avg_rgb = (r_sum / pixel_count, g_sum / pixel_count, b_sum / pixel_count)
        return True, rois, avg_rgb
