from genericpath import isfile
from threading import Lock, Thread, Timer
import PySimpleGUI as sg
from DetectionMode import detectionMode
from pynput.mouse import Listener
from ClickHandler import ClickHandler
from Target import *
import cursor
import csv
import os 
pyautogui.PAUSE = 0

millnames = ['',' Thousand',' Million',' Billion',' Trillion']

def millify(n):
    n = float(n)
    millidx = max(0,min(len(millnames)-1,
                        int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))
    if n > 9999:
        return '{:.3f}{}'.format(n / 10**(3 * millidx), f'\n{millnames[millidx]} Clicks')
    else:
        return f'{int(n)}\nClicks'
    
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
BIG_CPS             = '-BIGCPS-'
BIG_TOTAL           = '-BIGTOT-'
BIG_GOLD            = '-BIGGOLD-'
TIMES_CLICKED       = '-NBCLICKS-'
SAVE_BTN            = '-SAVE-'
LOAD_BTN            = '-LOAD-'
LOAD_LAST_BTN       = '-LOADLAST-'
CLEAR_BTN           = '-CLEAR-'
BOTTOM_ROW_FRAME    = '-BOTTOM_ROW_FRAME-'
ENABLED_COLOR       = ('black', 'green')
DISABLED_COLOR      = ('black', 'red')
PATIENCE_SLIDER     = '-PATIENCE-'
PATIENCE_PROGRESS   = '-PATIENCE_SLIDE-'
PATIENCE_PROGRESS_2 = '-PATIENCE_SLIDE_SMALLINC-'
NEXT_TARGET         = '-NEXT-'
TOGGLE_TRACK        = '-TOGGLETRACK-'
TOGGLE_TABLE        = '-TOGGLETABLE-'
COLOR_PREVIEW_SIZE  = (10,2)

#SETTINGS
SUBMIT_SETTINGS     = '-SUBMITSETTINGS'
SAVE_FOLDER         = '-SAVEDIR-'
SAVE_FOLDER_CUR     = '-SAVEDIRCUR-'

TARGET_ZONE         = '-TARGETZONE-'
TARGET_ZONE_CUR     = '-TARGETZONECUR-'

UI_UPDATE           = '-UIUPDATE-'
UI_UPDATE_CUR       = '-UIUPDATECUR-'

TRIGGER_CHECK_RATE       = '-TRIGGERCHECK-'
TRIGGER_CHECK_RATE_CUR   = '-TRIGGERCHECKCUR-'

GOLD_DIGGER          = '-GOLDDIG'
GOLD_DIGGER_CUR      = '-GOLDDIGCUR'

MAX_PATIENCE      = '-MAXPATIENCE-'
MAX_PATIENCE_CUR  = '-MAXPATIENCECUR-'

MAX_PATIENCE_STACK      = '-MAXPATIENCESTACK-'
MAX_PATIENCE_STACK_CUR  = '-MAXPATIENCESTACKCUR-'

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
        # self.allowed_positions = []
        self.all_targets_ready = False
        self.mode = detectionMode.fast

        self.cwd = os.path.dirname(os.path.realpath(__file__)) + '\\'
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
        self.triggercheck = None
        self.UI_update_rate = 100
        self.CLICKGOLD = True
        self.max_patience = 20
        self.tab_size_x = 50
        self.tab_size_y = 1
        self.autosave_freq = 5 # min
        self.last_autosave = time.time()
        self.cur_x = 0
        self.cur_y = 0

        # =========================== IDLE TAB ===========================
        idle_tab=[[sg.Text('IDLE',  size=(self.tab_size_x, self.tab_size_y))]]

        # =========================== FAST TAB ===========================
        fast_tab=[[sg.Text('FAST',  size=(self.tab_size_x, self.tab_size_y))]]

        # =========================== SETTINGS TAB ===========================
        text_width = 16
        settings_tab=[
            [sg.Text('Saves Dir', size=(text_width,1), tooltip='Directory to load and save data'), sg.InputText(key=SAVE_FOLDER, size=(15,1)), sg.Text(key=SAVE_FOLDER_CUR, text=self.saves_directory, text_color='light gray', auto_size_text=True)], 
            [sg.Text('Target zone', size=(text_width,1), tooltip='Height and width (px) of the area used to check if target has triggered.'), sg.InputText(key=TARGET_ZONE, size=(15,1)), sg.Text(key=TARGET_ZONE_CUR, text=self.zone_size, text_color='light gray', auto_size_text=True)], 
            [sg.Text('UI refresh', size=(text_width,1), tooltip='Delay (ms) between UI refresh while running.\nLow values can affect performances'), sg.InputText(key=UI_UPDATE, size=(15,1)), sg.Text(key=UI_UPDATE_CUR, text=self.UI_update_rate, text_color='light gray', auto_size_text=True)], 
            [sg.Text('Trigger check rate', size=(text_width,1), tooltip='Delay (s) between trigger checks (Same as current patience level by default)\nLow values can affect performances'), sg.InputText(key=TRIGGER_CHECK_RATE, size=(15,1)), sg.Text(key=TRIGGER_CHECK_RATE_CUR, text=f'{"Same as patience" if self.triggercheck is None else self.triggercheck}', text_color='light gray', auto_size_text=True)], 
            [sg.Text('Max patience', size=(text_width,1), tooltip='When using trackers, patience will prevent the clicker to simply click as soon as its triggered.\nEach newly triggered target add 1 stack. Each stack will take <<patience level>> sec to deplete.'), sg.InputText(key=MAX_PATIENCE, size=(15,1)), sg.Text(key=MAX_PATIENCE_CUR, text=self.max_patience, text_color='light gray', auto_size_text=True)], 
            [sg.Text('Max patience Stack', size=(text_width,1), tooltip='Patience stack that would bring the queued up delay to exceed this value will be ignored.'), sg.InputText(key=MAX_PATIENCE_STACK, size=(15,1)), sg.Text(key=MAX_PATIENCE_STACK_CUR, text=self.queue.max_patience_stack, text_color='light gray', auto_size_text=True)], 
            [sg.Checkbox(default=self.CLICKGOLD, text='GOLD DIGGER', key=GOLD_DIGGER, size=(text_width,1), tooltip='If selected, will periodically check and queue up golden cookies\n(For Cookie Clicker game)'),sg.Text(key=GOLD_DIGGER_CUR, text=f'{"CLICKING GOLD!!!" if self.CLICKGOLD else "Nope.. T_T"}', text_color='light gray', auto_size_text=True)], 
            [sg.Button(button_text='Update', key=SUBMIT_SETTINGS)]
            ]

        # =========================== RIGHT CLICK MENU ===========================
        self.right_click_menu = ['&Right', ['Delete', 'Toggle']]



        # =========================== TRACKER TAB ===========================

        self.toprow = ['priority', 'type', 'clicks', 'state']#, 'pos']

        treedata = sg.TreeData()
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])
        treedata.insert("", "Fast", "Fast", [])

        self.target_table=sg.Tree(data=treedata,
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
            sg.Sizer(0, 0),
            sg.Button('Set Targets', key=SET_TARGET_BTN, expand_x=True, expand_y=True),
            sg.Sizer(0, 0),
            # sg.VSeparator(key=TARGET_VSEP),
            sg.Button('same', key=MODE_SAME_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('diff', key=MODE_DIFF_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('change', key=MODE_CHANGE_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('fastClick', key=FAST_TRACK_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
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
        
        # TODO
        # self.graph_cps = sg.Graph(canvas_size=(IMAGE_SIZE_X*2, IMAGE_SIZE_Y*2),
        #         graph_bottom_left=(-IMAGE_SIZE_X, -IMAGE_SIZE_Y),
        #         graph_top_right=(IMAGE_SIZE_X, IMAGE_SIZE_Y),
        #         enable_events=True,
        #         drag_submits=False, key=NEXT_IMAGE_KEY,
        #         expand_x=True, expand_y=True)

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

        self.patience_slider = sg.Slider(range=(0, self.max_patience), default_value=5,
                expand_x=True, enable_events=True,
                orientation='horizontal', key=PATIENCE_SLIDER, tooltip='Patience level\nWait increment for each newly triggered tracker')

        detailsFont = 'Terminal'
        track_tab=[
            [sg.Sizer(625,0)],
            selection_buttons,
            [sg.Sizer(0,0)],
            [sg.Sizer(0,0), sg.Text(key=BIG_TOTAL, visible=False, expand_x=True, expand_y=True, font=(detailsFont, 35), justification='center')],
            [sg.Sizer(0,0), sg.Text(key=BIG_CPS, visible=False, expand_x=True, expand_y=True, font=(detailsFont, 22), justification='center', text_color='gold')], #DAA520
            [sg.Sizer(0,0), sg.Text(key=BIG_GOLD, visible=False, expand_x=True, expand_y=True, font=(detailsFont, 16), justification='center', text_color='gold')],
            [sg.Sizer(0,0)],
            [sg.Sizer(0,0), self.patience_slider],
            [sg.Sizer(0,0), sg.ProgressBar(self.queue.patience_level, orientation='h', expand_x=True, size=(20, 5),  key=PATIENCE_PROGRESS_2, visible=False, bar_color='blue')],
            [sg.Sizer(0,0), sg.ProgressBar(self.queue.max_patience_stack, orientation='h', expand_x=True, size=(20, 20), border_width= 3,  key=PATIENCE_PROGRESS, visible=False)],
            # [sg.Text(key=NEXT_TARGET, visible=False)],
            [sg.Sizer(0,0)],
            details,
            [sg.Sizer(0,0)],
            [self.target_table, sg.Sizer(0,0), ],
        ]

        bottom_row = [
            sg.Button(key=SAVE_BTN, button_text='SAVE', expand_x=True, expand_y=True),
            sg.VSeparator(),
            sg.Button(key=LOAD_BTN, button_text='LOAD', expand_x=True, expand_y=True),
            sg.Button(key=LOAD_LAST_BTN, button_text='LAST', expand_x=True, expand_y=True),
            sg.VSeparator(),
            sg.Button(key=CLEAR_BTN, button_text='CLEAR', expand_x=True, expand_y=True),
            sg.VSeparator(),
            sg.Button(key=TOGGLE_TRACK, button_text='Toggle Trackers', expand_x=True, expand_y=True),
            sg.VSeparator(),
            sg.Button(key=TOGGLE_TABLE, button_text='Details', expand_x=True, expand_y=True),
        ]
        bottom_row_frame = [bottom_row]

        # =========================== MAIN LAYOUT ===========================
        layout = [
            [sg.Sizer(0,0)],
            [sg.TabGroup([[
                # sg.Tab('idle', idle_tab),
                # sg.Tab('fast', fast_tab),
                sg.Tab('Track', track_tab,element_justification='center'),
                sg.Tab('Settings', settings_tab,element_justification='left')
            ]])],
            [sg.Sizer(0,0)],
        [
            [sg.Frame('', bottom_row_frame, visible=True, key=BOTTOM_ROW_FRAME, expand_x=False, border_width=1), sg.Sizer(0,0)],
            sg.Button('CLICK!', key=CLICK_BTN, visible=True, expand_x=True, expand_y=True)

        ]
        ]

        font = ("Arial", 12)
        # Create the window
        self.window = sg.Window("UltimateClicker", layout, location=(1100,100), font=font, element_justification='center')

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

    def load_last_auto_save(self):
        self.load_targets('auto_save')

    def autosave(self):
        self.save_targets('auto_save')
        self.last_autosave = time.time()

    def Choose_file_popup(self, text, data, can_create=False):
        if can_create:
            layout = [
                [sg.Text(text)],
                [sg.Listbox(data, size=(20,5), key='SELECTED')],
                [[sg.Text('New File:'), sg.InputText(key='-NEWFILE-', size=(10,1))]],
                [sg.OK(), sg.Cancel()],
            ]
        else:
            layout = [
                [sg.Text(text)],
                [sg.Listbox(data, size=(20,5), key='SELECTED')],
                [sg.OK(), sg.Cancel()],
            ]
        
        window = sg.Window('POPUP', layout).Finalize()
        
        while True:
            event, values = window.read()
            
            if event == sg.WINDOW_CLOSED:
                return None
            elif event == 'OK':
                break
            elif event == 'Cancel':
                return None
            else:
                print('OVER')

        window.close()

        print('[Choose_file_popup] event:', event)
        print('[Choose_file_popup] values:', values)

        if can_create and values and values['-NEWFILE-']:
            return values['-NEWFILE-']
        elif values and values['SELECTED']:
            return values['SELECTED'][0]
        else:
            return None

    def choose_load_file(self):
        files = [f for f in os.listdir(self.cwd + self.saves_directory)]
        return self.Choose_file_popup(text="Choose file to load", data=files)

    def choose_save_file(self):
        files = [f for f in os.listdir(self.cwd + self.saves_directory)]
        return self.Choose_file_popup(text="Choose file to save", data=files, can_create=True)

    def load_targets(self, save_file):
        print(f'INFO - load_targets - Loading targets from {save_file}')
        try:
            self.queue.clear_targets()
            file_path = self.cwd + self.saves_directory + save_file
            with open(file_path, 'r') as file:
                csvreader = csv.reader(file)

                Thread(target=self.track_ready, name='TrackReady').start()
                for row in csvreader:
                    tar = None
                    typ = row[0]
                    if typ == 'Tracker':
                        tar = TrackerTarget(int(row[1]), int(row[2]), self.zone_size, detectionMode(int(row[3])))
                    elif typ == 'Fast':
                        tar = FastTarget(int(row[1]), int(row[2]))
                    elif typ == 'Idle':
                        tar = IdleTarget(int(row[1]), int(row[2]))
                    elif typ == 'GOLD':
                        if row[1].isdigit():
                            self.queue.golden_clicked = int(row[1])

                    if tar is not None:
                        try: tar.times_clicked = int(row[4]) 
                        except: pass
                        self.add_target(tar, False)
        except Exception as e:
            print(f'Could not load targets from "{save_file}" ({e})')
            # self.track_ready_thread.join()

    def save_targets(self, save_file):
        if len(self.targets) == 0:
            return
        try:
            print(f'INFO - save_targets - Saving targets to {save_file}')
            file_path = self.cwd + self.saves_directory + save_file
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                for tar in self.targets:
                    writer.writerow(tar.to_csv())
                writer.writerow(['GOLD', self.queue.golden_clicked])
        except Exception as e:
            print(f'Could not save files to "{save_file}" ({e})')

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
        if next is not None and self.queue.waiting:
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

            self.window[SET_TARGET_BTN].update(visible=not self.running)
            self.window[MODE_SAME_BTN].update(visible=self.setting_targets)
            self.window[MODE_DIFF_BTN].update(visible=self.setting_targets)
            self.window[MODE_CHANGE_BTN].update(visible=self.setting_targets)
            self.window[FAST_TRACK_BTN].update(visible=self.setting_targets)
            # self.window[COLOR_BTN].update(visible=self.setting_targets and self.mode in [detectionMode.same, detectionMode.different, detectionMode.change])

            self.window[PATIENCE_SLIDER].update(visible=not self.running)
            self.window[PATIENCE_PROGRESS].update(visible=self.running)
            self.window[PATIENCE_PROGRESS_2].update(visible=self.running)

            self.window[BOTTOM_ROW_FRAME].update(visible= not self.running)
            self.window[CLICK_BTN].update(visible= not self.running)
            self.window[BIG_CPS].update(visible=self.running and self.queue.has_fast_target())
            self.window[BIG_TOTAL].update(visible=self.running and self.queue.has_fast_target())
            self.window[BIG_GOLD].update(visible=self.running and self.queue.CLICK_GOLDEN_COOKIES)

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
        self.window[NEXT_FRAME].update(visible=self.running and self.queue.has_tracker_targets())
        self.window[LAST_FRAME].update(visible=self.running and self.queue.has_tracker_targets())

        if self.queue.last_click is None:
            self.graph_last.erase()
        elif (self.last_target_drew is None or self.last_target_drew != self.queue.last_click):
            self.draw_last()

        if self.queue.next_target is None:
            self.graph_next.erase()
        elif (self.next_target_drew is None or self.next_target_drew != self.queue.next_target):
            self.draw_next()

    def update_target_table(self):
        # self.window[CLICK_BTN].update(visible=len([en_tar for en_tar in self.targets if en_tar.enabled]) > 0)
        treedata = sg.TreeData()
        treedata.insert("", "Fast", "Fast", [])
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])
        self.targets.sort(reverse=False)
        for tar in self.targets:
            if type(tar) is TrackerTarget:
                state = 'Disabled' if not tar.enabled else 'Waiting acquisition' if not tar.acquired else 'Stopped' if not tar.active else 'Active' if not tar.triggered else 'Triggered'
                priority = tar.priority
                treedata.insert("Tracker", str(tar.targetid), str(tar.targetid), [priority, str(tar.mode).split('.')[1], tar.times_clicked, state]) #, str(tar.pos())])
            elif type(tar) is FastTarget:
                state = 'Disabled' if not tar.enabled else 'Stopped' if not tar.active else 'Active'
                priority = tar.priority
                clicks = self.nice_notation("{:.1E}".format(int(tar.times_clicked))) if tar.times_clicked > 10000 else tar.times_clicked
                treedata.insert("Fast", str(tar.targetid),str(tar.targetid), [priority, "Fast", f'{clicks} ({int(tar.cps)}cps)', state]) #str(tar.pos())])

            elif type(tar) is IdleTarget:
                state = 'Disabled' if not tar.enabled else 'Stopped' if not tar.active else 'Active'
                priority = tar.priority
                treedata.insert("Idle", str(tar.targetid),str(tar.targetid), [priority, "Idle", tar.times_clicked, state]) #str(tar.pos())])
            elif type(tar) is GOLDENTARGET:
                state = 'GOLD!!!'
                priority = 'INFINITE'
                treedata.insert("Idle", str(tar.targetid),str(tar.targetid), [priority, "Idle", tar.times_clicked, state]) #str(tar.pos())])

        self.window[TARGET_TABLE].update(values=treedata)

    def update_run_details(self):
        if self.queue.has_fast_target():
            self.window[BIG_CPS].update(visible=self.running)
            self.window[BIG_TOTAL].update(visible=self.running)
            self.window[BIG_CPS].update(value=f'{int(self.queue.fast_target.cps)} CPS ({int(self.queue.fast_target.avg_cps)} avg)')
            self.window[BIG_TOTAL].update(value=f'{millify(self.queue.fast_target.times_clicked)}')
            self.window[BIG_GOLD].update(value=f'{self.queue.golden_clicked} Golden Cookie{"s" if self.queue.golden_clicked > 1 else ""}')
        else:
            self.window[BIG_CPS].update(visible=False)
            self.window[BIG_TOTAL].update(visible=False)

        self.window[BIG_GOLD].update(visible=self.running and self.queue.CLICK_GOLDEN_COOKIES)

    def is_click_inside_app(self, x, y):
        winPos_acc = self.window.CurrentLocation(True)
        winPos = self.window.CurrentLocation(False)
        winSize = self.window.size
        x_outside = x < winPos_acc[0] or x > winPos[0] + winSize[0]
        y_outside = y < winPos_acc[1] or y > winPos[1] + winSize[1]
        return not x_outside and not y_outside
# =-=-=-=-= CALLBACKS =-=-=-=-=
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
        elif self.running and (x,y) not in self.queue.get_allowed_positions():
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
            self.add_target(tar, not tar.is_ready())

            t = Timer(0.1, self.window.bring_to_front)
            t.name='BringToFront'
            t.start()

    def set_mode(self, m):
        self.mode = m
        self.update_buttons()
# =-=-=-=-==-=-=-=-==-=-=-=-=

    def track_ready(self):
        print('INFO - UI.track_ready() thread started')
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
        if self.queue.has_tracker_targets():
            if not self.queue.waiting:
                self.window[PATIENCE_PROGRESS_2].update(current_count=0, bar_color='blue')
                self.window[PATIENCE_PROGRESS].update(current_count=self.queue.additionnal_wait, bar_color='blue')
                last_click_id = self.queue.last_click.targetid if self.queue.last_click is not None else 'None'
                # self.window[NEXT_TARGET].update(value=f'Next Target ID: Waiting for target\nLast Target ID: {last_click_id}')
            else:
                self.window[PATIENCE_PROGRESS].update(current_count=self.queue.additionnal_wait, bar_color='green')
                self.window[PATIENCE_PROGRESS_2].update(current_count=self.queue.wait_prog, max=self.queue.patience_level, bar_color='green')
                if self.queue.next_target is not None:
                    last_click_id = self.queue.last_click.targetid if self.queue.last_click is not None else 'None'
                    # self.window[NEXT_TARGET].update(value=f'Next Target ID: {self.queue.next_target[1].targetid}\nLast Target ID: {last_click_id}')
        else:
            self.window[PATIENCE_PROGRESS_2].update(visible=False)
            self.window[PATIENCE_PROGRESS].update(visible=False)


    def run_queue(self):
        print('INFO - UI.run_queue() thread started')
        task=None
        self.setting_targets = False
        self.running = True
        self.aborted = False
        self.update_buttons()

        if self.triggercheck is not None:
            self.queue.triggercheck = self.triggercheck

        self.autosave()
        self.queue.CLICK_GOLDEN_COOKIES = self.CLICKGOLD
        self.queue.start()
        while not self.aborted:
            time.sleep(1)
        self.queue.stop()

        self.running = False

        self.autosave()
        self.update_graphs()
        self.update_buttons()
        print('INFO - UI.run_queue() thread finished')

    def add_target(self, tar, track=True):
        if tar in self.queue.targets:
            print(f'WARN - UI.add_target() - Target already in queue')
            return
        
        self.queue.add_target(tar)
        self.targets = self.queue.targets
        # self.allowed_positions = [(tar.x, tar.y) for tar in self.targets]
        if track:
            Thread(target=self.track_ready, name='TrackReady').start()

    def remove_target(self, tar):
        self.queue.remove_target(tar)

    def update_settings(self, values):

        if values[SAVE_FOLDER] != '':
            self.saves_directory = values[SAVE_FOLDER]
            self.window[SAVE_FOLDER_CUR].update(value=self.saves_directory)

        value = values[TARGET_ZONE]
        if value != '' :
            if value.isdigit() and int(value) > 1:
                self.zone_size = int(value)
                self.window[TARGET_ZONE_CUR].update(value=self.zone_size)
            else:
                print(f'WARN - invalid target zone value ({value})')

        value = values[UI_UPDATE]
        if value != '':
            if value.isdigit() and int(value) > 1:
                self.UI_update_rate = int(value)
                self.window[UI_UPDATE_CUR].update(value=self.UI_update_rate)
            else:
                print(f'WARN - invalid UI update rate value ({value})')

        value = values[TRIGGER_CHECK_RATE]
        if value != '':
            if value.isdigit() and int(value) > 1:
                self.triggercheck = int(value)
                self.window[TRIGGER_CHECK_RATE_CUR].update(value=self.triggercheck)
            else:
                print(f'WARN - invalid trigger check rate value ({value})')

        value = values[GOLD_DIGGER]
        if value != '':
            if isinstance(value, bool):
                self.CLICKGOLD = value
                self.window[GOLD_DIGGER_CUR].update(value=f'{"CLICKING GOLD!!!" if self.CLICKGOLD else "Nope.. T_T"}')
            else:
                print(f'WARN - invalid GOLD_DIGGER value ({value})')

        value = values[MAX_PATIENCE]
        if value != '':
            if value.isdigit():
                self.max_patience = int(value)
                self.window[MAX_PATIENCE_CUR].update(value=self.max_patience)
                self.window[PATIENCE_SLIDER].update(range=(0, self.max_patience))
            else:
                print(f'WARN - invalid max patience value ({value})')

        value = values[MAX_PATIENCE_STACK]
        if value != '':
            if value.isdigit():
                self.queue.max_patience_stack = int(value)
                self.window[MAX_PATIENCE_STACK_CUR].update(value=self.queue.max_patience_stack)
                self.window[PATIENCE_PROGRESS].update(max=self.queue.max_patience_stack)
            else:
                print(f'WARN - invalid max patience value ({value})')

    def run(self):
        try:
            print('INFO - UI.run_queue() thread finished')
            # Create an event loop
            self.click_listener_thread = Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
            self.click_listener_thread.name='ClickListener'
            self.click_listener_thread.start()
            while True:
                timeout = 1000 if not self.running else self.UI_update_rate
                event, values = self.window.read(timeout=timeout, timeout_key='NA')
                if event != 'NA':
                    print(f'INFO - UI.run() - Handling event [{event}]')
                # End program if user closes window or
                # presses the OK button
                if event in [sg.WIN_CLOSED, 'CLOSE', 'OK']:
                    break

                if self.queue.has_update:
                    self.queue.has_update = False
                    self.targets = self.queue.targets
                    # self.allowed_positions = [(tar.x, tar.y) for tar in self.targets]

                if self.running and self.autosave_freq > 0 and time.time() - self.last_autosave >= self.autosave_freq*60:
                    print(f'INFO - UI.run() - Automatic save (Set for every {self.autosave_freq} minutes)')
                    self.autosave()
                    
                self.update_graphs()
                self.update_patience_slider()

                self.update_run_details() 
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
                    file = self.choose_save_file()
                    if file is not None:
                        self.save_targets(file)
                elif event == LOAD_BTN:
                    file = self.choose_load_file()
                    if file is not None:
                        self.load_targets(file)
                elif event == LOAD_LAST_BTN:
                    self.load_targets('auto_save')
                elif event == CLEAR_BTN:
                    self.queue.clear_targets()
                    self.selected_target = None
                elif event == CLICK_BTN:
                    if not self.are_targets_ready():
                        print('WARN - Not all targets ready. Cant run.')
                        continue
                    time.sleep(0.5)
                    Thread(target=self.run_queue, daemon=True, name='RunQueue').start()
                    self.window[BOTTOM_ROW_FRAME].update(visible=False)
                    self.window[CLICK_BTN].update(visible=False)


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
                        self.selected_target.enabled = not self.selected_target.enabled
                elif event == TOGGLE_TRACK:
                    for t in [tar for tar in self.targets if isinstance(tar, TrackerTarget)]:
                        t.enabled = not t.enabled
                elif event == TOGGLE_TABLE:
                    self.window[TARGET_TABLE].update(visible=not self.target_table.visible)
                elif event == SUBMIT_SETTINGS:
                    self.update_settings(values)

            self.click_listener_thread.stop()
            self.click_listener_thread.join()
            self.window.close()

            if len(self.targets) > 0:
                self.autosave()

        except Exception as e:
            self.click_listener_thread.stop()
            self.click_listener_thread.join()
            self.window.close()
            raise e
if __name__ == '__main__':
    try:
        app = App()
        app.run()
        # mouse = Controller()
        # one = time.time_ns()
        # for i in range(200):
        #     mouse.click(Button.left)

        # two = time.time_ns()

        # print(f'{int((two-one)/1000000)}ms')
    except Exception as e:
        raise e
    finally:
        cursor.set_cursor_default()