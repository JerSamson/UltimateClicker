from threading import Lock, Thread, Timer
import PySimpleGUI as sg
from DetectionMode import detectionMode
from pynput.mouse import Listener
from ClickHandler import ClickHandler
from Target import *
from logger import Logger
from Collapsible import *
import cursor
import csv
import os 

from Settings import *
from event_graph import *

millnames = ['',' Thousand',' Million',' Billion',' Trillion']

def millify(n):
    n = float(n)
    millidx = max(0,min(len(millnames)-1,
                        int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))
    if n > 9999:
        return '{:.3f}{}'.format(n / 10**(3 * millidx), f'\n{millnames[millidx]} Clicks')
    else:
        return f'{int(n)}\nClicks'
         
SET_TARGET_BTN           = '-SET TARGETS-'
MODE_SAME_BTN            = '-SAME-'
MODE_DIFF_BTN            = '-DIFF-'
MODE_CHANGE_BTN          = '-CHANGE-'
MODE_IDLE_BTN            = '-IDLE-'
COLOR_BTN                = '-COLOT-'
CLICK_BTN                = '-CLICK-'
FAST_TRACK_BTN           = '-FASTTRACK-'
IDLE_MODE_BTN            = '-IDLEMODEBTN-'
CUR_IMAGE_KEY            = '-CURIMAGE-'
OG_IMAGE_KEY             = '-OGIMAGE-'
LAST_IMAGE_KEY           = '-LASTIMAGE-'
NEXT_IMAGE_KEY           = '-NEXTIMAGE-'
EVENT_GRAPH              = '-EVENTGRAPH-'
TARGET_VSEP              = '-TARVSEP-'
SELECTED_FRAME           = '-SELTARFRAME-'
NEXT_FRAME               = '-NEXTTARFRAME-'
LAST_FRAME               = '-LASTTARFRAME-'
TARGET_TABLE             = '-TARGETS-'
DETAIL_ID                = '-DETAILID-'
BIG_CPS                  = '-BIGCPS-'
BIG_TOTAL                = '-BIGTOT-'
BIG_GOLD                 = '-BIGGOLD-'
TIMES_CLICKED            = '-NBCLICKS-'
SAVE_BTN                 = '-SAVE-'
LOAD_BTN                 = '-LOAD-'
LOAD_LAST_BTN            = '-LOADLAST-'
CLEAR_BTN                = '-CLEAR-'
BOTTOM_ROW_FRAME         = '-BOTTOM_ROW_FRAME-'
ENABLED_COLOR            = ('black', 'green')
DISABLED_COLOR           = ('black', 'red')
PATIENCE_SLIDER          = '-PATIENCE_SLIDER-'
PATIENCE_PROGRESS        = '-PATIENCE_BIGINC-'
PATIENCE_PROGRESS_2      = '-PATIENCE_SMALLINC-'
NEXT_TARGET              = '-NEXT-'
TOGGLE_TRACK             = '-TOGGLETRACK-'
TOGGLE_TABLE             = '-TOGGLETABLE-'
COLOR_PREVIEW_SIZE       = (10,2)
     
TRACK_TAB                = '-TRACK_TAB-'
     
SUBMIT_SETTINGS          = '-SUBMIT_SETTINGS-'
RESET_SETTINGS           = '-RESET_SETTINGS-'
SAVE_SETTINGS            = '-SAVE_SETTINGS-'

def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)

def text_color_for_bg(r,g,b):
    return '#000000' if (r*0.299 + g*0.587 + b*0.114) > 186 else '#ffffff'
    
class App:
    def __init__(self) -> None:
        self.eventgraph = EventGraph(EVENT_GRAPH)  
        self.cam = ScreenRecorder()
        self.logger = Logger()
        self.settings = Settings()

        self.collapsibles = []
        self.last_saved = None
        self.click_listener_thread = None
        self.setting_targets = False
        self.targets = []
        self.all_targets_ready = False
        self.mode = detectionMode.fast
        self.current_tab = None
        self.cwd = os.path.dirname(os.path.realpath(__file__)) + '\\'
        self.userdata_dir = self.cwd + 'UserData\\'
        self.last_save_file = 'last_save'
        self.track_target_lock = Lock()
        self.selected_target = None
        self.last_target_drew = None
        self.last_next_target_drew = None
        self.last_selected = None
        self.aborted = False
        self.running = False
        self.queue = ClickHandler()
        self.tab_size_x = 50
        self.tab_size_y = 1
        self.last_autosave = time.time()
        self.cur_x = 0
        self.cur_y = 0
        self.max_cps_entry = 0

        # =========================== IDLE TAB ===========================
        idle_tab=[[sg.Text('IDLE',  size=(self.tab_size_x, self.tab_size_y))]]

        # =========================== FAST TAB ===========================
        fast_tab=[[sg.Text('FAST',  size=(self.tab_size_x, self.tab_size_y))]]

        # =========================== SETTINGS TAB ===========================
        text_width = 20
        setting_frame_title_color = 'dark slate gray'

        save_dir_setting            = self.settings.add_entry(SettingEntry('Save Directory', SAVE_FOLDER, SAVE_FOLDER_CUR, str, 'Directory to load and save data'))
        UI_refresh_setting          = self.settings.add_entry(SettingEntry('UI refresh (ms)', UI_UPDATE, UI_UPDATE_CUR, int, 'Delay (ms) between UI refresh while running.\nLow values can affect performances'))
        autosave_setting            = self.settings.add_entry(SettingEntry('Autosave (s)', AUTOSAVE_FREQ, AUTOSAVE_FREQ_CUR, int, 'Delay (s) between Autosaves (0 for no autosave)'))
        max_patience_setting        = self.settings.add_entry(SettingEntry('Max patience', MAX_PATIENCE, MAX_PATIENCE_CUR, int, 'When using trackers, patience will prevent the clicker to simply click as soon as its triggered.\nEach newly triggered target add 1 stack. Each stack will take <<patience level>> sec to deplete.'))
        max_patience_stack_setting  = self.settings.add_entry(SettingEntry('Max patience stack', MAX_PATIENCE_STACK, MAX_PATIENCE_STACK_CUR, int, 'Patience stack that would bring the queued up delay to exceed this value will be ignored.'))
        target_cps_setting          = self.settings.add_entry(SettingEntry('Target CPS', TARGET_CPS, TARGET_CPS_CUR, int, 'Setpoint for CPS pid of fast trgets.'))
        cps_update_setting          = self.settings.add_entry(SettingEntry('CPS Update Delay (s)', CPS_UPDATE, CPS_UPDATE_CUR, float, 'Delay between cps update (fast targets).'))
        trigger_rate_setting        = self.settings.add_entry(SettingEntry('Trigger check rate (s)', TRIGGER_CHECK_RATE, TRIGGER_CHECK_RATE_CUR, int, 'Delay (s) between trigger checks (Same as current patience level [-1] by default)\nLow values can affect performances'))
        target_zone_setting         = self.settings.add_entry(SettingEntry('Target zone (px)', TARGET_ZONE, TARGET_ZONE_CUR, int, 'Height and width (px) of the area used to check if target has triggered.'))
        cookie_check_rate_setting   = self.settings.add_entry(SettingEntry('Check freq (s)', GOLD_FREQ, GOLD_FREQ_CUR, int, 'Delay (s) between gold cookie seek'))
        kp_setting                  = self.settings.add_entry(SettingEntry('KP', KP, KP_CUR, float, 'PID P param'))
        ki_setting                  = self.settings.add_entry(SettingEntry('KI', KI, KI_CUR, float, 'PID I param'))
        kd_setting                  = self.settings.add_entry(SettingEntry('KD', KD, KD_CUR, float, 'PID D param'))

        log_level_setting           = self.settings.add_entry(SettingEntry('Log level', LOG_LEVEL, LOG_LEVEL_CUR, int))


        self.settings.load()

        # General settings
        general_settings_layout = [
            save_dir_setting.layout(),
            UI_refresh_setting.layout(),
            autosave_setting.layout()
        ]
        general_settings = Collapsible('General', general_settings_layout, GENERAL_FRAME, COLLAPSE_GENERAL_FRAME, True)
        self.collapsibles.append(general_settings)

        # Patience settings
        patience_settings_layout = [
            max_patience_setting.layout(),
            max_patience_stack_setting.layout()
        ]
        patience_settings = Collapsible('Patience', patience_settings_layout, PATIENCE_FRAME, COLLAPSE_PATIENCE_FRAME, True)
        self.collapsibles.append(patience_settings)

        # CPS settings
        cps_settings_layout = [
            target_cps_setting.layout(),
            cps_update_setting.layout()
        ]
        cps_settings = Collapsible('CPS', cps_settings_layout, CPS_FRAME, COLLAPSE_CPS_FRAME, True)
        self.collapsibles.append(cps_settings)

        # Tracker settings
        tracker_settings_layout = [
            trigger_rate_setting.layout(),
            target_zone_setting.layout()
        ]
        tracker_settings = Collapsible('Trackers', tracker_settings_layout, TRACKER_FRAME, COLLAPSE_TRACKER_FRAME, True)
        self.collapsibles.append(tracker_settings)
        
        # Cookie settings
        cookie_settings_layout = [
            cookie_check_rate_setting.layout(),
            [sg.Checkbox(default=self.settings.check_for_gold_cookie, text='GOLD DIGGER', key=GOLD_DIGGER, size=(text_width,1), tooltip='If selected, will periodically check and queue up golden cookies\n(For Cookie Clicker game)'),sg.Text(key=GOLD_DIGGER_CUR, text=f'{"CLICKING GOLD!!!" if self.settings.check_for_gold_cookie else "Nope.. T_T"}', text_color='light gray', auto_size_text=True)], 
        ]
        cookie_settings = Collapsible('Golden cookies', cookie_settings_layout, COOKIE_FRAME, COLLAPSE_COOKIE_FRAME, True)
        self.collapsibles.append(cookie_settings)

        # PID settings
        pid_settings_layout = [
            kp_setting.layout(),
            ki_setting.layout(),
            kd_setting.layout()
        ]
        pid_settings = Collapsible('PID', pid_settings_layout, PID_FRAME, COLLAPSE_PID_FRAME, True)
        self.collapsibles.append(pid_settings)

        # DEBUG settings
        debug_settings_layout = [
            log_level_setting.layout(),
        ]
        debug_settings = Collapsible('Debug', debug_settings_layout, DEBUG_FRAME, COLLAPSE_DEBUG_FRAME, True)
        self.collapsibles.append(debug_settings)

        settings_tab= [
            general_settings.permanent_section,
            general_settings.collapsible_section,

            patience_settings.permanent_section,
            patience_settings.collapsible_section,

            tracker_settings.permanent_section,
            tracker_settings.collapsible_section,
            
            cps_settings.permanent_section,
            cps_settings.collapsible_section,

            pid_settings.permanent_section,
            pid_settings.collapsible_section,

            cookie_settings.permanent_section,
            cookie_settings.collapsible_section,

            debug_settings.permanent_section,
            debug_settings.collapsible_section,

            [
                sg.Button(button_text='Apply', key=SUBMIT_SETTINGS),
                sg.Button(button_text='Apply and save',  key=SAVE_SETTINGS),
                sg.Button(button_text='Reset to default', key=RESET_SETTINGS),
                sg.Sizer(0,0)],
            ]

        # =========================== RIGHT CLICK MENU ===========================
        self.right_click_menu = ['&Right', ['Delete', 'Toggle']]


        # =========================== TRACKER TAB ===========================

        self.toprow = ['priority', 'type', 'clicks', 'state']#, 'pos']

        treedata = sg.TreeData()
        treedata.insert("", "Fast", "Fast", [])
        treedata.insert("", "Tracker", "Tracker", [])
        treedata.insert("", "Idle", "Idle", [])

        self.target_table=sg.Tree(data=treedata,
            header_font=('Bold, 11'),
            headings=self.toprow,
            auto_size_columns=True,
            # num_rows=20,
            col0_width=5,
            key=TARGET_TABLE,
            select_mode=sg.TABLE_SELECT_MODE_EXTENDED,
            show_expanded=True,
            enable_events=True,
            expand_x=True,
            # expand_y=True,
            right_click_menu=self.right_click_menu,
            justification='center',
            visible=False
        )

        selection_buttons = [
            sg.Sizer(0, 0),
            sg.Button('Set Targets', key=SET_TARGET_BTN, expand_x=True, expand_y=False),
            sg.Sizer(0, 0),
            sg.Button('same', key=MODE_SAME_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('diff', key=MODE_DIFF_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('change', key=MODE_CHANGE_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('fastClick', key=FAST_TRACK_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Button('Idle', key=IDLE_MODE_BTN, button_color = DISABLED_COLOR, visible=False, expand_x=True, expand_y=True),
            sg.Sizer(0, 0)
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
            sg.Sizer(0, 0)
            ]

        self.patience_slider = sg.Slider(range=(0, self.settings.get(MAX_PATIENCE)), default_value=5,
                expand_x=True, enable_events=True,
                orientation='horizontal', key=PATIENCE_SLIDER, tooltip='Patience level\nWait increment for each newly triggered tracker')

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

        detailsFont = 'Terminal'
        track_tab=[
            [sg.Sizer(625,0)],
            selection_buttons,
            [sg.Sizer(0,0)],
            [sg.Sizer(0,0), sg.Text(key=BIG_TOTAL, visible=False, expand_x=True, expand_y=True, font=(detailsFont, 35), justification='center')],
            [sg.Sizer(0,0), sg.Text(key=BIG_CPS, visible=False, expand_x=True, expand_y=True, font=(detailsFont, 22), justification='center', text_color='gold')], #DAA520
            [sg.Sizer(0,0), sg.Text(key=BIG_GOLD, visible=False, expand_x=True, expand_y=True, font=(detailsFont, 16), justification='center', text_color='gold')],
            [self.eventgraph.graph, sg.Sizer(0,0)],
            [sg.Sizer(0,0), self.patience_slider],
            [sg.Sizer(0,0), sg.ProgressBar(self.queue.patience_level, orientation='h', expand_x=True, size=(20, 5),  key=PATIENCE_PROGRESS_2, visible=False, bar_color='blue')],
            [sg.Sizer(0,0), sg.ProgressBar(self.settings.get(MAX_PATIENCE_STACK), orientation='h', expand_x=True, size=(20, 20), border_width= 3,  key=PATIENCE_PROGRESS, visible=False)],
            details,
            [self.target_table, sg.Sizer(0,0)],
            [sg.Sizer(0,0)],
            
            [sg.Frame('', bottom_row_frame, visible=True, key=BOTTOM_ROW_FRAME, expand_x=False, border_width=1), sg.Sizer(0,0)],
            [sg.Button('CLICK!', key=CLICK_BTN, visible=True, expand_x=True, expand_y=True)]
            
        ]

        # =========================== MAIN LAYOUT ===========================
        layout = [
            [sg.Sizer(0,0)],
            [sg.TabGroup([[
                sg.Tab('Track', track_tab, key=TRACK_TAB, element_justification='center'),
                sg.Tab('Settings', settings_tab, key=SETTINGS_TAB, element_justification='left')
            ]])],
            [sg.Sizer(0,0)],
        # [
        #     [sg.Frame('', bottom_row_frame, visible=True, key=BOTTOM_ROW_FRAME, expand_x=False, border_width=1), sg.Sizer(0,0)],
        #     sg.Button('CLICK!', key=CLICK_BTN, visible=True, expand_x=True, expand_y=True)
        # ]
        ]

        font = ("Arial", 12)

        # Create the window
        self.window = sg.Window("UltimateClicker", layout, location=(1100,100), font=font, element_justification='center')

    def toggle_collapsible(self, collapsible:Collapsible, collapse=None):
        if collapse is None:
            collapsible.collapsed = not collapsible.collapsed
        else:
            collapsible.collapsed = collapse

        self.window[collapsible.event_key].update(SYMBOL_DOWN if not collapsible.collapsed else SYMBOL_UP)
        self.window[collapsible.layout_key].update(visible= not collapsible.collapsed)

    def display_current(self):
        self.graph_cur.erase()
        cur = self.selected_target
        while cur == self.selected_target and self.selected_target is not None:
            try:
                self.draw_current()
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(f'UI.diplay_current() - display current failed: {e}')            
                self.graph_cur.erase()
                break

    def get_middle_of_main_window(self):
        try:
            location = self.window.CurrentLocation()
            size = self.window.size
            pLocation = (int(location[0] + size[0]/2), int(location[1] + size[1]/2))
            return pLocation
        except Exception as e:
            self.logger.error(f'UI.get_middle_of_main_window() - Failed: {e}')
    def information_popup(self, txt, duration=1, background='white'):

        sg.PopupAutoClose(txt, auto_close_duration=duration, location=self.get_middle_of_main_window(), keep_on_top=True, non_blocking=True, background_color=background)

    def load_last_auto_save(self):
        if self.get_last_saved() is None:
            self.load_targets('auto_save')
        else:
            self.load_targets(self.last_saved)
            
    def autosave(self):
        if self.settings.current_save is None:
            self.save_targets('auto_save')
        else:
            self.save_targets(self.settings.current_save)
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
        
        window = sg.Window('POPUP', layout, location=self.get_middle_of_main_window()).Finalize()
        
        while True:
            event, values = window.read()
            
            if event == sg.WINDOW_CLOSED:
                return None
            elif event == 'OK':
                break
            elif event == 'Cancel':
                break
            else:
                print('OVER')

        window.close()

        self.logger.debug(f'[Choose_file_popup] event:, {event}')            
        self.logger.debug(f'[Choose_file_popup] values: {values}')            

        if can_create and values and values['-NEWFILE-']:
            return values['-NEWFILE-']
        elif values and values['SELECTED']:
            return values['SELECTED'][0]
        else:
            return None

    def choose_load_file(self):
        files = [f for f in os.listdir(self.userdata_dir + self.settings.get(SAVE_FOLDER))]
        return self.Choose_file_popup(text="Choose file to load", data=files)

    def choose_save_file(self):
        files = [f for f in os.listdir(self.userdata_dir + self.settings.get(SAVE_FOLDER))]
        return self.Choose_file_popup(text="Choose file to save", data=files, can_create=True)

    def load_targets(self, save_file):
        self.logger.info(f'load_targets - Loading targets from {save_file}')            
        try:
            self.queue.clear_targets()
            file_path = self.userdata_dir + self.settings.get(SAVE_FOLDER) + save_file
            screenshot = self.cam.get_screen(caller='UI.LoadTargets()')
            with open(file_path, 'r') as file:
                csvreader = csv.reader(file)
                
                save_has_gold = False

                Thread(target=self.track_ready, name='TrackReady').start()
                for row in csvreader:
                    tar = None
                    typ = row[0]
                    if typ == 'Tracker':
                        tar = TrackerTarget(int(row[1]), int(row[2]), self.settings.get(TARGET_ZONE), detectionMode(int(row[3])), initial_screenshot=screenshot)
                    elif typ == 'Fast':
                        tar = FastTarget(int(row[1]), int(row[2]), initial_screenshot=screenshot)
                    elif typ == 'Idle':
                        tar = IdleTarget(int(row[1]), int(row[2]), initial_screenshot=screenshot)
                    elif typ == 'GOLD':
                        if row[1].isdigit():
                            save_has_gold = True
                            self.queue.golden_clicked = int(row[1])
                    elif typ == 'TIME':
                            self.settings.run_time = int(row[1])

                    if tar is not None:
                        try: 
                            tar.times_clicked = int(row[4]) 
                            self.add_target(tar, False) 
                        except: pass

                if not save_has_gold:
                    self.queue.golden_clicked = 0
                
                self.settings.current_save = save_file

        except Exception as e:
            self.logger.error(f'load_targets - Could not load targets from "{save_file}" ({e})')            

    def update_last_save(self, last_save):
        self.logger.info(f'UI.update_last_save() - Updating last save to {last_save}')            
        with open(self.userdata_dir + self.last_save_file, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['last_save', last_save])
            self.last_saved = last_save

    def get_last_saved(self):
        if self.last_saved is None:
            with open(self.userdata_dir + self.last_save_file, 'r') as file:
                csvreader = csv.reader(file)
                for row in csvreader:
                    if row[0] == 'last_save':
                        self.last_saved = row[1]
        return self.last_saved
    
    def save_targets(self, save_file):
        if len(self.targets) == 0:
            return
        try:
            self.logger.info(f'save_targets - Saving targets to {save_file}')            
            file_path = self.userdata_dir + self.settings.get(SAVE_FOLDER) + save_file
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                for tar in self.targets:
                    writer.writerow(tar.to_csv())

                writer.writerow(['GOLD', self.queue.golden_clicked])
                writer.writerow(['TIME', int(self.settings.run_time)])
                
            self.update_last_save(save_file)
            self.logger.info(f'save_targets - Targets saved successfuly to {save_file}')            
            self.information_popup('Save success', background='green')
        except Exception as e:
            self.logger.error(f'save_targets - Could not save files to "{save_file}" ({e})')            
            self.information_popup("Save Failed", background='red')

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
        if self.queue.OneQueue.has_one():
            next = self.queue.next_target
            if next is not None:
                self.draw(next[1], self.graph_next)
                self.last_next_target_drew = next
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

    def update_tabs(self):
        settings_visible = self.current_tab == SETTINGS_TAB
        if not settings_visible:  
            for coll in self.collapsibles:
                self.toggle_collapsible(coll, True)     
            self.logger.info(f'UI.update_tabs() - Settings tabs are now hidden')
        else:
            self.window[TARGET_TABLE].update(visible=False)

        track_visible = self.current_tab == TRACK_TAB


    def update_buttons(self):
        try:
            self.window[MODE_SAME_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.same else DISABLED_COLOR)
            self.window[MODE_DIFF_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.different else DISABLED_COLOR)
            self.window[MODE_CHANGE_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.change else DISABLED_COLOR)
            self.window[FAST_TRACK_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.fast else DISABLED_COLOR)
            self.window[IDLE_MODE_BTN].update(button_color = ENABLED_COLOR if self.mode == detectionMode.idle else DISABLED_COLOR)

            self.window[SET_TARGET_BTN].update(visible=not self.running)
            self.window[MODE_SAME_BTN].update(visible=self.setting_targets)
            self.window[MODE_DIFF_BTN].update(visible=self.setting_targets)
            self.window[MODE_CHANGE_BTN].update(visible=self.setting_targets)
            self.window[FAST_TRACK_BTN].update(visible=self.setting_targets)
            self.window[IDLE_MODE_BTN].update(visible=self.setting_targets)
            
            # self.window[COLOR_BTN].update(visible=self.setting_targets and self.mode in [detectionMode.same, detectionMode.different, detectionMode.change])

            self.window[PATIENCE_SLIDER].update(visible= not self.running)
            self.window[PATIENCE_PROGRESS].update(visible=self.running)
            self.window[PATIENCE_PROGRESS_2].update(visible=self.running)

            self.window[BOTTOM_ROW_FRAME].update(visible= not self.running)
            self.window[CLICK_BTN].update(visible= not self.running)
            self.window[BIG_CPS].update(visible=self.running and self.queue.has_fast_target())
            self.window[BIG_TOTAL].update(visible=self.running and self.queue.has_fast_target())
            self.window[EVENT_GRAPH].update(visible=self.running)# and self.queue.has_fast_target())
            self.window[BIG_GOLD].update(visible=self.running and self.settings.check_for_gold_cookie)

            Thread(target=self.update_cursor, name='UpdateCursor').start()

        except RuntimeError as e:
            self.logger.error(f'UI.update_buttons() - Could not run update button ({e})')            

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
        self.window[EVENT_GRAPH].update(visible=self.running)

        if self.queue.last_click is None:
            self.graph_last.erase()
        elif (self.last_target_drew is None or self.last_target_drew != self.queue.last_click):
            self.draw_last()

        if self.queue.next_target is None:
            self.graph_next.erase()
            self.last_next_target_drew = None
        elif (self.last_next_target_drew is None or self.last_next_target_drew != self.queue.next_target):
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

        # num_row = len(self.targets) if len(self.targets) <= 20 else 20
        # self.target_table.NumRows = num_row
        # self.target_table.TreeData = treedata
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

        self.eventgraph.update()
        self.window[BIG_GOLD].update(visible=self.running and self.settings.check_for_gold_cookie)

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
        elif self.running and (x,y) not in self.queue.get_allowed_positions():
            self.aborted = True
            # self.window.bring_to_front()

    def on_scroll(self, x, y, dx, dy):
        pass

    def on_click(self, x, y, button, pressed):
        if self.setting_targets and pressed:
            if self.is_click_inside_app(x, y):
                self.logger.debug('Click in app')            
                return
            target_zone = self.settings.get(TARGET_ZONE)
            if self.mode == detectionMode.same:
                tar = TrackerTarget(x, y, target_zone, detectionMode.same)
            elif self.mode == detectionMode.different:
                tar = TrackerTarget(x, y, target_zone, detectionMode.different)
            elif self.mode == detectionMode.change:
                tar = TrackerTarget(x, y, target_zone, detectionMode.change)
            elif self.mode == detectionMode.fast:
                if self.queue.has_fast_target():
                    self.remove_target(self.queue.fast_target)
                tar = FastTarget(x, y, 0)
            elif self.mode == detectionMode.idle:
                tar = IdleTarget(x, y, 60)
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
        self.logger.info('UI.track_ready() thread started')            
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
                    self.logger.info(f'UI.track_ready() - Waiting for targets ready ({n}/{len(self.targets)})')            
            except Exception as e:
                self.logger.error(f'UI.track_ready() - failed ({e})')            
                break

        self.all_targets_ready = True
        self.queue.has_update = True
        self.logger.info('UI.track_ready() thread finished')            

        # self.window[CLICK_BTN].update(text='Click!')

    def update_patience_slider(self):
        if self.queue.has_tracker_targets():
            self.window[PATIENCE_PROGRESS].update(visible=self.running)
            self.window[PATIENCE_PROGRESS_2].update(visible=self.running)
            self.window[PATIENCE_SLIDER].update(visible= not self.running)

            if not self.queue.waiting:
                self.window[PATIENCE_PROGRESS_2].update(current_count=0, bar_color='blue')
                self.window[PATIENCE_PROGRESS].update(current_count=self.queue.additionnal_wait, bar_color='blue')
                # last_click_id = self.queue.last_click.targetid if self.queue.last_click is not None else 'None'
                # self.window[NEXT_TARGET].update(value=f'Next Target ID: Waiting for target\nLast Target ID: {last_click_id}')
            else:
                self.window[PATIENCE_PROGRESS].update(current_count=self.queue.additionnal_wait, bar_color='green', max=self.settings.get(MAX_PATIENCE_STACK))
                self.window[PATIENCE_PROGRESS_2].update(current_count=self.queue.wait_prog, max=self.queue.patience_level, bar_color='green')
                # if self.queue.next_target is not None:
                    # last_click_id = self.queue.last_click.targetid if self.queue.last_click is not None else 'None'
                    # self.window[NEXT_TARGET].update(value=f'Next Target ID: {self.queue.next_target[1].targetid}\nLast Target ID: {last_click_id}')
        else:
            self.window[PATIENCE_PROGRESS_2].update(visible=False)
            self.window[PATIENCE_PROGRESS].update(visible=False)


    def run_queue(self):
        self.logger.info('UI.run_queue() thread started')            
        self.setting_targets = False
        self.running = True
        self.aborted = False


        self.autosave()

        self.queue.start()
        
        self.update_buttons()

        while not self.aborted:
            time.sleep(1)

        self.queue.stop()

        self.running = False

        self.autosave()
        self.update_graphs()
        self.update_buttons()

        self.logger.info('UI.run_queue() thread finished')            

    def add_target(self, tar, track=True):
        if tar in self.queue.targets:
            self.logger.warn('UI.add_target() - Target already in queue')            
            return
        
        self.queue.add_target(tar)
        self.targets = self.queue.targets
        if track:
            Thread(target=self.track_ready, name='TrackReady').start()

    def remove_target(self, tar):
        self.queue.remove_target(tar)

    # TODO: Could be in settings class
    def update_settings(self, values):

        value = values[SAVE_FOLDER]
        if value != '':
            self.settings.set(SAVE_FOLDER, values[SAVE_FOLDER])
        self.window[SAVE_FOLDER_CUR].update(value=self.settings.get(SAVE_FOLDER))
        self.window[SAVE_FOLDER].update(value='')

        value = values[TARGET_ZONE]
        if value != '' :
            if value.isdigit() and int(value) > 1:
                self.settings.set(TARGET_ZONE, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid target zone value ({value})')            
        self.window[TARGET_ZONE_CUR].update(value=self.settings.get(TARGET_ZONE))
        self.window[TARGET_ZONE].update(value='')

        value = values[UI_UPDATE]
        if value != '':
            if value.isdigit() and int(value) >= 1:
                self.settings.set(UI_UPDATE, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid UI update rate value ({value})')
        self.window[UI_UPDATE_CUR].update(value=self.settings.get(UI_UPDATE))
        self.window[UI_UPDATE].update(value='')

        value = values[TRIGGER_CHECK_RATE]
        if value != '':
            if value.isdigit() and int(value) >= 1:
                self.settings.set(TRIGGER_CHECK_RATE, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid trigger check rate value ({value})')
        current_value = self.settings.get(TRIGGER_CHECK_RATE)
        display_value = current_value if current_value > 0 else str(current_value) + " (Same as patience)"
        self.window[TRIGGER_CHECK_RATE_CUR].update(value=display_value)
        self.window[TRIGGER_CHECK_RATE].update(value='')

        value = values[GOLD_DIGGER]
        if value != '':
            if isinstance(value, bool):
                self.settings.check_for_gold_cookie = value

            else:
                self.logger.warn(f'UI.update_settings - invalid GOLD_DIGGER value ({value})')
        self.window[GOLD_DIGGER_CUR].update(value=f'{"CLICKING GOLD!!!" if self.settings.check_for_gold_cookie else "Nope.. T_T"}')

        value = values[GOLD_FREQ]
        if value != '':
            if value.isdigit() and int(value) >= 1:
                self.settings.set(GOLD_FREQ, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid gold seek freq value ({value})')
        self.window[GOLD_FREQ_CUR].update(value=self.settings.get(GOLD_FREQ))
        self.window[GOLD_FREQ].update(value='')

        value = values[MAX_PATIENCE]
        if value != '':
            if value.isdigit() and int(value) > 0:
                self.settings.set(MAX_PATIENCE, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid max patience value ({value})')
        self.window[MAX_PATIENCE_CUR].update(value=self.settings.get(MAX_PATIENCE))
        self.window[PATIENCE_SLIDER].update(range=(0, self.settings.get(MAX_PATIENCE)))
        self.window[MAX_PATIENCE].update(value='')

        value = values[MAX_PATIENCE_STACK]
        if value != '':
            if value.isdigit() and int(value) > 0:
                self.settings.set(MAX_PATIENCE_STACK, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid max patience value ({value})')
        self.window[MAX_PATIENCE_STACK_CUR].update(value=self.settings.get(MAX_PATIENCE_STACK))
        self.window[PATIENCE_PROGRESS].update(max=self.settings.get(MAX_PATIENCE_STACK))
        self.window[MAX_PATIENCE_STACK].update(value='')

        value = values[TARGET_CPS]
        if value != '':
            if value.isdigit() and int(value) >= 0:
                self.settings.set(TARGET_CPS, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid Target cps value ({value})')
        self.window[TARGET_CPS_CUR].update(value=self.settings.get(TARGET_CPS))
        self.window[TARGET_CPS].update(value='')

        value = values[CPS_UPDATE]
        if value != '':
            if value.replace('.','',1).isdigit() and float(value) >= 0:
                self.settings.set(CPS_UPDATE, float(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid cps update value ({value})')
        self.window[CPS_UPDATE_CUR].update(value=self.settings.get(CPS_UPDATE))
        self.window[CPS_UPDATE].update(value='')

        value = values[AUTOSAVE_FREQ]
        if value != '':
            if value.isdigit() and int(value) >= 0:
                self.settings.set(AUTOSAVE_FREQ, int(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid autosave_freq value ({value})')
        self.window[AUTOSAVE_FREQ_CUR].update(value=self.settings.get(AUTOSAVE_FREQ))
        self.window[AUTOSAVE_FREQ].update(value='')

        value = values[KP]
        if value != '':
            if value.replace('.','',1).replace('-','',1).isdigit():
                self.settings.set(KP, float(value))

            else:
                self.logger.warn(f'UI.update_settings - invalid KP value ({value})')
        self.window[KP_CUR].update(value=self.settings.get(KP))
        self.window[KP].update(value='')

        value = values[KI]
        if value != '':
            if value.replace('.','',1).replace('-','',1).isdigit():
                self.settings.set(KI, float(value))
            else:
                self.logger.warn(f'UI.update_settings - invalid KI value ({value})')
        self.window[KI_CUR].update(value=self.settings.get(KI))
        self.window[KI].update(value='')
        
        value = values[KD]
        if value != '':
            if value.replace('.','',1).replace('-','',1).isdigit():
                self.settings.set(KD, float(value))
            else:
                self.logger.warn(f'UI.update_settings - invalid KD value ({value})')
        self.window[KD_CUR].update(value=self.settings.get(KD))
        self.window[KD].update(value='')

        value = values[LOG_LEVEL]
        if value != '':
            if value.isdigit() and int(value) >= 0:
                self.settings.set(LOG_LEVEL, int(value))
                self.logger.set_log_level(int(value))
            else:
                self.logger.warn(f'UI.update_settings - invalid log level value ({value})')
        self.window[LOG_LEVEL_CUR].update(value=self.settings.get(LOG_LEVEL))
        self.window[LOG_LEVEL].update(value='')

    def run(self):
        try:
            self.logger.info('UI.run() Started')
            # Create an event loop
            self.click_listener_thread = Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
            self.click_listener_thread.name='ClickListener'
            self.click_listener_thread.start()

            while True:
                start = time.time()
                timeout = 250 if not self.running else self.settings.get(UI_UPDATE)
                event, values = self.window.read(timeout=timeout, timeout_key='NA')
                if event != 'NA':
                    self.logger.info(f'UI.run() - Handling event [{event}]')

                if values is not None and values[4] == SETTINGS_TAB and self.current_tab != SETTINGS_TAB:
                    self.current_tab = SETTINGS_TAB
                    self.update_tabs()
                elif values is not None and values[4] == TRACK_TAB and self.current_tab != TRACK_TAB:
                    self.current_tab = TRACK_TAB
                    self.update_tabs()

                # End program if user closes window or
                # presses the OK button
                if event in [sg.WIN_CLOSED, 'CLOSE', 'OK']:
                    break

                # if self.running:
                #     self.eventgraph.add_entry(EventEntry(time.time(), 'UI_update'))

                if self.queue.has_update:
                    self.queue.has_update = False
                    self.targets = self.queue.targets

                if self.running:
                    autosave_freq = self.settings.get(AUTOSAVE_FREQ)
                    if autosave_freq > 0 and time.time() - self.last_autosave >= autosave_freq*60:
                        self.logger.info(f'UI.run() - Automatic save (Set for every {autosave_freq} minutes)')
                        self.eventgraph.add_event_entry(EventEntry(time.time(), 'autosave'))
                        self.autosave()
                    self.settings.run_time += (time.time()-start)
                    
                self.update_graphs()
                self.update_patience_slider()

                self.update_run_details() 
                self.update_target_table()

                if event == 'NA':
                    continue

                elif event == PATIENCE_SLIDER:
                    self.queue.patience_level = int(values[PATIENCE_SLIDER])
                    self.logger.info(f'UI.run() - Updated patience level ({self.queue.patience_level})')

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

                elif event == IDLE_MODE_BTN:
                    self.set_mode(detectionMode.idle)

                elif event == SAVE_BTN:
                    file = self.choose_save_file()
                    if file is not None:
                        self.save_targets(file)

                elif event == LOAD_BTN:
                    file = self.choose_load_file()
                    if file is not None:
                        self.load_targets(file)

                elif event == LOAD_LAST_BTN:
                    self.load_targets(self.get_last_saved())

                elif event == CLEAR_BTN:
                    self.queue.clear_targets()
                    self.settings.current_save = None
                    self.selected_target = None

                elif event == CLICK_BTN:
                    if not self.are_targets_ready():
                        self.logger.warn(f'UI.run() - Not all targets ready. Cant run.')
                        # print('WARN - Not all targets ready. Cant run.')
                        continue
                    time.sleep(0.5)
                    Thread(target=self.run_queue, daemon=True, name='RunQueue').start()
                    self.window[BOTTOM_ROW_FRAME].update(visible=False)
                    self.window[CLICK_BTN].update(visible=False)

                # Collapsibles
                elif event.startswith('-COLLAPSE_'): 
                    for collapsible in self.collapsibles:
                        if event == collapsible.event_key:
                            self.toggle_collapsible(collapsible)

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

                elif event == SAVE_SETTINGS:
                    self.update_settings(values)
                    self.settings.save()

                elif event == RESET_SETTINGS:
                    self.settings.reset_userdata()
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
        finally:

            self.logger.info('UI.run() - UI.run() Finished')
        
if __name__ == '__main__':
    try:
        app = App()
        app.run()

    except Exception as e:
        raise e
    finally:
        cursor.set_cursor_default()