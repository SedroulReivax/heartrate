import time

class LightController:
    def __init__(self):
        self.mode = "OFF"
        self.color = "WHITE"
        self.state = "IDLE" # IDLE, STARTING, MEASURING
        self.stabilization_time = 0.0
        
    def set_illumination(self, mode, color="WHITE"):
        """
        mode: 'OFF', 'SCREEN', 'EXTERNAL'
        color: 'WHITE', 'GREEN'
        """
        self.mode = mode
        self.color = color
        self.state = "STARTING"
        # Delay for stabilization
        self.stabilization_time = time.time() + 1.0 # 1 second stabilization
        
    def check_stabilization(self):
        if self.state == "STARTING":
            if time.time() >= self.stabilization_time:
                self.state = "MEASURING"
                return True # Indicates we just stabilized
        return False
        
    def get_state(self):
        return {
            "mode": self.mode,
            "color": self.color,
            "state": self.state
        }
