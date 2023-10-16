import win32api, win32con
import time
import os
import math
from pynput.mouse import Listener
from threading import Thread, Timer
import getpixelcolor
from enum import Enum

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

class detectionMode(Enum):
    different = 1
    same      = 2
    change    = 3

class clicker():
    def __init__(self) -> None:
        self.idle_delay = 120

        self.nb_clicks   = 0
        self.nb_clicks_theo = 0
        self.last_nb_clicks_theo = 0
        self.last_nb_clicks = 0
        self.last_cps_time = None
        self.first_click_time = 0
        self.most_efficient_delay = 1
        self.highest_cps = 0
        self.start       = time.time()

        self.cps         = 0
        self.fast_delay  = 0.0001

        self.zone_area = 5 #pixel

        self.active = True
        self.stop_on_move = True

        self.single_target = None

        self.targets = []
        self.nb_targets = 0
        self.target_mode = detectionMode.different
        self.acquisition_min_dist = 300
        self.check_for_targets = False
        self.setting_targets = False

        self.x = 0
        self.y = 0 



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

# =-=-=-=-= MODES =-=-=-=-=

    def idle_presence(self):
        self.last_click = time.time()
        self.click(self.single_target[0], self.single_target[1])
        time.sleep(0.5)
        self.click(self.single_target[0], self.single_target[1])

    def fast_click(self):
        self.last_cps_time = time.time()
        rt = RepeatedTimer(0.1, self.update_cps)
        while self.active:
            self.click(self.single_target[0], self.single_target[1])
            self.nb_clicks_theo += 1

            time.sleep(self.fast_delay)
        rt.stop()

    def detect_color_change(self):
        while self.active:
            if self.check_for_targets:
                for tar in self.targets:
                    cur_avg = getpixelcolor.average(tar[0][0], tar[0][1], self.zone_area, self.zone_area)
                    init_avg = tar[1]

                    if tar[2] == detectionMode.same:
                        if cur_avg == init_avg:
                            self.click(tar[0][0], tar[0][1])
                    elif tar[2] == detectionMode.different:
                        if cur_avg != init_avg:
                            self.click(tar[0][0], tar[0][1])
                    elif tar[2] == detectionMode.change:
                        if cur_avg != init_avg:
                            self.click(tar[0][0], tar[0][1])
                            self.targets.remove(tar)
                            self.targets.append((tar[0], cur_avg, tar[2]))
                            time.sleep(0.5)
            time.sleep(0.1)
            
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
# =-=-=-=-= INFO =-=-=-=-=
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

    def idle_info(self):
        os.system('cls')
        print(f'Total time:\t{int(time.time()-self.start)}s')
        print(f'Total clicks:\t{self.nb_clicks} clicks')
        print(f'Next click in:\t{int(math.ceil(self.idle_delay - (time.time() - self.last_click)))}s')

    def fast_info(self):
        os.system('cls')
        print(f'\rTotal time:\t{int(time.time()-self.start)}s')
        print(f'\rTotal clicks:\t{self.nb_clicks} clicks')
        print(f'\rCPS:\t\t{int(self.cps)}cps')
        print(f'\rCPS_t:\t\t{int(self.cps_theo)}cps')
        print(f'avg cps:\t{int(self.nb_clicks/(time.time()-self.start))}cps')
        print(f'\nhighest cps:{int(self.highest_cps)}s')

        print(f'\rDelay:\t\t{round(self.fast_delay*1000,5)}ms')
        print(f'\nmost efficient delay:{round(self.most_efficient_delay*1000,5)}s')


# =-=-=-=-= CALLBACKS =-=-=-=-=

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


# =-=-=-=-= LISTENER =-=-=-=-=

    def click_listener(self):
        with Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll) as self.listener:
            self.listener.join()

    def run(self):
        mode = input('1: idle\n2: fast\n3: Target\n4: Targets + Fast\n')
        os.system('cls')

        cmd = ""
        while cmd != 'n':
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
            os.system('cls')
            cmd = input('Resume? (y/n)')
# =-=-=-=-= MAIN =-=-=-=-=

if __name__ == '__main__':
    c = clicker()
    
    c.run()
