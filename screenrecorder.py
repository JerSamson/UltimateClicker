from threading import Lock
from singleton import Singleton
import dxcam

class ScreenRecorder(metaclass=Singleton):
    def __init__(self) -> None:
        self.cam = dxcam.create()
        self.lock = Lock()

    def get_screen(self, region=None, caller=''):
        with self.lock:
            val = None
            print(f'DEBUG - screenrecorder.get_screen() - LOCK ACQUIRED {"by " + caller if caller is not None else ""} <|><|><|><|>')
            if region is None:
                val = self.cam.grab()
            else:
                val = self.cam.grab(region=region)

            print(f'DEBUG - screenrecorder.get_screen() - LOCK RELEASED by {"by " + caller if caller is not None else ""} <><><><><>')
        return val