from ctypes import windll
import time
from pynput.mouse import Button, Controller
import win32api, win32con

timeBeginPeriod = windll.winmm.timeBeginPeriod #new
timeBeginPeriod(1) #new

mouse = Controller()

countdown = 2
how_long = 10 #s
how_many = 600 #clicks

for i in range(countdown):
    print(countdown-i)
    time.sleep(1)

ellapsed = 0
n_click = 0

start = time.time()

for c in range(how_many):
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0,0,0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0,0,0)
       

# mouse.click(button=Button.left, count=how_many)
# for c in range(how_many):
#     mouse.click(button=Button.left)
#     n_click+=1

ellapsed=time.time()-start
print(f'CPS: {round(how_many/ellapsed, 2)}')
pass
# while ellapsed <= how_long:
#     mouse.click(button=Button.left)
#     n_click+=1
#     ellapsed=time.time()-start
