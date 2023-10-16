from pynput.mouse import Listener
import win32api, win32con

class MouseTracker(object):
    _instance = None

    def __init__(self):
        raise RuntimeError('Call instance() instead')
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            print('Creating new instance')
            cls._instance = cls.__new__(cls)
            # Put any initialization here.
        return cls._instance
    
    def on_move(self, x, y):
        self.x = x
        self.y = y 
        if self.stop_on_move and (x,y) not in self.targets:
            self.active = False
            self.listener.stop()
        
    def on_scroll(self, x, y, dx, dy):
        self.active = False
        self.listener.stop()

    def on_click(self, x, y, button, pressed):
        if self.setting_targets and pressed:
            a = getpixelcolor.average(x, y, 5, 5)
            if(a == (12, 12, 12)):
                print("I assume this click was the terminal...")
                return
            self.nb_targets+=1
            Thread(target=self.wait_for_color_acquisition, args=(x, y)).start()
        elif pressed:
            self.nb_clicks+=1