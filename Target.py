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
        self.handled=True
        self.targetid=-1
        self.enable = True
        self.times_clicked=0
        self.ref_area = None
        self.type_priority = {
            TrackerTarget :  100,
            IdleTarget    :  300,
            FastTarget    :  500
        }
        self.priority_mode = 'lowest_first'
        self.priority = 0

    def __lt__(self, target): 
        return self.priority < target.priority
         
    def get_priority(self, tar):
        raise NotImplementedError()
    
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
        self.handled=True
        if self.infoTask is not None:
            self.infoTask.stop()

    def start(self):
        self.active=True
        if self.info_freq > 0:
            self.infoTask = RepeatedTimer(self.info_freq, self.info)
        else: self.infoTask = None

    def to_csv(self):
        raise NotImplementedError()

    def info(self):
        raise NotImplementedError()

    def check_trigger(self):
        raise NotImplementedError()

    def handle(self):
        raise NotImplementedError()
    
class IdleTarget(BaseTarget):
    def __init__(self, x, y, delay):
        BaseTarget.__init__(self, x, y)
        self.get_ref_area()
        self.delay = delay
        
    def is_ready(self):
        return True

    def info(self):
        if self.active:
            os.system('cls')
            print(f'Total time:\t{int(time.time()-self.start)}s')
            print(f'Total clicks:\t{self.nb_clicks} clicks')
            print(f'Next click in:\t{int(math.ceil(self.idle_delay - (time.time() - self.last_click)))}s')
    
    def get_priority(self):
        if self.priority != 0:
            return self.priority
        else:
            p = self.type_priority[IdleTarget]
            return p
    
    def to_csv(self):
        return ['IDLE', self.x, self.y, '']

    def get_ref_area(self):
        try:
            im=ImageGrab.grab(bbox=(self.x - IMAGE_SIZE_X, self.y - IMAGE_SIZE_Y, self.x + IMAGE_SIZE_X, self.y + IMAGE_SIZE_Y))
            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())
        except Exception as e:
            print(e)
            self.ref_area = None
            pass # Minor repercussions

    def check_trigger(self):
        pass

    def handle(self):
        if self.active and not self.handled:
            self.handled=True
            self.click()
            self.times_clicked+=1
    
class FastTarget(BaseTarget):
    def __init__(self, x, y, info_freq=0, active=False):
        BaseTarget.__init__(self, x, y, info_freq, active)
        self.delay = 0.0001
        self.most_efficient_delay = self.delay
        self.first_click_time = 0
        self.cps         = 0
        self.cps_theo    = 0
        self.highest_cps = 0

        self.nb_clicks      = 0
        self.last_nb_clicks = 0

        self.nb_clicks_theo = 0
        self.last_nb_clicks_theo = 0
        self.get_ref_area()
        self.last_cps_time = 0
        self.cps_compute_freq = 1
        self.start_time       = time.time()

    def is_ready(self):
        return True

    def get_priority(self):
        if self.priority != 0:
            return self.priority
        else:
            p = self.type_priority[FastTarget]
            return p

    def to_csv(self):
        return ['Fast', self.x, self.y, '']

    def click(self):
        if self.first_click_time == 0:
            self.first_click_time = time.time()
        self.nb_clicks = self.nb_clicks + 1
        return super().click()

    def get_ref_area(self):
        try:
            im=ImageGrab.grab(bbox=(self.x - IMAGE_SIZE_X, self.y - IMAGE_SIZE_Y, self.x + IMAGE_SIZE_X, self.y + IMAGE_SIZE_Y))
            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())
        except Exception as e:
            print(e)
            self.ref_area = None
            pass # Minor repercussions

    def info(self):
        if self.active and self.enable:
            os.system('cls')
            print(f'\rTotal time:\t{int(time.time()-self.start_time)}s')
            print(f'\rTotal clicks:\t{self.nb_clicks} clicks')
            print(f'\rCPS:\t\t{int(self.cps)}cps')
            print(f'\rCPS_t:\t\t{int(self.cps_theo)}cps')
            print(f'avg cps:\t{int(self.nb_clicks/(time.time()-self.start_time))}cps')
            print(f'\nhighest cps:{int(self.highest_cps)}s')

            print(f'\rDelay:\t\t{round(self.delay*1000,5)}ms')
            print(f'\nmost efficient delay:{round(self.most_efficient_delay*1000,5)}s')

    def check_trigger(self):
        return False

    def handle(self):
        if self.active:
            self.click()
            self.times_clicked+=1
            time.sleep(self.delay)
            if time.time() - self.last_cps_time > self.cps_compute_freq:
                self.update_cps()
            # self.tweak_delay()

    def tweak_delay(self):
        if (self.cps_theo - self.cps) <= 5:
            self.delay *= 0.999
        else:
            self.delay = self.most_efficient_delay*(self.cps_theo/self.cps) 
    
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
            self.most_efficient_delay = self.delay
        self.tweak_delay()


class TrackerTarget(BaseTarget):
    def __init__(self, x, y, zone_area, mode, mindist = 300, info_freq=False, active=False):
        BaseTarget.__init__(self, x, y, info_freq, active)
        self.zone_area = zone_area
        self.mode = mode
        self.triggered = False
        self.waiting_acquisition = False
        self.acquisition_min_dist = mindist
        self.acquired = False
        self.color = None
        self.priority = self.get_priority()
        self.bg_color_acquisition()

    def to_csv(self):
        return ['Tracker', self.x, self.y, int(self.mode)]

    def get_priority(self):
        p = self.type_priority[TrackerTarget]
        if self.priority_mode == 'lowest_first':
            if self.mode in [detectionMode.different, detectionMode.same]: 
                p -= self.y // 71
            elif self.mode == detectionMode.change:
                p += self.x // 71
        self.priority = p
        return p

    def is_ready(self):
        return self.acquired
    
    def get_ref_area(self):
        try:
            im=ImageGrab.grab(bbox=(self.x - IMAGE_SIZE_X, self.y - IMAGE_SIZE_Y, self.x + IMAGE_SIZE_X, self.y + IMAGE_SIZE_Y))
            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())
        except Exception as e:
            print(e)
            self.ref_area = None
            pass # Minor repercussions

    def get_color(self):
        return getpixelcolor.average(self.x, self.y, self.zone_area, self.zone_area)

    def color_acquisition(self):
        x,y = win32api.GetCursorPos()
        while (abs(self.x-x) <= self.acquisition_min_dist and abs(self.y-y) <= self.acquisition_min_dist):
            time.sleep(0.2)
            x,y = win32api.GetCursorPos()

        # Get ref area
        self.get_ref_area()

        self.color = self.get_color()
        self.acquired = True        
        self.waiting_acquisition = False

    def bg_color_acquisition(self):
        self.waiting_acquisition = True
        self.acquired = False
        Thread(target=self.color_acquisition, daemon=True, name='bg_color_acquisition').start()

    def check_trigger(self):
        if not self.is_ready():
            self.triggered = False
            return False
        
        self.triggered = False

        if self.mode == detectionMode.same:
            self.triggered = self.color == self.get_color()
        elif self.mode in [detectionMode.different, detectionMode.change]:
            self.triggered = self.color != self.get_color()
        else:
            raise Exception('Unsupported trigger mode')
        
        # self.handled = self.handled and not self.triggered 

        return self.triggered        
    
    def info(self):
        if self.active:
            pass


    def handle(self):
        if self.active:
            self.click()
            self.times_clicked+=1
            if self.mode == detectionMode.change:
                self.bg_color_acquisition()
            self.handled=True

