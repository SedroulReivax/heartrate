import cv2
import asyncio
import base64
import time
from roi import FaceROIExtractor
from signal_processor import SignalProcessor, ProcessingConfig
from evm import EulerianMagnifier
from camera_controller import CameraController
from light_controller import LightController

class CaptureSession:
    def __init__(self, fps=30):
        self.fps = fps
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        
        self.cam_ctrl = CameraController(self.cap)
        self.actual_fps = self.cam_ctrl.configure_fps(self.fps)
        self.cam_ctrl.apply_manual_settings()

        self.roi_extractor = FaceROIExtractor()
        self.sig_proc = SignalProcessor(target_fps=self.actual_fps, buffer_seconds=10)
        self.evm = EulerianMagnifier(fps=self.actual_fps)
        self.light_ctrl = LightController()
        
        self.proc_config = ProcessingConfig()
        
        self.is_running = False
        self.enable_evm = False
        self.measurement_active = False
        self.force_compute = False

    def encode_frame(self, frame):
        if frame is None:
            return None
        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 55])
        return f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

    async def handle_commands(self, cmd_queue):
        while not cmd_queue.empty():
            cmd = cmd_queue.get_nowait()
            t = cmd.get("type")
            if t == "set_processing":
                reprocess = False
                if "algorithm" in cmd:
                    self.proc_config.algorithm = cmd["algorithm"]
                    reprocess = True
                if "bandpass" in cmd:
                    low = float(cmd["bandpass"].get("low", self.proc_config.min_hz))
                    high = float(cmd["bandpass"].get("high", self.proc_config.max_hz))
                    if low > 0 and high > low and high < (self.actual_fps / 2):
                        self.proc_config.min_hz = low
                        self.proc_config.max_hz = high
                        reprocess = True
                if "chrom" in cmd:
                    self.proc_config.chrom_alpha_mode = cmd["chrom"].get("alphaMode", self.proc_config.chrom_alpha_mode).upper()
                    alpha = float(cmd["chrom"].get("alpha", self.proc_config.chrom_alpha))
                    import math
                    if not math.isnan(alpha) and not math.isinf(alpha):
                        self.proc_config.chrom_alpha = alpha
                    reprocess = True
                if "evm" in cmd:
                    self.enable_evm = bool(cmd["evm"])
                if reprocess:
                    self.force_compute = True
            elif t == "lighting":
                action = cmd.get("action")
                if action == "on":
                    mode = cmd.get("mode", "screen").upper()
                    color = cmd.get("color", "white").upper()
                    self.light_ctrl.set_illumination(mode, color)
                    self.sig_proc.reset()
                elif action == "off":
                    self.light_ctrl.set_illumination("OFF")
                    self.sig_proc.reset()
            elif t == "measurement":
                action = cmd.get("action")
                if action == "start":
                    self.measurement_active = True
                    self.sig_proc.reset()
                elif action == "stop":
                    self.measurement_active = False
            elif t == "camera":
                # handle specific camera commands if needed
                pass

    async def run_loop(self, queue: asyncio.Queue, cmd_queue: asyncio.Queue):
        self.is_running = True

        if not self.cap.isOpened():
            print("ERROR: Cannot open camera")
            return

        print(f"Camera opened @ {self.actual_fps:.1f} fps")

        last_ui_update = 0
        last_sig_update = 0

        fail_count = 0
        try:
            while self.is_running:
                await self.handle_commands(cmd_queue)

                ret, frame = self.cap.read()
                if not ret:
                    fail_count += 1
                    if fail_count > 10:
                        print("Camera crashed. Hard restarting...")
                        self.cap.release()
                        await asyncio.sleep(0.5)
                        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                        self.cam_ctrl = CameraController(self.cap)
                        self.cam_ctrl.configure_fps(self.fps)
                        self.cam_ctrl.apply_manual_settings()
                        fail_count = 0
                    else:
                        await asyncio.sleep(0.05)
                    continue

                fail_count = 0
                frame = cv2.flip(frame, 1)
                now = time.perf_counter()
                
                if self.light_ctrl.check_stabilization():
                    self.sig_proc.reset()

                amplified_frame = None
                if self.enable_evm:
                    amplified_frame = self.evm.process_frame(frame)

                face_found, rois, avg_rgb = self.roi_extractor.process_frame(frame)
                
                is_ready, progress = False, 0.0
                empty_res = {"available": False, "bpm": 0.0, "peakHz": 0.0, "snrDb": 0.0, "confidence": 0.0, "signal": [], "spectrum": []}
                r_res, c_res, p_res = empty_res, empty_res, empty_res

                send_ui = (now - last_ui_update > 0.1) or self.force_compute
                compute_sig = send_ui and (now - last_sig_update > 0.2 or self.force_compute)

                if self.measurement_active and face_found and self.light_ctrl.state != "STARTING":
                    is_ready, progress, r_res, c_res, p_res = self.sig_proc.process(avg_rgb, now, self.proc_config, compute_results=compute_sig)
                elif not face_found:
                    self.sig_proc.reset()
                    
                if send_ui:
                    for (x, y, w, h) in rois:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 65), 2)
                        
                    state = {
                        "face_detected": face_found,
                        "rois": [list(r) for r in rois],
                        "avg_green": float(avg_rgb[1]) if face_found else 0.0,
                        "is_ready": is_ready,
                        "progress": progress,
                        
                        "config": {
                            "algorithm": self.proc_config.algorithm,
                            "min_hz": self.proc_config.min_hz,
                            "max_hz": self.proc_config.max_hz,
                            "chrom_alpha_mode": self.proc_config.chrom_alpha_mode,
                            "chrom_alpha": self.proc_config.chrom_alpha,
                            "evm": self.enable_evm
                        },
                        "lighting": self.light_ctrl.get_state(),
                        "measurement_active": self.measurement_active,
                        "diagnostics": self.cam_ctrl.get_diagnostics(),
                    }

                    if compute_sig and is_ready:
                        state["results"] = {
                            "GREEN": r_res,
                            "CHROM": c_res,
                            "POS": p_res
                        }
                        last_sig_update = now
                        self.force_compute = False
                    else:
                        state["results"] = None

                    state["frame_original"] = self.encode_frame(frame)
                    state["frame_amplified"] = self.encode_frame(amplified_frame) if self.enable_evm else None

                    try:
                        queue.put_nowait(state)
                    except asyncio.QueueFull:
                        try:
                            queue.get_nowait()
                            queue.put_nowait(state)
                        except:
                            pass
                            
                    last_ui_update = now

                await asyncio.sleep(0.001)

        finally:
            self.cap.release()
            self.is_running = False
            print("Camera released")

    def stop(self):
        self.is_running = False
