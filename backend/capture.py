import cv2
import asyncio
import base64
import time
from roi import FaceROIExtractor
from signal_processor import SignalProcessor
from evm import EulerianMagnifier

class CaptureSession:
    def __init__(self, fps=30):
        self.fps = fps
        # Default backend — MSMF works fine when only one instance holds the camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Use actual FPS reported by the driver (could be 15, 25, 30…)
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
        if 1 < actual_fps < 120:
            self.fps = actual_fps

        self.roi_extractor = FaceROIExtractor()
        self.signal_processor = SignalProcessor(fps=self.fps, buffer_size=int(self.fps * 10))
        self.evm = EulerianMagnifier(fps=self.fps)
        self.is_running = False

    def encode_frame(self, frame):
        if frame is None:
            return None
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
        return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

    async def run_loop(self, queue: asyncio.Queue):
        self.is_running = True

        if not self.cap.isOpened():
            print("ERROR: Cannot open camera")
            return

        print(f"Camera opened @ {self.fps:.1f} fps")

        try:
            while self.is_running:
                ret, frame = self.cap.read()
                if not ret:
                    await asyncio.sleep(0.05)
                    continue

                # Mirror for natural webcam feel
                frame = cv2.flip(frame, 1)
                frame = cv2.resize(frame, (640, 480))

                # --- EVM amplified copy ---
                amplified_frame = self.evm.process_frame(frame)

                # --- rPPG signal from static ROIs ---
                face_found, rois, avg_rgb = self.roi_extractor.process_frame(frame)

                state = {
                    "face_detected": face_found,
                    "rois": [list(r) for r in rois],
                    "avg_green": float(avg_rgb[1]) if face_found else 0.0,
                    "is_ready": False,
                    "progress": 0.0,
                    "bpm": 0.0,
                    "signal": [],
                    "spectrum": [],
                    "confidence": 0.0,
                    "frame_original": None,
                    "frame_amplified": None,
                }

                if face_found:
                    now = time.perf_counter()
                    is_ready, bpm, sig, spec, conf = self.signal_processor.process(avg_rgb, now)
                    state.update({
                        "is_ready": is_ready,
                        "bpm": round(float(bpm), 1),
                        "signal": [float(v) for v in sig],
                        "spectrum": spec,
                        "confidence": float(conf),
                        "progress": float(conf),
                    })
                else:
                    self.signal_processor.r_buf = []
                    self.signal_processor.g_buf = []
                    self.signal_processor.b_buf = []

                # Draw ROI boxes on the original frame
                for (x, y, w, h) in rois:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 65), 2)

                state["frame_original"] = self.encode_frame(frame)
                state["frame_amplified"] = self.encode_frame(amplified_frame)

                try:
                    queue.put_nowait(state)
                except asyncio.QueueFull:
                    pass

                await asyncio.sleep(1.0 / self.fps)

        finally:
            self.cap.release()
            self.is_running = False
            print("Camera released")

    def stop(self):
        self.is_running = False
