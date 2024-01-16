import base64
import io
import os
import time
import math
from threading import Thread
from PIL import Image
import win32api
import pyscreenshot as ImageGrab
import pyautogui
# from pynput import mouse
from pynput.mouse import Button, Controller
from pynput.mouse import Controller, Button
from DetectionMode import detectionMode
from RepeatedTimer import RepeatedTimer
from simple_pid import PID
from event_graph import EventGraph, CpsEntry
from logger import Logger
from Settings import *

import numpy as np

import mouse

from screenrecorder import ScreenRecorder


def click_mouse(x, y, button):
    mouse.move(x, y, absolute=True)
    mouse.click(button=button)


IMAGE_SIZE_X = 125
IMAGE_SIZE_Y = 30

class BaseTarget(object):
    def __init__(self, x, y, info_freq=0, active=False, initial_screenshot=None):
        self.settings = Settings()
        self.x = x
        self.y = y
        self.info_freq = info_freq
        self.infoTask=None
        self.active=active
        self.triggered=False
        self.handled=False
        self.targetid=-1
        self.enabled = True
        self.times_clicked=0
        self.ref_area = None
        self.mouse = Controller()
        self.initial_screenshot = initial_screenshot
        self.type_priority = {
            TrackerTarget :  100,
            IdleTarget    :  1000,
            FastTarget    :  5000
        }
        self.priority_mode = 'lowest_first'
        self.priority = 0
        self.cam = ScreenRecorder()
        self.logger = Logger()

    def __lt__(self, target):
        return self.priority < target.priority

    def __eq__(self, __value: object) -> bool:
        return self.x == __value.x and self.y == __value.y and type(self) == type(__value)

    def get_ref_area(self, screenshot=None):
        try:
            res = pyautogui.size() #TODO change that
            x1 = self.x - IMAGE_SIZE_X if self.x > IMAGE_SIZE_X else 0
            x2 = self.x + IMAGE_SIZE_X if self.x + IMAGE_SIZE_X < res[0] else res[0]
            y1 = self.y - IMAGE_SIZE_Y if self.y > IMAGE_SIZE_Y else 0
            y2 = self.y + IMAGE_SIZE_Y if self.y + IMAGE_SIZE_Y < res[1] else res[1]

            if screenshot is None:
                # im=ImageGrab.grab(bbox=(x1, y1, x2, y2))
                screenshot=self.cam.get_screen(caller=f'Target[{self.targetid}]')
                im = Image.fromarray(screenshot, 'RGB').crop((x1, y1, x2, y2))

                # print('')
                # self.ref_area = base64.b64encode(im)
            else:
                # im=screenshot[x1:x2, y1:y2]
                im = Image.fromarray(screenshot, 'RGB').crop((x1, y1, x2, y2))
                
            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())

        except Exception as e:
            self.logger.error(f'TARGET{self.targetid} - get_ref_area failed ({e})')            
            self.ref_area = None
            pass # Minor repercussions

    def get_priority(self, tar):
        raise NotImplementedError()

    def is_ready(self):
        raise NotImplementedError()

    def pos(self):
        return (self.x, self.y)

    def click(self):

        if self.active and self.mouse.position != (self.x, self.y):
            win32api.SetCursorPos((self.x,self.y))

        self.mouse.click(button=Button.left)
        self.times_clicked+=1

    def stop(self):
        self.active=False
        self.handled=True
        if self.infoTask is not None:
            self.infoTask.stop()

        self.logger.info(f'TARGET[{self.targetid}] - Stop() called. Now Inactive.')            

    def start(self):
        self.active=True
        self.handled=False
        if self.info_freq > 0:
            self.infoTask = RepeatedTimer(self.info_freq, self.info, name=f'InfoTarget{self.targetid}')
        else: self.infoTask = None
        self.logger.info(f'TARGET[{self.targetid}] - Start() called. Now Active.')            

    def to_csv(self):
        raise NotImplementedError()

    def info(self):
        raise NotImplementedError()

    def check_trigger(self):
        raise NotImplementedError()

    def handle(self):
        raise NotImplementedError()

class IdleTarget(BaseTarget):
    def __init__(self, x, y, delay, initial_screenshot=None):
        BaseTarget.__init__(self, x, y, initial_screenshot=initial_screenshot)
        self.get_ref_area(initial_screenshot)
        self.delay = delay
        self.last_trigger = time.time()

    def is_ready(self):
        return True

    def info(self):
        if self.active:
            os.system('cls')
            print(f'Total time:\t{int(time.time()-self.start)}s')
            print(f'Total clicks:\t{self.times_clicked} clicks')
            print(f'Next click in:\t{int(math.ceil(self.idle_delay - (time.time() - self.last_click)))}s')

    def get_priority(self):
        if self.priority != 0:
            return self.priority
        else:
            p = self.type_priority[IdleTarget]
            return p

    def to_csv(self):
        return ['IDLE', self.x, self.y, '', self.times_clicked]

    def check_trigger(self):
        now = time.time()
        ellapsed = (now - self.last_trigger)
        if ellapsed > self.delay:
            self.last_trigger = now
            return True
        return False
    
    def handle(self):
        if self.active and not self.handled:
            self.click()
            self.handled=True
            return True
        else:
            self.handled=False
            return False

class FastTarget(BaseTarget):
    def __init__(self, x, y, info_freq=0, active=False, initial_screenshot=None):
        BaseTarget.__init__(self, x, y, info_freq, active, initial_screenshot)
        self.delay = 0.0001
        self.init_delay = self.delay
        self.most_efficient_delay = self.delay
        self.first_click_time = 0
        self.cps          = 0
        self.avg_cps      = 0
        self.n_cps_sample = 0
        self.highest_cps  = 0
        self.last_handle  = time.time()
        self.last_nb_clicks = 0
        self.original_delay = (1/self.settings.get(TARGET_CPS))
        self.pid = PID(self.settings.get(KP), self.settings.get(KI), self.settings.get(KD), output_limits=(0.00001,1), proportional_on_measurement = True)
        # self.pid = PID(-0.0000005, -0.000050, -0.00000000125, output_limits=(0.00001,1), proportional_on_measurement = True)
        self.last_cps_time = 0
        self.start_time    = time.time()
        self.eventgraph = EventGraph()
        self.last_target_cps = None
        self.get_ref_area(initial_screenshot)

    def approxCpsAverage(self, new_sample):
        self.n_cps_sample += 1
        avg = self.avg_cps
        avg -= avg / self.n_cps_sample
        avg += new_sample / self.n_cps_sample
        self.avg_cps = avg
        return self.avg_cps

    def is_ready(self):
        return True

    def get_priority(self):
        if self.priority != 0:
            return self.priority
        else:
            p = self.type_priority[FastTarget]
            return p

    def to_csv(self):
        return ['Fast', self.x, self.y, '', self.times_clicked]

    def click(self):
        if self.first_click_time == 0:
            self.first_click_time = time.time()
            
                # self.pid.output_limits = (0.5/self.settings.target_cps, 1)
        # self.nb_clicks = self.nb_clicks + 1
        return super().click()

    def stop(self):
        self.cps = 0
        self.avg_cps = 0
        self.n_cps_sample = 0
        self.first_click_time = 0
        return super().stop()

    def start(self):
        self.cps = 0
        self.avg_cps = 0
        self.n_cps_sample = 0
        self.first_click_time = 0

        self.pid.Kp = self.settings.get(KP)
        self.pid.Ki = self.settings.get(KI)
        self.pid.Kd = self.settings.get(KD)

        target_cps = self.settings.get(TARGET_CPS)
        if self.last_target_cps != target_cps:
            self.last_target_cps = target_cps
            if target_cps > 0:
                self.original_delay = (1/target_cps)
                self.pid.setpoint = target_cps
                self.pid.output_limits = (0, self.original_delay)

            self.pid.reset()
        return super().start()

    def info(self):
        if self.active and self.enabled:
            os.system('cls')
            now = time.time()
            print(f'\rTotal time:\t{int(now-self.start_time)}s')
            print(f'\rTotal clicks:\t{self.times_clicked} clicks')
            print(f'\rCPS:\t\t{int(self.cps)}cps')
            print(f'avg cps:\t{int(self.times_clicked/(now-self.start_time))}cps')
            print(f'\nhighest cps:{int(self.highest_cps)}s')

            print(f'\Initial Delay:\t\t{round(self.init_delay*1000,5)}ms')
            print(f'\rDelay:\t\t{round(self.delay*1000,5)}ms')
            print(f'\nmost efficient delay:{round(self.most_efficient_delay*1000,5)}s')

    def check_trigger(self):
        return False

    def handle(self):
        if self.active:

            self.click()

            if time.time() - self.last_cps_time > self.settings.get(CPS_UPDATE):
                self.update_cps()

            self.last_handle = time.time()

            if self.settings.get(TARGET_CPS) > 0:
                time.sleep(self.delay)

            return True
        else:
            return False

    def update_cps(self):
        if self.first_click_time == 0:
            return

        now = time.time()
        self.cps = math.ceil((self.times_clicked - self.last_nb_clicks)/(now - self.last_cps_time))
        self.last_cps_time = now
        self.last_nb_clicks= self.times_clicked

        self.eventgraph.add_cps_entry(CpsEntry(now, self.cps))

        if self.cps > self.highest_cps:
            self.highest_cps = self.cps
            self.most_efficient_delay = self.delay

        if self.times_clicked > 100:
            self.approxCpsAverage(self.cps)

        if self.settings.get(TARGET_CPS) > 0:
            pid_correction=self.pid(self.cps)
            self.delay = self.original_delay - pid_correction 
            self.logger.debug(f'FastTarget.update_cps - pid correction: {pid_correction}, delay:{self.delay}')
            if self.delay <= 0:
                self.delay = 0
                self.logger.warn('FastTarget.UpdateCPS - Had to clip delay to 0 s')            

class TrackerTarget(BaseTarget):
    def __init__(self, x, y, zone_area, mode, mindist = 300, info_freq=False, active=False, initial_screenshot=None):
        BaseTarget.__init__(self, x, y, info_freq, active, initial_screenshot)
        self.zone_area = zone_area
        self.mode = mode
        self.triggered = False
        self.waiting_acquisition = False
        self.acquisition_min_dist = mindist #TODO : Setting
        self.acquired = False
        self.color = None
        self.last_handle = time.time()
        self.last_color_trigger = None
        self.delay_after_handle_2_trigger = 0.5
        self.tolerance = 5
        self.priority = self.get_priority()
        self.bg_color_acquisition(initial_screenshot)
  
    def to_csv(self):
        return ['Tracker', self.x, self.y, int(self.mode), self.times_clicked]

    def get_priority(self):
        p = self.type_priority[TrackerTarget]
        if self.priority_mode == 'lowest_first':
            if self.mode in [detectionMode.different, detectionMode.same]:
                p -= self.y // 47
                p *= 3
            elif self.mode == detectionMode.change:
                p += self.x // 47 - self.type_priority[TrackerTarget]
        self.priority = p
        return p

    def is_ready(self):
        return self.acquired

    def get_color(self, screenshot=None):
        if screenshot is None:
            screenshot = np.array(ImageGrab.grab())
        img=Image.fromarray(screenshot, 'RGB').crop((int(self.x-self.zone_area/2), int(self.y-self.zone_area/2), int(self.x+self.zone_area/2), int(self.y+self.zone_area/2))).getcolors()
        return img

    def color_acquisition(self, screenshot=None, delay=None):
        self.logger.info(f'TARGET[{self.targetid}].color_acquisition() - Starting color acquisition thread')
        if delay is not None:
            time.sleep(delay)

        had_to_wait = False
        x,y = win32api.GetCursorPos()
        while (abs(self.x-x) <= self.acquisition_min_dist and abs(self.y-y) <= self.acquisition_min_dist):
            had_to_wait = True
            time.sleep(0.2)
            x,y = win32api.GetCursorPos()

        if had_to_wait or screenshot is None:
            screenshot = ScreenRecorder().get_screen()
        
        # Get ref area
        self.get_ref_area(screenshot=screenshot)

        self.color = self.get_color()
        self.acquired = True
        self.waiting_acquisition = False

    def bg_color_acquisition(self, screenshot=None, delay=None):
        self.waiting_acquisition = True
        self.acquired = False
        Thread(target=self.color_acquisition, daemon=True, name='bg_color_acquisition', args=[screenshot, delay]).start()

    def check_trigger(self, screenshot=None):

        if time.time() - self.last_handle < self.delay_after_handle_2_trigger:
            self.logger.warn(f'TARGET[{self.targetid}] - Too soon after handling to check trigger to avoid capturing the cursor. Skipping')            
            return False

        if not self.is_ready():
            raise Exception(f'Tried to check trigger before ref was acquired (TARGET[{self.targetid}])')

        start = time.time_ns()
        old_value = self.triggered
        cur_color = self.get_color(screenshot)

        if cur_color == (30, 30, 30):
            self.logger.warn(f'TARGET[{self.targetid}] - Ignoring trigger with color value (30,30,30)')            
            # print('THATS MY CURSOR BITCH STOP STOP')
            return False

        if self.mode == detectionMode.same:
            self.triggered = cur_color == self.color
            # self.triggered = self.compare_color(cur_color)
        elif self.mode in [detectionMode.different, detectionMode.change]:
            self.triggered = cur_color != self.color
            # self.triggered = not self.compare_color(cur_color)
        else:
            raise Exception('Unsupported trigger mode')

        if (not old_value and self.triggered): # Has become triggered
            self.logger.info(f'TARGET[{self.targetid}] has triggered.')            
            self.handled = False

        if self.triggered:
            self.last_color_trigger = cur_color
        else:
            self.handled = True

        self.logger.debug(f'TARGET[{self.targetid}] - Checked trigger in {int((time.time_ns()-start)/1000000)}ms')

        return self.triggered

    def info(self):
        if self.active:
            pass

    def compare_color(self, color):
        dR = abs(self.color[0] - color[0])
        dG = abs(self.color[1] - color[1])
        dB = abs(self.color[2] - color[2])
        dTotal = dR+dG+dB
        same = dTotal < self.tolerance

        if same and self.color != color:
            self.logger.info(f'TARGET[{self.targetid}] - Would have triggered with lower tolerance (diff {dTotal})')            

        return same

    def handle(self):
        if self.active and self.enabled and not self.handled:
            self.click()

            if self.mode == detectionMode.change:
                self.bg_color_acquisition(delay=1)

            self.logger.info(f'Handled Target {self.targetid}')            
            self.handled=True
            self.triggered = False
            self.last_handle = time.time()
            return True
        else:
            err = 'inactive' if not self.active else 'disabled' if not self.enabled else 'already handled'

            self.logger.error(f'TARGET - Could not handle (Target {err})')            
            return False

class GOLDENTARGET(BaseTarget):
    def __init__(self, x, y):
        super().__init__(x, y, 0, False)

    def get_priority(self):
        return -999

    def is_ready(self):
        return True

    def check_trigger(self):
        return True

    def handle(self):
        self.single_shot_triggered = True
        win32api.SetCursorPos((self.x,self.y))
        self.mouse.click(button=Button.left)
        self.times_clicked+=1
        self.handled = True