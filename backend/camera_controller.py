import cv2

class CameraController:
    def __init__(self, cap):
        self.cap = cap

    def _set_and_verify(self, prop, value, name):
        self.cap.set(prop, value)
        actual = self.cap.get(prop)
        if actual == -1.0 or actual == 0.0 and value != 0.0: # 0.0 sometimes means unsupported if we didn't request 0
            status = "UNSUPPORTED"
        elif abs(actual - value) < 0.01:
            status = "LOCKED"
        else:
            status = "FAILED/DIFFERENT"
        return {"requested": value, "actual": actual, "status": status}

    def configure_fps(self, target_fps):
        res = self._set_and_verify(cv2.CAP_PROP_FPS, target_fps, "FPS")
        actual = self.cap.get(cv2.CAP_PROP_FPS)
        return actual if actual > 0 else target_fps

    def _format_diag(self, prop):
        val = self.cap.get(prop)
        if val == -1.0:
            return "UNSUPPORTED"
        return f"{val:.2f}"

    def get_diagnostics(self):
        return {
            "fps": self.cap.get(cv2.CAP_PROP_FPS),
            "auto_exposure": self._format_diag(cv2.CAP_PROP_AUTO_EXPOSURE),
            "exposure": self._format_diag(cv2.CAP_PROP_EXPOSURE),
            "auto_focus": self._format_diag(cv2.CAP_PROP_AUTOFOCUS),
            "focus": self._format_diag(cv2.CAP_PROP_FOCUS),
            "auto_wb": self._format_diag(cv2.CAP_PROP_AUTO_WB),
            "white_balance": self._format_diag(cv2.CAP_PROP_WB_TEMPERATURE),
            "gain": self._format_diag(cv2.CAP_PROP_GAIN)
        }

    def apply_manual_settings(self):
        results = {}
        results["auto_exposure"] = self._set_and_verify(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25, "Auto Exposure")
        results["auto_focus"] = self._set_and_verify(cv2.CAP_PROP_AUTOFOCUS, 0.0, "Auto Focus")
        results["auto_wb"] = self._set_and_verify(cv2.CAP_PROP_AUTO_WB, 0.0, "Auto WB")
        
        results["exposure"] = self._set_and_verify(cv2.CAP_PROP_EXPOSURE, -5.0, "Exposure")
        results["focus"] = self._set_and_verify(cv2.CAP_PROP_FOCUS, 0.0, "Focus")
        results["gain"] = self._set_and_verify(cv2.CAP_PROP_GAIN, 0.0, "Gain")
        
        for k, v in results.items():
            print(f"Camera Config [{k}]: requested={v['requested']}, actual={v['actual']}, status={v['status']}")
            
        return results
