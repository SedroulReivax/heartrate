import cv2
import mediapipe as mp
import numpy as np

class FaceROIExtractor:
    def __init__(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )

    def process_frame(self, frame):
        """
        Processes a BGR frame, detects face, extracts ROIs, and returns the average green channel value.
        Returns:
            face_found (bool)
            rois (list of (x,y,w,h) tuples)
            avg_green (float)
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_detection.process(rgb_frame)
        
        if not results.detections:
            return False, [], 0.0
            
        # Get the first face
        detection = results.detections[0]
        bboxC = detection.location_data.relative_bounding_box
        ih, iw, _ = frame.shape
        x, y, w, h = int(bboxC.xmin * iw), int(bboxC.ymin * ih), int(bboxC.width * iw), int(bboxC.height * ih)
        
        # Ensure bbox is within frame
        x = max(0, x)
        y = max(0, y)
        w = min(iw - x, w)
        h = min(ih - y, h)
        
        if w <= 0 or h <= 0:
            return False, [], 0.0

        # Define ROIs relative to face bbox
        # Forehead: top 15%, width 50% centered
        fh_w = int(w * 0.5)
        fh_h = int(h * 0.15)
        fh_x = x + int(w * 0.25)
        fh_y = y + int(h * 0.05)
        
        # Left Cheek: width 20%, height 20%, below eyes
        lc_w = int(w * 0.2)
        lc_h = int(h * 0.2)
        lc_x = x + int(w * 0.15)
        lc_y = y + int(h * 0.45)
        
        # Right Cheek: width 20%, height 20%, below eyes
        rc_w = int(w * 0.2)
        rc_h = int(h * 0.2)
        rc_x = x + int(w * 0.65)
        rc_y = y + int(h * 0.45)
        
        rois = [
            (fh_x, fh_y, fh_w, fh_h),
            (lc_x, lc_y, lc_w, lc_h),
            (rc_x, rc_y, rc_w, rc_h)
        ]
        
        # Extract average green channel from these ROIs
        green_sum = 0
        pixel_count = 0
        
        for (rx, ry, rw, rh) in rois:
            # Ensure ROI is within bounds
            rx = max(0, rx)
            ry = max(0, ry)
            rw = min(iw - rx, rw)
            rh = min(ih - ry, rh)
            
            if rw > 0 and rh > 0:
                roi_region = frame[ry:ry+rh, rx:rx+rw]
                # BGR format, so green is index 1
                green_sum += np.sum(roi_region[:, :, 1])
                pixel_count += rw * rh
                
        if pixel_count == 0:
            return True, rois, 0.0
            
        avg_green = float(green_sum) / pixel_count
        return True, rois, avg_green
