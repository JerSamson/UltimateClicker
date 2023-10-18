import base64
import io
from threading import Thread, Timer
import PySimpleGUI as sg
from DetectionMode import detectionMode
from pynput.mouse import Listener
import getpixelcolor
from ClickQueue import ClickQueue
from Target import *
import pyscreenshot as ImageGrab
from PIL import ImageTk, Image
import cursor
import csv


SET_TARGET_BTN      = '-SET TARGETS-'
MODE_SAME_BTN       = '-SAME-'
MODE_DIFF_BTN       = '-DIFF-'
MODE_CHANGE_BTN     = '-CHANGE-'
COLOR_BTN           = '-COLOT-'
CLICK_BTN           ='-CLICK-'
FAST_TRACK_BTN      ='-FASTTRACK-'
CUR_IMAGE_KEY       ='-CURIMAGE-'
OG_IMAGE_KEY        ='-OGIMAGE-'
TARGET_TABLE        = '-TARGETS-'
DETAIL_ID           = '-DETAILID-'
TIMES_CLICKED       = '-NBCLICKS-'
SAVE_BTN            = '-SAVE-'
LOAD_BTN            = '-LOAD-'
CLEAR_BTN            = '-CLEAR-'
ENABLED_COLOR       = ('black', 'green')
DISABLED_COLOR      = ('black', 'red')
PATIENCE_SLIDER     = '-PATIENCE-'
COLOR_PREVIEW_SIZE  = (10,2)

#TODO: Priority Queue

def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def text_color_for_bg(r,g,b):
    return '#000000' if (r*0.299 + g*0.587 + b*0.114) > 186 else '#ffffff'

class App:

    def __init__(self) -> None:
        
        self.click_listener_thread = None
        self.setting_targets = False
        self.targets = []
        self.mode = detectionMode.same

        self.saves_directory = 'SavedTargets\\'
        self.zone_size = 10 

        self.selected_target = None

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

        # =========================== RIGHT CLICK MENU ===========================
        self.right_click_menu = ['&Right', ['Delete', 'Toggle']]



        # =========================== TRACKER TAB ===========================

        self.toprow = ['type', 'clicks', 'state', 'pos']

        treedata = sg.TreeData()
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])
        treedata.insert("", "Fast", "Fast", [])

        target_table=sg.Tree(data=treedata,
            headings=self.toprow,
            auto_size_columns=True,
            num_rows=20,
            col0_width=5,
            key=TARGET_TABLE,
            select_mode=sg.TABLE_SELECT_MODE_EXTENDED,
            show_expanded=True,
            enable_events=True,
            expand_x=True,
            expand_y=True,
            right_click_menu=self.right_click_menu,
            justification='center'
        )

        selection_buttons = [sg.Button('Set Targets', key=SET_TARGET_BTN, button_color = DISABLED_COLOR),
            sg.VSeparator(),
            sg.Button('same', key=MODE_SAME_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('diff', key=MODE_DIFF_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('change', key=MODE_CHANGE_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('fastClick', key=FAST_TRACK_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.VSeparator(),
            sg.Button('', key=COLOR_BTN, size=COLOR_PREVIEW_SIZE ,button_color = DISABLED_COLOR, visible=False),
            ]
        
        self.graph_cur = sg.Graph(canvas_size=(IMAGE_SIZE_X*2, IMAGE_SIZE_Y*2),
                graph_bottom_left=(-IMAGE_SIZE_X, -IMAGE_SIZE_Y),
                graph_top_right=(IMAGE_SIZE_X, IMAGE_SIZE_Y),
                enable_events=True,
                drag_submits=False, key=CUR_IMAGE_KEY)
        self.graph_og = sg.Graph(canvas_size=(IMAGE_SIZE_X*2, IMAGE_SIZE_Y*2),
                graph_bottom_left=(-IMAGE_SIZE_X, -IMAGE_SIZE_Y),
                graph_top_right=(IMAGE_SIZE_X, IMAGE_SIZE_Y),
                enable_events=True,
                drag_submits=False, key=OG_IMAGE_KEY)
        
        cur_frame = [self.graph_cur]
        og_frame = [self.graph_og]

        details=[
            sg.Frame('Current', [cur_frame]),
            sg.Frame('Original', [og_frame]),
            sg.Text(key=DETAIL_ID),
            ]

        track_tab=[
            [sg.Sizer(600,0)],
            selection_buttons,
            [sg.Slider(range=(0, 20), default_value=5,
                expand_x=True, enable_events=True,
                orientation='horizontal', key=PATIENCE_SLIDER)],
            [target_table],
            details,
            [sg.Button('CLICK!', key=CLICK_BTN, visible=False)]
        ]


        # =========================== MAIN LAYOUT ===========================
        layout = [
            [sg.TabGroup([[
                # sg.Tab('idle', idle_tab),
                # sg.Tab('fast', fast_tab),
                sg.Tab('Track', track_tab)
            ]])],
        [sg.OK(),
        sg.Cancel(),
        sg.Button(key=SAVE_BTN, button_text='SAVE'),
        sg.Button(key=LOAD_BTN, button_text='LOAD'),
        sg.Button(key=CLEAR_BTN, button_text='CLEAR')]
        ]
        font = ("Arial", 12)
        # Create the window
        self.window = sg.Window("UltimateClicker", layout, location=(900,500), font=font)

    def display_current(self):
        self.graph_cur.erase()
        cur = self.selected_target
        while cur == self.selected_target and self.selected_target is not None:
            try:
                self.draw_current()
                time.sleep(0.5)
            except Exception as e:
                print(f'display current failed: {e}')
                self.graph_cur.erase()
                break

    def load_targets(self, save_file):
        file_path = self.saves_directory + save_file
        with open(file_path, 'r') as file:
            csvreader = csv.reader(file)
            for row in csvreader:
                tar = None
                typ = row[0] 
                if typ == 'Tracker':
                    tar = TrackerTarget(int(row[1]), int(row[2]), self.zone_size, detectionMode(int(row[3])))
                elif typ == 'Fast':
                    tar = FastTarget(int(row[1]), int(row[2]))
                elif typ == 'Idle':
                    tar = IdleTarget(int(row[1]), int(row[2]))    
                if tar is not None:
                    self.add_target(tar)

    def save_targets(self, save_file):
        if len(self.targets) == 0:
            return
        
        file_path = self.saves_directory + save_file
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            for tar in self.targets:
                writer.writerow(tar.to_csv())

    def draw_current(self):
        try:
            im=ImageGrab.grab(
            bbox=(
                self.selected_target.x - IMAGE_SIZE_X,
                self.selected_target.y - IMAGE_SIZE_Y,
                self.selected_target.x + IMAGE_SIZE_X,
                self.selected_target.y + IMAGE_SIZE_Y))

            buffer = io.BytesIO()
            im.save(buffer, format='PNG')
            im.close()
            b64_str = base64.b64encode(buffer.getvalue())
            self.graph_cur.draw_image(data=b64_str, location=(-IMAGE_SIZE_X, IMAGE_SIZE_Y))
            if isinstance(self.selected_target, TrackerTarget):
                self.graph_cur.draw_circle((0,0), self.selected_target.zone_area//2, line_color='red', line_width=3)
            else:
                self.graph_cur.draw_line((-10,0), (10,0), color='red', width=3)
                self.graph_cur.draw_line((0,-10), (0,10), color='red', width=3)
        except Exception as e:
            print(e)
            pass

    def draw_og(self):
        self.graph_og.draw_image(data=self.selected_target.ref_area, location=(-IMAGE_SIZE_X, IMAGE_SIZE_Y))
        if isinstance(self.selected_target, TrackerTarget):
            self.graph_og.draw_circle((0,0), self.selected_target.zone_area//2, line_color='red', line_width=3)
        else:
            self.graph_og.draw_line((-10,0), (10,0), color='red', width=3)
            self.graph_og.draw_line((0,-10), (0,10), color='red', width=3)


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
        if self.setting_targets:
            cursor.set_cursor_circle()
        else:
            cursor.set_cursor_default()

    def update_target_table(self):
        self.window[CLICK_BTN].update(visible=len([en_tar for en_tar in self.targets if en_tar.enable]) > 0)
        treedata = sg.TreeData()
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])
        treedata.insert("", "Fast", "Fast", [])

        for tar in self.targets:
            if type(tar) is TrackerTarget:
                state = 'Disabled' if not tar.enable else 'Waiting acquisition' if not tar.acquired else 'Stopped' if not tar.active else 'Active' if not tar.triggered else 'Triggered'
                treedata.insert("Tracker", str(tar.targetid), str(tar.targetid), [str(tar.mode).split('.')[1], tar.times_clicked, state, str(tar.pos())])
            elif type(tar) is FastTarget:
                state = 'Disabled' if not tar.enable else 'Stopped' if not tar.active else 'Active'
                treedata.insert("Fast", str(tar.targetid),str(tar.targetid), ["Fast", f'{tar.times_clicked} ({int(tar.cps)}cps)', state, str(tar.pos())])
            elif type(tar) is IdleTarget:
                state = 'Disabled' if not tar.enable else 'Stopped' if not tar.active else 'Active'
                treedata.insert("Idle", str(tar.targetid),str(tar.targetid), ["Idle", tar.times_clicked, state, str(tar.pos())])

        self.window[TARGET_TABLE].update(values=treedata)


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
                r,g,b = getpixelcolor.average(x, y, self.zone_size, self.zone_size)
                hex = rgb_to_hex(r,b,g)
                _hex = text_color_for_bg(r,g,b)
                self.window[COLOR_BTN].update(button_color = (_hex, hex), text=str((x, y)))
            except Exception as e:
                self.window[COLOR_BTN].update(button_color = 'red', text='error')
        elif self.running and (x,y) not in [(tar.x, tar.y) for tar in self.targets]:
            self.aborted = True
            self.window.bring_to_front()

    def on_scroll(self, x, y, dx, dy):
        pass

    def on_click(self, x, y, button, pressed):
        if self.setting_targets and pressed:
            if self.is_click_inside_app(x, y):
                return
            if self.mode == detectionMode.same:
                tar = TrackerTarget(x, y, self.zone_size, detectionMode.same)
            elif self.mode == detectionMode.different:
                tar = TrackerTarget(x, y, self.zone_size, detectionMode.different)
            elif self.mode == detectionMode.change:
                tar = TrackerTarget(x, y, self.zone_size, detectionMode.change)
            elif self.mode == detectionMode.fast:
                if self.queue.has_fast_target():
                    self.remove_target(self.queue.fast_target)
                tar = FastTarget(x, y, 0)
            else:
                return
            self.add_target(tar)

            Timer(0.1, self.window.bring_to_front).start()

    def set_mode(self, m):
        self.mode = m
        self.update_buttons()
# =-=-=-=-==-=-=-=-==-=-=-=-=

    def track_ready(self):
        while not self.are_targets_ready():
            try:
                time.sleep(0.2)
                self.window[CLICK_BTN].update(text=f'{self.nb_target_ready()}/{len(self.targets)}')
            except:
                continue
        self.window[CLICK_BTN].update(text='Click!')

    def run_queue(self):
        task=None
        self.setting_targets = False
        self.running = True
        self.aborted = False
        self.update_buttons()

        self.queue.start()
        while not self.aborted:
            time.sleep(0.1)
        self.queue.stop()

        self.running = False
        print('No longer active')
        self.update_buttons()
        self.queue.stop()

    def add_target(self, tar):
        self.queue.add_target(tar)
        self.targets = self.queue.targets
        Thread(target=self.track_ready, daemon=True, name='track_ready').start()

    def remove_target(self, tar):
        self.queue.remove_target(tar)

    def run(self):
        try:
            # Create an event loop
            self.click_listener_thread = Thread(target=self.click_listener, daemon=True, name='click_listener')
            self.click_listener_thread.start()

            while True:
                timeout = 100 if not self.running else 1000
                event, values = self.window.read(timeout=timeout, timeout_key='NA')

                if self.queue.has_update:
                    self.targets = self.queue.targets
                    self.update_target_table()

                # End program if user closes window or
                # presses the OK button
                if event in [sg.WIN_CLOSED, 'CLOSE', 'OK']:
                    break

                elif event == PATIENCE_SLIDER:
                    self.queue.patience_level = int(values[PATIENCE_SLIDER])
                    print(f'Updated patience level ({self.queue.patience_level})')
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
                elif event == SAVE_BTN:
                    self.save_targets('testSave')
                elif event == LOAD_BTN:
                    self.load_targets('testSave')
                elif event == CLEAR_BTN:
                    self.queue.clear_targets()
                elif event == CLICK_BTN:
                    Thread(target=self.run_queue, daemon=True).start()
                elif TARGET_TABLE in event:
                    try:
                        t = [tar for tar in self.targets if tar.targetid == int(values[TARGET_TABLE][0])]
                        self.selected_target = None if len(t) <= 0 else t[0]
                        if self.selected_target is not None:
                            if isinstance(t, TrackerTarget) and not t.acquired:
                                continue 
                            self.window[DETAIL_ID].update(value=f'Target ID: {str(self.selected_target.targetid)}')
                            if not isinstance(self.selected_target, FastTarget): # Temp fix
                                self.draw_og()
                                self.draw_current()
                                Thread(target=self.display_current, daemon=True).start()
                    except Exception as e:
                        pass #No Target selected
                elif event == 'Delete':
                    if self.selected_target is not None:
                        self.remove_target(self.selected_target)
                        self.selected_target=None
                        self.graph_cur.Erase()
                        self.graph_og.Erase()
                        self.window[DETAIL_ID].update(value='')
                elif event == 'Toggle':
                    if self.selected_target is not None:
                        self.selected_target.enable = not self.selected_target.enable  
            self.listener.stop()
            self.click_listener_thread.join()
            self.window.close()
        except Exception as e:
            self.listener.stop()
            self.click_listener_thread.join()
            self.window.close()
            raise Exception(e)
if __name__ == '__main__':
    try:
        app = App()
        app.run()
    except Exception as e:
        raise e
    finally:
        cursor.set_cursor_default()