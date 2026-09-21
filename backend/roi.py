import cv2
import numpy as np
import mediapipe as mp

class FaceROIExtractor:
    """
    Uses MediaPipe Face Mesh to physically track skin tissue.
    This eliminates 'bounding box sliding' noise that ruins rPPG signals.
    """

    def __init__(self):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # MediaPipe landmark indices for forehead, left cheek, right cheek
        self.FOREHEAD_INDICES = [10, 107, 108, 109, 338, 337, 336, 151, 9, 8]
        self.LEFT_CHEEK_INDICES = [117, 118, 119, 100, 47, 50, 205, 206]
        self.RIGHT_CHEEK_INDICES = [346, 347, 348, 329, 277, 280, 425, 426]

    def process_frame(self, frame):
        ih, iw = frame.shape[:2]
        
        # Convert the BGR image to RGB before processing
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if not results.multi_face_landmarks:
            return False, [], (0.0, 0.0, 0.0)
            
        landmarks = results.multi_face_landmarks[0]
        
        rois = []
        
        mask = np.zeros((ih, iw), dtype=np.uint8)
        
        def extract_roi(indices):
            nonlocal rois
            
            pts = np.array([[[int(landmarks.landmark[idx].x * iw), int(landmarks.landmark[idx].y * ih)] for idx in indices]], dtype=np.int32)
            cv2.fillPoly(mask, pts, 255)
            
            # Calculate bounding box for visualization
            xs = pts[0, :, 0]
            ys = pts[0, :, 1]
            x_min, x_max = max(0, np.min(xs)), min(iw, np.max(xs))
            y_min, y_max = max(0, np.min(ys)), min(ih, np.max(ys))
            
            w = x_max - x_min
            h = y_max - y_min
            
            if w > 0 and h > 0:
                rois.append((int(x_min), int(y_min), int(w), int(h)))
        
        extract_roi(self.FOREHEAD_INDICES)
        extract_roi(self.LEFT_CHEEK_INDICES)
        extract_roi(self.RIGHT_CHEEK_INDICES)
        
        roi_pixels = frame[mask == 255]
        pixel_count = len(roi_pixels)
        if pixel_count == 0:
            return False, rois, (0.0, 0.0, 0.0)
            
        b_sum = np.sum(roi_pixels[:, 0].astype(np.float64))
        g_sum = np.sum(roi_pixels[:, 1].astype(np.float64))
        r_sum = np.sum(roi_pixels[:, 2].astype(np.float64))
        
        avg_rgb = (r_sum / pixel_count, g_sum / pixel_count, b_sum / pixel_count)
        return True, rois, avg_rgb
