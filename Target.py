import base64
import io
import os
import time
import math
from enum import Enum
from threading import Thread
import getpixelcolor
import win32api, win32con
import pyscreenshot as ImageGrab

from DetectionMode import detectionMode
from RepeatedTimer import RepeatedTimer

IMAGE_SIZE_X = 150
IMAGE_SIZE_Y = 50

class BaseTarget(object):
    def __init__(self, x, y, info_freq=0, active=False):
        self.x = x
        self.y = y
        self.info_freq = info_freq
        self.active=active
        self.triggered=False
        self.handled=False
        self.targetid=-1

    def is_ready(self):
        raise NotImplementedError()

    def pos(self):
        return (self.x, self.y)

    def click(self):
        win32api.SetCursorPos((self.x,self.y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,self.x,self.y,0,0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,self.x,self.y,0,0)
    
    def stop(self):
        self.active=False
        if self.infoTask is not None:
            self.infoTask.stop()

    def start(self):
        self.active=True
        if self.info_freq > 0:
            self.infoTask = RepeatedTimer(self.info_freq, self.info)
        else: self.infoTask = None

    def info(self):
        raise NotImplementedError()

    def check_trigger(self):
        raise NotImplementedError()

    def handle(self):
        raise NotImplementedError()
    
class IdleTarget(BaseTarget):
    def __init__(self, x, y, delay):
        BaseTarget.__init__(self, x, y)
        self.delay = delay
        
    def is_ready(self):
        return True

    def info(self):
        if self.active:
            os.system('cls')
            print(f'Total time:\t{int(time.time()-self.start)}s')
            print(f'Total clicks:\t{self.nb_clicks} clicks')
            print(f'Next click in:\t{int(math.ceil(self.idle_delay - (time.time() - self.last_click)))}s')

    def check_trigger(self):
        pass

    def handle(self):
        if self.active and not self.handled:
            self.handled=True
            self.click()
    
class FastTarget(BaseTarget):
    def __init__(self, x, y, info_freq=0, active=True):
        BaseTarget.__init__(self, x, y, info_freq, active)
        self.delay = 0.0001
        self.most_efficient_delay = self.delay
        
        self.cps         = 0
        self.cps_theo    = 0
        self.highest_cps = 0

        self.nb_clicks      = 0
        self.last_nb_clicks = 0

        self.nb_clicks_theo = 0
        self.last_nb_clicks_theo = 0

        self.start       = time.time()

    def is_ready(self):
        return True

    def info(self):
        if self.active:
            os.system('cls')
            print(f'\rTotal time:\t{int(time.time()-self.start)}s')
            print(f'\rTotal clicks:\t{self.nb_clicks} clicks')
            print(f'\rCPS:\t\t{int(self.cps)}cps')
            print(f'\rCPS_t:\t\t{int(self.cps_theo)}cps')
            print(f'avg cps:\t{int(self.nb_clicks/(time.time()-self.start))}cps')
            print(f'\nhighest cps:{int(self.highest_cps)}s')

            print(f'\rDelay:\t\t{round(self.delay*1000,5)}ms')
            print(f'\nmost efficient delay:{round(self.most_efficient_delay*1000,5)}s')

    def check_trigger(self):
        return False

    def handle(self):
        if self.active:
            self.click()
            time.sleep(self.delay)
    
    def tweak_delay(self):
        if (self.cps_theo - self.cps) <= 5:
            self.fast_delay *= 0.999
        else:
            self.fast_delay = self.most_efficient_delay*(self.cps_theo/self.cps) 
    
    def update_cps(self):
        if self.first_click_time == 0:
            return
        
        self.cps = (self.nb_clicks - self.last_nb_clicks)/(time.time() - self.last_cps_time)
        self.cps_theo = (self.nb_clicks_theo - self.last_nb_clicks_theo)/(time.time() - self.last_cps_time)
        self.last_cps_time = time.time()
        self.last_nb_clicks= self.nb_clicks
        self.last_nb_clicks_theo = self.nb_clicks_theo
        if self.cps > self.highest_cps:
            self.highest_cps = self.cps
            self.most_efficient_delay = self.fast_delay
        self.tweak_delay()


class TrackerTarget(BaseTarget):
    def __init__(self, x, y, zone_area, mode, mindist = 300, info_freq=False, active=True):
        BaseTarget.__init__(self, x, y, info_freq, active)
        self.zone_area = zone_area
        self.mode = mode
        
        self.ref_area = None
        self.waiting_acquisition = False
        self.acquisition_min_dist = mindist
        self.acquired = False
        self.color = None

        self.bg_color_acquisition()

    def is_ready(self):
        return self.acquired
    
    def get_color(self):
        return getpixelcolor.average(self.x, self.y, self.zone_area, self.zone_area)

    def color_acquisition(self):
        x,y = win32api.GetCursorPos()
        while (abs(self.x-x) <= self.acquisition_min_dist and abs(self.y-y) <= self.acquisition_min_dist):
            time.sleep(0.2)
            x,y = win32api.GetCursorPos()

        # Get ref area
        im=ImageGrab.grab(bbox=(self.x - IMAGE_SIZE_X, self.y - IMAGE_SIZE_Y, self.x + IMAGE_SIZE_X, self.y + IMAGE_SIZE_Y))
        buffer = io.BytesIO()
        im.save(buffer, format='PNG')
        im.close()
        self.ref_area = base64.b64encode(buffer.getvalue())

        self.color = self.get_color()
        self.acquired = True        
        self.waiting_acquisition = False

    def bg_color_acquisition(self):
        self.waiting_acquisition = True
        self.acquired = False
        Thread(target=self.color_acquisition, daemon=True).start()

    def check_trigger(self):
        if not self.is_ready():
            return False
        
        triggered = False

        if self.mode == detectionMode.same:
            triggered = self.color == self.get_color()
            self.handled = False
        elif self.mode in [detectionMode.different, detectionMode.change]:
            triggered = self.color != self.get_color()
        else:
            raise Exception('Unsupported trigger mode')
        
        self.handled = triggered
        return triggered        
    
    def info(self):
        if self.active:
            pass


    def handle(self):
        if self.active and not self.handled:
            self.click()
            if self.mode == detectionMode.change:
                self.bg_color_acquisition()
            self.handled=True
