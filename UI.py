from threading import Thread
import PySimpleGUI as sg
from DetectionMode import detectionMode
from pynput.mouse import Listener
import getpixelcolor
from ClickQueue import ClickQueue
from Target import *

SET_TARGET_BTN      = '-SET TARGETS-'
MODE_SAME_BTN       = '-SAME-'
MODE_DIFF_BTN       = '-DIFF-'
MODE_CHANGE_BTN     = '-CHANGE-'
COLOR_BTN           = '-COLOT-'
CLICK_BTN           ='-CLICK-'
FAST_TRACK_BTN      ='-FASTTRACK-'

TARGET_TABLE        = '-TARGETS-'

ENABLED_COLOR       = ('black', 'green')
DISABLED_COLOR      = ('black', 'red')

COLOR_PREVIEW_SIZE  = (10,2)

def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def text_color_for_bg(r,g,b):
    return '#000000' if (r*0.299 + g*0.587 + b*0.114) > 186 else '#ffffff'

class App:

    def __init__(self) -> None:
        
        self.click_listener_thread = None
        self.setting_targets = False
        self.targets = []
        self.mode = detectionMode.undefined

        self.aborted = False
        self.running = False
        self.queue = ClickQueue()

        self.tab_size_x = 50
        self.tab_size_y = 1

        self.cur_x = 0
        self.cur_y = 0

        # =========================== IDLE TAB ===========================
        idle_tab=[[sg.Text('IDLE',  size=(self.tab_size_x, self.tab_size_y))]]

        # =========================== FAST TAB ===========================
        fast_tab=[[sg.Text('FAST',  size=(self.tab_size_x, self.tab_size_y))]]

        # =========================== TRACKER TAB ===========================

        toprow = ['id', 'type', 'pos']
        rows = []

        target_table = sg.Table(values=rows, headings=toprow,
        auto_size_columns=True,
        display_row_numbers=False,
        justification='center', key=TARGET_TABLE,
        selected_row_colors='red on yellow',
        enable_events=True,
        expand_x=True,
        expand_y=True,
        enable_click_events=True)

        track_tab=[
            [sg.Text('TRACK' ,  size=(self.tab_size_x, self.tab_size_y))],
            [sg.Button('Set Targets', key=SET_TARGET_BTN, button_color = DISABLED_COLOR),
            sg.VSeparator(),
            sg.Button('same', key=MODE_SAME_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('diff', key=MODE_DIFF_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('change', key=MODE_CHANGE_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('fastClick', key=FAST_TRACK_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.VSeparator(),
            sg.Button('', key=COLOR_BTN, size=COLOR_PREVIEW_SIZE ,button_color = DISABLED_COLOR, visible=False),
            ],
            [target_table],
            [sg.Button('CLICK!', key=CLICK_BTN, visible=False)]
        ]


        # =========================== MAIN LAYOUT ===========================
        layout = [
            [sg.TabGroup([[
                sg.Tab('idle', idle_tab),
                sg.Tab('fast', fast_tab),
                sg.Tab('Track', track_tab)
            ]])],
        [sg.OK(), sg.Cancel()]
        ]

        # Create the window
        self.window = sg.Window("UltimateClicker", layout, location=(500,500))

    def nb_target_ready(self):
        i=0
        for tar in self.targets:
            if tar.is_ready():
                i+=1
        return i
    def are_targets_ready(self):
        for tar in self.targets:
            if not tar.is_ready():
                return False
        return True

    def update_buttons(self):
        self.window[MODE_SAME_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.same else DISABLED_COLOR)
        self.window[MODE_DIFF_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.different else DISABLED_COLOR)
        self.window[MODE_CHANGE_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.change else DISABLED_COLOR)
        self.window[FAST_TRACK_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.fast else DISABLED_COLOR)
        self.window[SET_TARGET_BTN].update(button_color = ENABLED_COLOR if self.setting_targets else DISABLED_COLOR)

        self.window[MODE_SAME_BTN].update(visible=self.setting_targets)
        self.window[MODE_DIFF_BTN].update(visible=self.setting_targets)
        self.window[MODE_CHANGE_BTN].update(visible=self.setting_targets)
        self.window[FAST_TRACK_BTN].update(visible=self.setting_targets)
        self.window[COLOR_BTN].update(visible=self.setting_targets and self.mode in [detectionMode.same, detectionMode.different, detectionMode.change])

    def update_target_table(self):
        self.window[CLICK_BTN].update(visible=len(self.targets) > 0)
        rows = []
        for tar in self.targets:
            if type(tar) is TrackerTarget:
                rows.append([str(tar.targetid), 'track: '+str(tar.mode).split('.')[1], str(tar.pos())])
            else:
                rows.append([str(tar.targetid), 'Fast Click', str(tar.pos())])
        self.window[TARGET_TABLE].update(values=rows)

    def is_click_inside_app(self, x, y):
        winPos = self.window.CurrentLocation()
        winSize = self.window.size
        x_outside = x < winPos[0] or x > winPos[0] + winSize[0]
        y_outside = y < winPos[1] or y > winPos[1] + winSize[1]
        return not x_outside and not y_outside
# =-=-=-=-= CALLBACKS =-=-=-=-=
    def click_listener(self):
        with Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll) as self.listener:
            self.listener.join()

    def on_move(self, x, y):
        if self.setting_targets:
            try:
                self.cur_x = x
                self.cur_y = y
                r,g,b = getpixelcolor.average(x, y, 5, 5)
                hex = rgb_to_hex(r,b,g)
                _hex = text_color_for_bg(r,g,b)
                self.window[COLOR_BTN].update(button_color = (_hex, hex), text=str((x, y)))
            except Exception as e:
                self.window[COLOR_BTN].update(button_color = 'red', text='error')
        elif self.running and (x,y) not in [(tar.x, tar.y) for tar in self.targets]:
            self.aborted = True

    def on_scroll(self, x, y, dx, dy):
        pass

    def on_click(self, x, y, button, pressed):
        if self.setting_targets and pressed:
            if self.is_click_inside_app(x, y):
                return
            if self.mode == detectionMode.same:
                tar = TrackerTarget(x, y, 5, detectionMode.same)
            elif self.mode == detectionMode.different:
                tar = TrackerTarget(x, y, 5, detectionMode.different)
            elif self.mode == detectionMode.change:
                tar = TrackerTarget(x, y, 5, detectionMode.different)
            elif self.mode == detectionMode.fast:
                tar = FastTarget(x, y, 1)
            self.add_target(tar)

    def set_mode(self, m):
        self.mode = m
        self.update_buttons()
# =-=-=-=-==-=-=-=-==-=-=-=-=

    def track_ready(self):
        while not self.are_targets_ready():
            time.sleep(0.2)
            self.window[CLICK_BTN].update(text=f'{self.nb_target_ready()}/{len(self.targets)}')
        self.window[CLICK_BTN].update(text='Click!')

    def run_queue(self):
        task=None
        self.setting_targets = False
        self.running = True
        self.aborted = False
        self.update_buttons()

        self.queue.start()
        while not self.aborted:
            print('Checking task...')
            task = self.queue.get_if_any()
            if task is None:
                if self.queue.has_fast_target():
                    print('Defaulting to fast target')
                    self.queue.fast_target.handle()
                    # time.sleep(2)
            else:
                print(f'Handling {type(task)}')
                task.handle()

        self.running = False
        print('No longer active')
        self.update_buttons()
        self.queue.stop()

    def add_target(self, tar):
        self.targets.append(tar)
        self.queue.add_target(tar)
        self.update_target_table()
        Thread(target=self.track_ready, daemon=True).start()

        # self.window[TARGET_TABLE].update(values=self.targets)

    def remove_target(self, tar):
        self.targets.remove(tar)
        self.queue.remove_target(tar)
        self.update_target_table()

    def run(self):
        # Create an event loop
        self.click_listener_thread = Thread(target=self.click_listener, daemon=True)
        self.click_listener_thread.start()
        event, values = self.window.read()
        while True:
            event, values = self.window.read()
            # End program if user closes window or
            # presses the OK button
            if event in [sg.WIN_CLOSED, 'CLOSE', 'OK']:
                break

            elif event == SET_TARGET_BTN:
                self.setting_targets = not self.setting_targets
                self.update_buttons()
 
            elif event == MODE_SAME_BTN:
                self.set_mode(detectionMode.same)

            elif event == MODE_DIFF_BTN:
                self.set_mode(detectionMode.different)

            elif event == MODE_CHANGE_BTN:
                self.set_mode(detectionMode.change)
            elif event == FAST_TRACK_BTN:
                self.set_mode(detectionMode.fast)
            elif event == CLICK_BTN:
                Thread(target=self.run_queue, daemon=True).start()

            elif '+CLICKED+' in event:
                self.remove_target(self.targets[event[2][0]])

        self.listener.stop()
        self.click_listener_thread.join()
        self.window.close()

if __name__ == '__main__':
    app = App()
    app.run()