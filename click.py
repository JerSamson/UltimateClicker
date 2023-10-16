import win32api, win32con
import time
import os
from pynput.mouse import Listener
import getpixelcolor
from threading import Thread
import PySimpleGUI as sg

from DetectionMode import detectionMode
from RepeatedTimer import RepeatedTimer
from Target import *
from ClickQueue import ClickQueue
from queue import Queue


class clicker():
    def __init__(self) -> None:

        self.queue = ClickQueue()
        self.idle_delay = 120

        self.active = True
        self.stopped   = False
        self.stop_on_move = True

        self.x = 0
        self.y = 0 


    def add_target2Queue(self, tar):
        self.queue.add_target(tar)

    def stop(self):
        self.active = False

    def mode_str(self):
        return str(self.target_mode).split('.')[1]

    def wait_for_targets_ready(self):
        if self.targets.__len__() != self.nb_targets:
            print('Some targets were not yet acquired...')
        while self.targets.__len__() != self.nb_targets:
            time.sleep(1)

    def wait_for_color_acquisition(self, x, y):
        print('Waiting for acquisition...')
        while (abs(self.x-x) <= self.acquisition_min_dist and abs(self.y-y) <= self.acquisition_min_dist):
            time.sleep(0.5)
        self.targets.append(((x,y), getpixelcolor.average(x, y, self.zone_area, self.zone_area), self.target_mode))
        print(f'New target: ({x},{y}) - click when {self.mode_str()} - ({self.targets.__len__()} Total)\r')

    def countdown(self, ct_time):
        print(f'Starting in {ct_time}...')
        time.sleep(1)
        for i in range(ct_time-1):
            print(f'{ct_time-i-1}...\r')
            time.sleep(1)
        self.start = time.time()
        
    def tweak_delay(self):
        if (self.cps_theo - self.cps) <= 5:
            self.fast_delay *= 0.999
        else:
            self.fast_delay = self.most_efficient_delay*(self.cps_theo/self.cps) 

    def add_target(self, target, color=(0, 0, 0, 0), reverse=False):
        self.targets.append({target, color, reverse})



    def click(self, target):
        self.click(target[0], target[1])
    def click(self, x,y):
        if self.setting_targets:
            return
        
        win32api.SetCursorPos((x,y))

        if self.first_click_time == 0:
            self.first_click_time = time.time()
            self.last_cps_time = self.first_click_time

        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,x,y,0,0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,x,y,0,0)


            
    def click_color_change(self):
        self.stop_on_move = False
        self.setting_targets = True
        ans = input(f'Enter any key to stop recording targets\ntype [rev] to toggle detection type\nCurrent type: click when {self.mode_str()}\n')
        
        while ans in ['same', 'diff', 'change']:
            if ans == 'same': self.target_mode = detectionMode.same
            elif ans == 'diff': self.target_mode = detectionMode.different
            elif ans == 'change': self.target_mode = detectionMode.change
            ans = input(f'Current type: click when {self.mode_str()}')

        self.wait_for_targets_ready()
        self.setting_targets = False
        t = Thread(target=self.detect_color_change, daemon=True)

        t.start()

# =-=-=-=-= CALLBACKS =-=-=-=-=

    def on_move(self, x, y):
        self.x = x
        self.y = y 
        if self.stop_on_move and (x,y) not in [(tar.x, tar.y) for tar in self.queue.targets]:
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


# =-=-=-=-= LISTENER =-=-=-=-=

    def click_listener(self):
        with Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll) as self.listener:
            self.listener.join()

    def run_queue(self):
        task=None
        t = Thread(target=self.click_listener)
        t.start()
        while self.active:
            print('Checking task...')
            task = self.queue.get_if_any()
            if task is None:
                if self.queue.has_fast_target():
                    print('Defaulting to fast target')
                    self.queue.fast_target.handle()
                    time.sleep(2)
            else:
                print(f'Handling {type(task)}')
                task.handle()

        print('No longer active')
        self.queue.stop()
        t.join()

    def run(self):
        while self.active and not self.stopped:
            mode = input('1: idle\n2: fast\n3: Target\n4: Targets + Fast\n')
            os.system('cls')
            if mode == '1': # IDLE
                
                self.countdown(2)
                self.single_target = win32api.GetCursorPos()

                t = Thread(target=self.click_listener)
                t.start()
                
                rt1 = RepeatedTimer(1, self.idle_info)
                rt2 = RepeatedTimer(self.idle_delay, self.idle_presence)

                self.idle_presence()
                self.idle_info()
                t.join()
                
                while(self.active):
                    time.sleep(1)

                rt1.stop()
                rt2.stop()

            elif mode == '2': # FAST
                self.countdown(2)
                self.single_target = win32api.GetCursorPos()

                t = Thread(target=self.click_listener)
                t.start()

                rt1 = RepeatedTimer(1, self.fast_info)
                # rt2 = RepeatedTimer(100, self.stop)

                self.fast_click()
                time.sleep(0.01)
                self.fast_info()

                rt1.stop()
                # rt2.stop()

                t.join()

            elif mode == '3': # ZONE CHANGE
                t = Thread(target=self.click_listener)
                t.start()

                self.click_color_change()

                self.check_for_targets = True
                self.stop_on_move = True

                while(self.active):
                    time.sleep(1)
                t.join()

            elif mode == '4': # AUTO-CLICK + DETECT
                t = Thread(target=self.click_listener)
                t.start()

                self.click_color_change()

                self.countdown(5)
                self.check_for_targets = True
                self.single_target = win32api.GetCursorPos()
                self.stop_on_move = True
                self.fast_click()

                t.join()

# =-=-=-=-= MAIN =-=-=-=-=

# if __name__ == '__main__':
#     sg.Window(title="Hello World", layout=[[]], margins=(100, 50)).read()
    
#     c = clicker()
#     c.add_target2Queue(FastTarget(1000, 1000, info_freq=0))
#     c.add_target2Queue(TrackerTarget(1000, 1000, 5, detectionMode.change))
#     c.run_queue()
