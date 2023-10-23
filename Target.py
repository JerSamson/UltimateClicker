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
import pyautogui
# from pynput import mouse
from pynput.mouse import Button, Controller
from pynput.mouse import Controller, Button
from DetectionMode import detectionMode
from RepeatedTimer import RepeatedTimer
from simple_pid import PID

from numba import jit, cuda
import numpy as np

import mouse
def click_mouse(x, y, button):
    mouse.move(x, y, absolute=True)
    mouse.click(button=button)

pyautogui.PAUSE = 0

IMAGE_SIZE_X = 150
IMAGE_SIZE_Y = 30

class BaseTarget(object):
    def __init__(self, x, y, info_freq=0, active=False):
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
        self.type_priority = {
            TrackerTarget :  100,
            IdleTarget    :  1000,
            FastTarget    :  5000
        }
        self.priority_mode = 'lowest_first'
        self.priority = 0

    def __lt__(self, target):
        return self.priority < target.priority

    def __eq__(self, __value: object) -> bool:
        return self.x == __value.x and self.y == __value.y and type(self) == type(__value)

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

    def start(self):
        self.active=True
        self.handled=False
        if self.info_freq > 0:
            self.infoTask = RepeatedTimer(self.info_freq, self.info, name=f'InfoTarget{self.targetid}')
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

    def get_ref_area(self):
        try:
            res = pyautogui.size()
            x1 = self.x - IMAGE_SIZE_X if self.x > IMAGE_SIZE_X else 0
            x2 = self.x + IMAGE_SIZE_X if self.x + IMAGE_SIZE_X < res[0] else res[0]
            y1 = self.y - IMAGE_SIZE_Y if self.y > IMAGE_SIZE_Y else 0
            y2 = self.y + IMAGE_SIZE_Y if self.y + IMAGE_SIZE_Y < res[1] else res[1]

            im=ImageGrab.grab(bbox=(x1, y1, x2, y2))
            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())
        except Exception as e:
            print(f'ERROR - IDLE - get_ref_area ({e})')
            self.ref_area = None
            pass # Minor repercussions

    def check_trigger(self):
        pass

    def handle(self):
        if self.active and not self.handled:
            self.click()
            self.handled=True
            return True
        else:
            self.handled=False
            return False

class FastTarget(BaseTarget):
    def __init__(self, x, y, info_freq=0, active=False):
        BaseTarget.__init__(self, x, y, info_freq, active)
        self.delay = 0.0001
        self.init_delay = self.delay
        self.most_efficient_delay = self.delay
        self.first_click_time = 0
        self.cps          = 0
        self.avg_cps      = 0
        self.n_cps_sample = 0
        self.highest_cps  = 0
        self.target_cps   = 0
        self.last_handle  = time.time()
        self.last_nb_clicks = 0
        self.cps_history    = []
        self.actual_timestamps = []
        self.max_history_len = 60
        self.pid = PID(-0.00000025, -0.000025, 0, output_limits=(0,1))
        self.last_cps_time = 0
        self.cps_compute_freq = 0.1
        self.start_time       = time.time()
        self.get_ref_area()

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
            if self.target_cps > 0:
                self.pid.setpoint = self.target_cps
                self.pid.output_limits = (0.5/self.target_cps, 1)
        # self.nb_clicks = self.nb_clicks + 1
        return super().click()

    def get_ref_area(self):
        try:
            res = pyautogui.size()
            x1 = self.x - IMAGE_SIZE_X if self.x > IMAGE_SIZE_X else 0
            x2 = self.x + IMAGE_SIZE_X if self.x + IMAGE_SIZE_X < res[0] else res[0]
            y1 = self.y - IMAGE_SIZE_Y if self.y > IMAGE_SIZE_Y else 0
            y2 = self.y + IMAGE_SIZE_Y if self.y + IMAGE_SIZE_Y < res[1] else res[1]

            im=ImageGrab.grab(bbox=(x1, y1, x2, y2))
            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())

        except Exception as e:
            print(f'ERROR - FAST - get_ref_area ({e})')
            self.ref_area = None
            pass # Minor repercussions

    def stop(self):
        self.cps = 0
        self.avg_cps = 0
        self.n_cps_sample = 0
        self.first_click_time = 0
        self.cps_history.clear()
        return super().stop()

    def start(self):
        self.cps = 0
        self.avg_cps = 0
        self.n_cps_sample = 0
        self.first_click_time = 0
        self.cps_history.clear()
        return super().start()

    def info(self):
        if self.active and self.enabled:
            os.system('cls')
            now = time.time()
            print(f'\rTotal time:\t{int(now-self.start_time)}s')
            print(f'\rTotal clicks:\t{self.times_clicked} clicks')
            print(f'\rCPS:\t\t{int(self.cps)}cps')
            # print(f'\rCPS_t:\t\t{int(self.cps_theo)}cps')
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

            if time.time() - self.last_cps_time > self.cps_compute_freq:
                self.update_cps()
                # self.tweak_delay()

            self.last_handle = time.time()

            return True
        else:
            return False

    def tweak_delay(self):
        if self.cps > self.highest_cps:
            self.delay *= 0.999
        else:
            self.delay = self.most_efficient_delay#*(self.cps_theo/self.cps)

    def normalize_timestamp(self, ts):
        if len(self.cps_history) > 0:
            min_cps_timestamp = min([entry[2] for entry in self.cps_history])
            # min_cps_timestamp = min([entry for entry in self.actual_timestamps])
        else:
            min_cps_timestamp = time.time()

        relative_timestamp = int(round((ts - min_cps_timestamp), 3)*1000)
        return relative_timestamp

    def update_cps(self):
        if self.first_click_time == 0:
            return

        now = time.time()
        self.cps = math.ceil((self.times_clicked - self.last_nb_clicks)/(now - self.last_cps_time))
        self.last_cps_time = now
        self.last_nb_clicks= self.times_clicked

        actual_timestamp = time.time()
        relative_timestamp = self.normalize_timestamp(actual_timestamp)

        # print(f'INFO - FASTTARGET - Relative Timestamp: {relative_timestamp}')

        if len(self.cps_history) >= self.max_history_len:
            self.cps_history.pop(0)
            for entry in self.cps_history:
                entry[0] = self.normalize_timestamp(entry[2])

        self.cps_history.append([relative_timestamp, self.cps, actual_timestamp])

        if self.cps > self.highest_cps:
            self.highest_cps = self.cps
            self.most_efficient_delay = self.delay

        if self.times_clicked > 100:
            self.approxCpsAverage(self.cps)

        if self.target_cps > 0:
            self.delay = self.pid(self.cps)



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
        self.last_handle = time.time()
        self.last_color_trigger = None
        self.delay_after_handle_2_trigger = 1
        self.tolerance = 5

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

    def get_ref_area(self):
        try:
            res = pyautogui.size()
            x1 = self.x - IMAGE_SIZE_X if self.x > IMAGE_SIZE_X else 0
            x2 = self.x + IMAGE_SIZE_X if self.x + IMAGE_SIZE_X < res[0] else res[0]
            y1 = self.y - IMAGE_SIZE_Y if self.y > IMAGE_SIZE_Y else 0
            y2 = self.y + IMAGE_SIZE_Y if self.y + IMAGE_SIZE_Y < res[1] else res[1]

            im=ImageGrab.grab(bbox=(x1, y1, x2, y2))

            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            self.ref_area = base64.b64encode(buffer.getvalue())
        except Exception as e:
            print(f'ERROR - TRACKER - get_ref_area ({e})')
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

        if time.time() - self.last_handle < self.delay_after_handle_2_trigger:
            print(f'WARN - TARGET[{self.targetid}] - Too soon after handling to check trigger to avoid capturing the cursor. Skipping')
            return False

        if not self.is_ready():
            raise Exception(f'Tried to check trigger before ref was acquired (TARGET[{self.targetid}])')

        start = time.time_ns()

        old_value = self.triggered
        cur_color = self.get_color()

        if cur_color == (30, 30, 30):
            print('THATS MY CURSOR BITCH STOP STOP')
            return False

        if self.mode == detectionMode.same:
            self.triggered = self.compare_color(cur_color)
        elif self.mode in [detectionMode.different, detectionMode.change]:
            self.triggered = not self.compare_color(cur_color)
        else:
            raise Exception('Unsupported trigger mode')

        if (not old_value and self.triggered): # Has become triggered
            print(f'INFO - TARGET[{self.targetid}] has triggered. now:{cur_color} ref:{self.color}')
            self.handled = False
            # print(f'Target {self.targetid} triggered.\n\tcur:{cur_color} og:{self.color}')

        if self.triggered:
            self.last_color_trigger = cur_color
        else:
            self.handled = True

        # print(f'INFO - TARGET[{self.targetid}] - Checked trigger in {int((time.time_ns()-start)/1000000)}ms')

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
            print(f'INFO - TARGET[{self.targetid}] - Would have triggered with lower tolerance (diff {dTotal})')

        return same

    def handle(self):
        if self.active and self.enabled and not self.handled:
            self.click()
            if self.mode == detectionMode.change:
                self.bg_color_acquisition()
            print(f'INFO - Handled Target {self.targetid}')
            self.handled=True
            self.triggered = False
            self.last_handle = time.time()
            return True
        else:
            err = 'inactive' if not self.active else 'disabled' if not self.enabled else 'already handled'
            print(f'ERROR - TARGET - Could not handle (Target {err})')
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