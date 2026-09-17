import cv2
import asyncio
import base64
from roi import FaceROIExtractor
from signal_processor import SignalProcessor

class CaptureSession:
    def __init__(self, fps=30):
        self.fps = fps
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        
        # In case the camera doesn't support exactly the requested FPS, we get the actual
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if actual_fps > 0 and actual_fps < 100:
            self.fps = actual_fps
            
        self.roi_extractor = FaceROIExtractor()
        self.signal_processor = SignalProcessor(fps=self.fps, buffer_size=int(self.fps * 10))
        self.is_running = False

    async def run_loop(self, queue: asyncio.Queue):
        self.is_running = True
        
        try:
            while self.is_running:
                ret, frame = self.cap.read()
                if not ret:
                    await asyncio.sleep(0.1)
                    continue

                # Mirror frame horizontally for intuitive view
                frame = cv2.flip(frame, 1)
                
                # Resize for performance if needed
                frame = cv2.resize(frame, (640, 480))
                
                # Process ROI
                face_found, rois, avg_green = self.roi_extractor.process_frame(frame)
                
                state = {
                    "face_detected": face_found,
                    "rois": rois,
                    "avg_green": avg_green,
                    "is_ready": False,
                    "progress": 0.0,
                    "bpm": 0.0,
                    "signal": [],
                    "spectrum": [],
                    "confidence": 0.0,
                    "frame": None
                }

                if face_found:
                    # Process signal
                    is_ready, bpm, sig, spec, conf = self.signal_processor.process(avg_green)
                    state["is_ready"] = is_ready
                    state["bpm"] = round(bpm, 1) if isinstance(bpm, float) else bpm
                    state["signal"] = sig
                    state["spectrum"] = spec
                    state["confidence"] = conf
                    if not is_ready:
                        state["progress"] = conf # using conf slot for progress when not ready
                else:
                    # Reset buffer if face lost
                    self.signal_processor.signal_buffer = []

                # Draw ROIs on frame
                if face_found:
                    for (x, y, w, h) in rois:
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                
                # Make frame monochrome green
                frame[:, :, 0] = 0 # Blue channel to 0
                frame[:, :, 2] = 0 # Red channel to 0
                
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                frame_b64 = base64.b64encode(buffer).decode('utf-8')
                state["frame"] = f"data:image/jpeg;base64,{frame_b64}"

                # Put state in queue without blocking indefinitely
                try:
                    queue.put_nowait(state)
                except asyncio.QueueFull:
                    pass
                
                # Sleep to maintain FPS
                await asyncio.sleep(1.0 / self.fps)
                
        finally:
            self.cap.release()
            self.is_running = False

    def stop(self):
        self.is_running = False
