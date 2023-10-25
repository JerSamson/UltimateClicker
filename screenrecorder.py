from threading import Lock
from singleton import Singleton
import dxcam

class ScreenRecorder(metaclass=Singleton):
    def __init__(self) -> None:
        self.cam = dxcam.create()
        self.lock = Lock()

    def get_screen(self, region=None):
        with self.lock:
            if region is None:
                return self.cam.grab()
            else:
                return self.cam.grab(region=region)