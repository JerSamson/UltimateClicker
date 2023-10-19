import base64
import io
from threading import Lock, Thread, Timer
import PySimpleGUI as sg
from DetectionMode import detectionMode
from pynput.mouse import Listener
import getpixelcolor
from ClickHandler import ClickHandler
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
LAST_IMAGE_KEY      ='-LASTIMAGE-'
NEXT_IMAGE_KEY      ='-NEXTIMAGE-'
TARGET_VSEP         ='-TARVSEP-'
SELECTED_FRAME      ='-SELTARFRAME-'
NEXT_FRAME          ='-NEXTTARFRAME-'
LAST_FRAME          ='-LASTTARFRAME-'
TARGET_TABLE        = '-TARGETS-'
DETAIL_ID           = '-DETAILID-'
TIMES_CLICKED       = '-NBCLICKS-'
SAVE_BTN            = '-SAVE-'
LOAD_BTN            = '-LOAD-'
CLEAR_BTN            = '-CLEAR-'
ENABLED_COLOR       = ('black', 'green')
DISABLED_COLOR      = ('black', 'red')
PATIENCE_SLIDER     = '-PATIENCE-'
PATIENCE_PROGRESS   = '-PATIENCE_SLIDE-'
PATIENCE_PROGRESS_2 = '-PATIENCE_SLIDE_SMALLINC-'
NEXT_TARGET         = '-NEXT-'
TOGGLE_TRACK        = '-TOGGLETRACK-'
COLOR_PREVIEW_SIZE  = (10,2)

#TODO: Priority Queue

def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def text_color_for_bg(r,g,b):
    return '#000000' if (r*0.299 + g*0.587 + b*0.114) > 186 else '#ffffff'

class App:

    def __init__(self) -> None:

        self.click_listener_thread = None
        # self.track_ready_thread = Thread(target=self.track_ready, name='TrackReady')
        # self.track_ready_thread_started = False
        self.setting_targets = False
        self.targets = []
        self.all_targets_ready = False
        self.mode = detectionMode.fast

        self.saves_directory = 'SavedTargets\\'
        self.zone_size = 10
        self.track_target_lock = Lock()
        self.selected_target = None
        self.last_target_drew = None
        self.next_target_drew = None
        self.last_selected = None
        self.aborted = False
        self.running = False
        self.queue = ClickHandler()

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

        self.toprow = ['priority', 'type', 'clicks', 'state']#, 'pos']

        treedata = sg.TreeData()
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])
        treedata.insert("", "Fast", "Fast", [])

        target_table=sg.Tree(data=treedata,
            header_font=('Bold, 11'),
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

        selection_buttons = [
            sg.Button('Set Targets', key=SET_TARGET_BTN, button_color = DISABLED_COLOR),
            sg.VSeparator(key=TARGET_VSEP),
            sg.Button('same', key=MODE_SAME_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('diff', key=MODE_DIFF_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('change', key=MODE_CHANGE_BTN, button_color = DISABLED_COLOR, visible=False),
            sg.Button('fastClick', key=FAST_TRACK_BTN, button_color = DISABLED_COLOR, visible=False),
            # sg.VSeparator(),
            # sg.Button('', key=COLOR_BTN, size=COLOR_PREVIEW_SIZE ,button_color = DISABLED_COLOR, visible=False),
            ]


        self.graph_selected = sg.Graph(canvas_size=(IMAGE_SIZE_X*2, IMAGE_SIZE_Y*2),
                graph_bottom_left=(-IMAGE_SIZE_X, -IMAGE_SIZE_Y),
                graph_top_right=(IMAGE_SIZE_X, IMAGE_SIZE_Y),
                enable_events=True,
                drag_submits=False, key=OG_IMAGE_KEY,
                expand_x=True, expand_y=True)
        detail_txt = sg.Text(key=DETAIL_ID)

        selected_frame = [self.graph_selected, detail_txt]

        self.graph_last = sg.Graph(canvas_size=(IMAGE_SIZE_X*2, IMAGE_SIZE_Y*2),
                graph_bottom_left=(-IMAGE_SIZE_X, -IMAGE_SIZE_Y),
                graph_top_right=(IMAGE_SIZE_X, IMAGE_SIZE_Y),
                enable_events=True,
                drag_submits=False, key=LAST_IMAGE_KEY,
                expand_x=True, expand_y=True)

        self.graph_next = sg.Graph(canvas_size=(IMAGE_SIZE_X*2, IMAGE_SIZE_Y*2),
                graph_bottom_left=(-IMAGE_SIZE_X, -IMAGE_SIZE_Y),
                graph_top_right=(IMAGE_SIZE_X, IMAGE_SIZE_Y),
                enable_events=True,
                drag_submits=False, key=NEXT_IMAGE_KEY,
                expand_x=True, expand_y=True)

        last_frame = [self.graph_last]
        next_frame = [self.graph_next]

        details=[
            sg.Sizer(0, 0),
            sg.Frame('Next', [next_frame], visible=False, key=NEXT_FRAME, expand_x=True),
            sg.Frame('Last', [last_frame], visible=False, key=LAST_FRAME, expand_x=True),
            sg.Frame('Selected', [selected_frame], visible=False, key=SELECTED_FRAME, expand_x=True),
            ]

        # selected=[
        #     sg.Frame('Selected ref', [selected_frame, detail_txt], visible=False, key=SELECTED_FRAME)
        # ]

        track_tab=[
            [sg.Sizer(700,0)],
            selection_buttons,
            [sg.Slider(range=(0, 20), default_value=5,
                expand_x=True, enable_events=True,
                orientation='horizontal', key=PATIENCE_SLIDER)],
            [sg.ProgressBar(10, orientation='h', expand_x=True, size=(20, 5),  key=PATIENCE_PROGRESS_2, visible=False, bar_color='blue')],
            [sg.ProgressBar(10, orientation='h', expand_x=True, size=(20, 20), border_width= 3,  key=PATIENCE_PROGRESS, visible=False)],
            [sg.Text(key=NEXT_TARGET, visible=False)],
            [target_table],
            details,
        ]


        # =========================== MAIN LAYOUT ===========================
        layout = [
            [sg.TabGroup([[
                # sg.Tab('idle', idle_tab),
                # sg.Tab('fast', fast_tab),
                sg.Tab('Track', track_tab)
            ]])],
        [
        sg.Button('CLICK!', key=CLICK_BTN, visible=True),
        sg.VSeparator(),
        sg.Button(key=SAVE_BTN, button_text='SAVE'),
        sg.Button(key=LOAD_BTN, button_text='LOAD'),
        sg.Button(key=CLEAR_BTN, button_text='CLEAR'),
        sg.VSeparator(),
        sg.Button(key=TOGGLE_TRACK, button_text='Toggle Trackers'),
        ]
        ]
        font = ("Arial", 12)
        # Create the window
        self.window = sg.Window("UltimateClicker", layout, location=(1100,100), font=font)

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

            Thread(target=self.track_ready, name='TrackReady').start()
            # if not self.track_ready_thread_started and not self.track_ready_thread.is_alive():
            #     self.track_ready_thread.start()
            #     self.track_ready_thread_started = True

            # self.track_target_lock.release()

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
                    self.add_target(tar, False)
            # self.track_ready_thread.join()
    def save_targets(self, save_file):
        if len(self.targets) == 0:
            return

        file_path = self.saves_directory + save_file
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            for tar in self.targets:
                writer.writerow(tar.to_csv())

    def draw(self, tar=None, graph = None):
        graph.draw_image(data=tar.ref_area, location=(-IMAGE_SIZE_X, IMAGE_SIZE_Y))
        if isinstance(tar, TrackerTarget):
            graph.draw_circle((0,0), tar.zone_area//2, line_color='red', line_width=3)
        else:
            graph.draw_line((-10,0), (10,0), color='red', width=3)
            graph.draw_line((0,-10), (0,10), color='red', width=3)

    def draw_last(self):
        last_click = self.queue.last_click
        if last_click is not None:
            self.draw(last_click, self.graph_last)
            self.last_target_drew = last_click
        else:
            self.graph_last.erase()

    def draw_next(self):
        next = self.queue.next_target
        if next is not None:
            self.draw(next[1], self.graph_next)
            self.next_target_drew = next
        else:
            self.graph_next.erase()

    def draw_selected(self):
        sel = self.selected_target
        if sel is not None:
            self.window[SELECTED_FRAME].update(visible=True)
            self.draw(sel, self.graph_selected)
            self.last_selected = sel
        else:
            self.graph_selected.erase()
            self.window[SELECTED_FRAME].update(visible=False)

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
        try:
            self.window[MODE_SAME_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.same else DISABLED_COLOR)
            self.window[MODE_DIFF_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.different else DISABLED_COLOR)
            self.window[MODE_CHANGE_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.change else DISABLED_COLOR)
            self.window[FAST_TRACK_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.fast else DISABLED_COLOR)
            self.window[SET_TARGET_BTN].update(button_color = ENABLED_COLOR if self.setting_targets else DISABLED_COLOR)

            self.window[SET_TARGET_BTN].update(visible=not self.running)
            self.window[MODE_SAME_BTN].update(visible=self.setting_targets)
            self.window[MODE_DIFF_BTN].update(visible=self.setting_targets)
            self.window[MODE_CHANGE_BTN].update(visible=self.setting_targets)
            self.window[FAST_TRACK_BTN].update(visible=self.setting_targets)
            # self.window[COLOR_BTN].update(visible=self.setting_targets and self.mode in [detectionMode.same, detectionMode.different, detectionMode.change])

            self.window[PATIENCE_SLIDER].update(visible=not self.running)
            self.window[PATIENCE_PROGRESS].update(visible=self.running)
            self.window[PATIENCE_PROGRESS_2].update(visible=self.running)
            self.window[NEXT_TARGET].update(visible=self.running)

            Thread(target=self.update_cursor, name='UpdateCursor').start()

        except RuntimeError as e:
            print(f'ERROR - Could not run update button ({e})')

    def update_cursor(self):
        if self.setting_targets:
            cursor.set_cursor_circle()
        else:
            cursor.set_cursor_default()

    def nice_notation(self, sc_not):
        left, right = sc_not.split('E')
        right = right.replace('+','')
        right = right.replace('0','')
        return f'{left}E{right}'

    def update_graphs(self):
        self.window[SELECTED_FRAME].update(visible=self.selected_target is not None and not self.running)
        self.window[NEXT_FRAME].update(visible=self.running)
        self.window[LAST_FRAME].update(visible=self.running)

        if self.queue.last_click is None:
            self.graph_last.erase()
        elif (self.last_target_drew is None or self.last_target_drew.targetid != self.queue.last_click):
            self.draw_last()

        if self.queue.next_target is None:
            self.graph_next.erase()
        elif (self.next_target_drew is None or self.next_target_drew[1].targetid != self.queue.next_target):
            self.draw_next()

    def update_target_table(self):
        # self.window[CLICK_BTN].update(visible=len([en_tar for en_tar in self.targets if en_tar.enable]) > 0)
        treedata = sg.TreeData()
        treedata.insert("", "Fast", "Fast", [])
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])
        self.targets.sort(reverse=False)
        for tar in self.targets:
            if type(tar) is TrackerTarget:
                state = 'Disabled' if not tar.enable else 'Waiting acquisition' if not tar.acquired else 'Stopped' if not tar.active else 'Active' if not tar.triggered else 'Triggered'
                priority = tar.priority
                treedata.insert("Tracker", str(tar.targetid), str(tar.targetid), [priority, str(tar.mode).split('.')[1], tar.times_clicked, state]) #, str(tar.pos())])
            elif type(tar) is FastTarget:
                state = 'Disabled' if not tar.enable else 'Stopped' if not tar.active else 'Active'
                priority = tar.priority
                clicks = self.nice_notation("{:.1E}".format(int(tar.times_clicked))) if tar.times_clicked > 10000 else tar.times_clicked
                treedata.insert("Fast", str(tar.targetid),str(tar.targetid), [priority, "Fast", f'{clicks} ({int(tar.cps)}cps)', state]) #str(tar.pos())])
            elif type(tar) is IdleTarget:
                state = 'Disabled' if not tar.enable else 'Stopped' if not tar.active else 'Active'
                priority = tar.priority
                treedata.insert("Idle", str(tar.targetid),str(tar.targetid), [priority, "Idle", tar.times_clicked, state]) #str(tar.pos())])

        self.window[TARGET_TABLE].update(values=treedata)


    def is_click_inside_app(self, x, y):
        winPos_acc = self.window.CurrentLocation(True)
        winPos = self.window.CurrentLocation(False)
        winSize = self.window.size
        x_outside = x < winPos_acc[0] or x > winPos[0] + winSize[0]
        y_outside = y < winPos_acc[1] or y > winPos[1] + winSize[1]
        return not x_outside and not y_outside
# =-=-=-=-= CALLBACKS =-=-=-=-=
    def click_listener(self):
        with Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll) as self.listener:
            self.listener.join()
            print('INFO - UI.click_listener() thread finished')

    def on_move(self, x, y):
        if self.setting_targets:
            pass
            # try:
                # self.cur_x = x
                # self.cur_y = y
                # r,g,b = getpixelcolor.average(x, y, self.zone_size, self.zone_size)
                # hex = rgb_to_hex(r,b,g)
                # _hex = text_color_for_bg(r,g,b)
                # self.window[COLOR_BTN].update(text=str((x, y)))
                # self.window[COLOR_BTN].update(button_color = (_hex, hex), text=str((x, y)))
            # except Exception as e:
                # self.window[COLOR_BTN].update(button_color = 'red', text='error')
        elif self.running and (x,y) not in [(tar.x, tar.y) for tar in self.targets]:
            self.aborted = True
            self.window.bring_to_front()

    def on_scroll(self, x, y, dx, dy):
        pass

    def on_click(self, x, y, button, pressed):
        if self.setting_targets and pressed:
            if self.is_click_inside_app(x, y):
                print('INFO - Click in app')
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
        nb_ready = 0
        n=0
        self.all_targets_ready = False

        while len(self.targets) <= 0:
            time.sleep(0.2)

        while not self.are_targets_ready():
            try:
                time.sleep(0.3)
                n = self.nb_target_ready()
                if nb_ready is not n:
                    nb_ready = n
                    print(f'Waiting for targets ready ({n}/{len(self.targets)})')
            except Exception as e:
                print(f'are_targets_ready failed ({e})')
                break

        self.all_targets_ready = True
        self.queue.has_update = True
        print('INFO - UI.track_ready() thread finished')

        return
        # self.window[CLICK_BTN].update(text='Click!')

    def update_patience_slider(self):
        if not self.queue.waiting:
            self.window[PATIENCE_PROGRESS_2].update(current_count=0, bar_color='blue')
            self.window[PATIENCE_PROGRESS].update(current_count=self.queue.additionnal_wait, bar_color='blue')
            last_click_id = self.queue.last_click.targetid if self.queue.last_click is not None else 'None'
            self.window[NEXT_TARGET].update(value=f'Next Target ID: Waiting for target\nLast Target ID: {last_click_id}')
        else:
            self.window[PATIENCE_PROGRESS].update(current_count=self.queue.additionnal_wait, bar_color='green')
            self.window[PATIENCE_PROGRESS_2].update(current_count=self.queue.wait_prog, max=self.queue.patience_level, bar_color='green')
            if self.queue.next_target is not None:
                last_click_id = self.queue.last_click.targetid if self.queue.last_click is not None else 'None'
                self.window[NEXT_TARGET].update(value=f'Next Target ID: {self.queue.next_target[1].targetid}\nLast Target ID: {last_click_id}')



    def run_queue(self):
        task=None
        self.setting_targets = False
        self.running = True
        self.aborted = False
        self.update_buttons()

        self.queue.start()
        while not self.aborted:
            time.sleep(1)
        self.queue.stop()

        self.running = False

        self.update_graphs()
        self.update_buttons()
        print('INFO - UI.run_queue() thread finished')

    def add_target(self, tar, track=True):
        self.queue.add_target(tar)
        self.targets = self.queue.targets
        if track:
            Thread(target=self.track_ready, name='TrackReady').start()

        # self.track_target_lock.acquire()
        # if track and not self.track_ready_thread_started and not self.track_ready_thread.is_alive():
        #     self.track_ready_thread.start()
        #     self.track_ready_thread_started = True
        # self.track_target_lock.release()
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

                # End program if user closes window or
                # presses the OK button
                if event in [sg.WIN_CLOSED, 'CLOSE', 'OK']:
                    break

                if self.queue.has_update:
                    self.queue.has_update = False
                    self.targets = self.queue.targets
                    self.update_graphs()
                    if self.running:
                        self.update_patience_slider()
                self.update_target_table()

                if event == 'NA':
                    continue
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
                    self.selected_target = None
                elif event == CLICK_BTN:
                    if not self.all_targets_ready:
                        print('Not all targets ready. Cant run.')
                        continue
                    time.sleep(0.5)
                    Thread(target=self.run_queue, daemon=True).start()
                elif TARGET_TABLE in event:
                    try:
                        t = [tar for tar in self.targets if tar.targetid == int(values[TARGET_TABLE][0])]
                        self.selected_target = None if len(t) <= 0 else t[0]
                        if self.selected_target is not None:
                            self.window[DETAIL_ID].update(
                                value=f'Target ID: {str(self.selected_target.targetid)}')
                        self.draw_selected()
                    except Exception as e:
                        pass #No Target selected
                elif event == 'Delete':
                    if self.selected_target is not None:
                        self.remove_target(self.selected_target)
                        self.selected_target=None
                        # self.graph_cur.Erase()
                        self.graph_selected.erase()
                        self.window[DETAIL_ID].update(value='')
                elif event == 'Toggle':
                    if self.selected_target is not None:
                        self.selected_target.enable = not self.selected_target.enable
                elif event == TOGGLE_TRACK:
                    for t in [tar for tar in self.targets if isinstance(tar, TrackerTarget)]:
                        t.enable = not t.enable

            self.listener.stop()
            self.click_listener_thread.join()
            self.window.close()
        except Exception as e:
            self.listener.stop()
            self.click_listener_thread.join()
            self.window.close()
            raise e
if __name__ == '__main__':
    try:
        app = App()
        app.run()
    except Exception as e:
        raise e
    finally:
        cursor.set_cursor_default()