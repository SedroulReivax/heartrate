import cv2
import numpy as np

class FaceROIExtractor:
    def __init__(self):
        # We bypass Haar Cascades and MediaPipe entirely to avoid missing data files
        # and network timeouts on downloads.
        # We will use static Regions of Interest and ask the user to center their face.
        pass

    def process_frame(self, frame):
        """
        Processes a BGR frame, extracts static ROIs, and returns the average green channel value.
        """
        ih, iw, _ = frame.shape
        
        # Assume face is roughly in the center, taking up 35% of the width and 60% of the height
        fw = int(iw * 0.35)
        fh = int(ih * 0.6)
        fx = int(iw * 0.325)
        fy = int(ih * 0.2)
        
        # Forehead: top 15% of face, centered
        fh_w = int(fw * 0.5)
        fh_h = int(fh * 0.15)
        fh_x = fx + int(fw * 0.25)
        fh_y = fy + int(fh * 0.05)
        
        # Left Cheek
        lc_w = int(fw * 0.2)
        lc_h = int(fh * 0.2)
        lc_x = fx + int(fw * 0.15)
        lc_y = fy + int(fh * 0.45)
        
        # Right Cheek
        rc_w = int(fw * 0.2)
        rc_h = int(fh * 0.2)
        rc_x = fx + int(fw * 0.65)
        rc_y = fy + int(fh * 0.45)
        
        rois = [
            (fh_x, fh_y, fh_w, fh_h),
            (lc_x, lc_y, lc_w, lc_h),
            (rc_x, rc_y, rc_w, rc_h)
        ]
        
        green_sum = 0
        pixel_count = 0
        
        for (rx, ry, rw, rh) in rois:
            if rw > 0 and rh > 0:
                roi_region = frame[ry:ry+rh, rx:rx+rw]
                green_sum += np.sum(roi_region[:, :, 1])
                pixel_count += rw * rh
                
        if pixel_count == 0:
            return True, rois, 0.0
            
        avg_green = float(green_sum) / pixel_count
        return True, rois, avg_green
