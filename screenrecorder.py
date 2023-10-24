from singleton import Singleton
import dxcam

class ScreenRecorder(metaclass=Singleton):
    def __init__(self) -> None:
        self.cam = dxcam.create()
        pass

    def get_screen(self, region=None):
        if region is None:
            return self.cam.grab()
        else:
            return self.cam.grab(region=region)