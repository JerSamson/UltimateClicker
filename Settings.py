import os
from singleton import Singleton
import PySimpleGUI as sg
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import logger
import os.path
import math

# SETTINGS    
SETTINGS_TAB             = '-SETTINGS_TAB-'
     
#   GENERAL
GENERAL_FRAME            = '-GENERAL_FRAME-'
COLLAPSE_GENERAL_FRAME   = '-COLLAPSE_GENERAL_FRAME-'
SAVE_FOLDER              = '-SAVE_DIR-'
SAVE_FOLDER_CUR          = '-SAVE_DIR_CUR-'
UI_UPDATE                = '-UI_UPDATE-'
UI_UPDATE_CUR            = '-UI_UPDATE_CUR-'
AUTOSAVE_FREQ            = '-AUTOSAVE_FREQ-'
AUTOSAVE_FREQ_CUR        = '-AUTOSAVE_FREQ_CUR-'

#   PATIENCE
PATIENCE_FRAME           = '-PATIENCE_FRAME-'
COLLAPSE_PATIENCE_FRAME  = '-COLLAPSE_PATIENCE_FRAME-'
MAX_PATIENCE             = '-MAX_PATIENCE-'
MAX_PATIENCE_CUR         = '-MAX_PATIENCE_CUR-'
MAX_PATIENCE_STACK       = '-MAX_PATIENCE_STACK-'
MAX_PATIENCE_STACK_CUR   = '-MAX_PATIENCE_STACK_CUR-'

#   CPS
CPS_FRAME                = '-CPS_FRAME-'
COLLAPSE_CPS_FRAME       = '-COLLAPSE_CPS_FRAME-'
TARGET_CPS               = '-TARGET_CPS-'
TARGET_CPS_CUR           = '-TARGET_CPS_CUR-'
CPS_UPDATE               = '-CPS_UPDATE-'
CPS_UPDATE_CUR           = '-CPS_UPDATE_CUR-'

#   TRACKER
TRACKER_FRAME            = '-TRACKER_FRAME-'
COLLAPSE_TRACKER_FRAME   = '-COLLAPSE_TRACKER_FRAME-'
TARGET_ZONE              = '-TARGET_ZONE-'
TARGET_ZONE_CUR          = '-TARGET_ZONE_CUR-'
TRIGGER_CHECK_RATE       = '-TRIGGERCHECK-'
TRIGGER_CHECK_RATE_CUR   = '-TRIGGERCHECKCUR-'

#   COOKIE
COOKIE_FRAME             = '-COOKIE_FRAME-'
COLLAPSE_COOKIE_FRAME    = '-COLLAPSE_COOKIE_FRAME-'
GOLD_DIGGER              = '-GOLD_DIG'
GOLD_DIGGER_CUR          = '-GOLD_DIG_CUR'
GOLD_FREQ                = '-GOLD_FREQ-'
GOLD_FREQ_CUR            = '-GOLD_FREQ_CUR-'

#   PID
PID_FRAME                = '-PID_FRAME-'
COLLAPSE_PID_FRAME       = '-COLLAPSE_PID_FRAME-'
KP                       = '-KP-'
KP_CUR                   = '-KP_CUR-'
KI                       = '-KI-'
KI_CUR                   = '-KI_CUR-'
KD                       = '-KD-'
KD_CUR                   = '-KD_CUR-'

#   DEBUG
DEBUG_FRAME              = '-DEBUG_FRAME-'
COLLAPSE_DEBUG_FRAME     = '-COLLAPSE_DEBUG_FRAME-'
LOG_LEVEL                = '-LOG_LEVEL-'  
LOG_LEVEL_CUR            = '-LOG_LEVEL_CUR-'  
ADVANCED_GRAPH_INFO      = '-ADVANCED_GRAPH_INFO-'
ADVANCED_GRAPH_INFO_CUR  = '-ADVANCED_GRAPH_INFO_CUR-'

class SettingEntry:
    def __init__(self, text, input_key, cur_val_key, type, tooltip=None, text_width=20, text_color='light gray', min=-math.inf, max=math.inf) -> None:
        self.text = text
        self.input_key = input_key
        self.cur_val_key = cur_val_key
        self.text_color = text_color
        self.text_width = text_width
        self.type = type
        self.tooltip = tooltip
        self.cur_value = None
        self.min = min
        self.max = max
        
    def layout(self):
        if self.type == bool:
            return [
                sg.Checkbox(text=self.text, key=self.input_key, size=(self.text_width,1), tooltip=self.tooltip),
                sg.Text(key=self.cur_val_key, text=self.cur_value, text_color=self.text_color, auto_size_text=True)
                ]
        else:
            return [
                sg.Text(text=self.text, size=(self.text_width,1), tooltip=self.tooltip),
                sg.InputText(key=self.input_key, size=(15,1)),
                sg.Text(key=self.cur_val_key, text=self.cur_value, text_color=self.text_color, auto_size_text=True)
                ]


class Settings(metaclass=Singleton):
    def __init__(self) -> None:
        self.entries = []
        self.logger = logger.Logger()
        self.cwd = os.path.dirname(os.path.realpath(__file__)) + '\\'
        self.userdata_dir = self.cwd + 'UserData\\'
        self.preferences_dir = self.userdata_dir + 'Settings\\'
        self.defaultdata_file = self.preferences_dir + "Default.xml"
        self.userdata_file = self.preferences_dir + 'user_settings.xml'

        self.check_for_gold_cookie = True
        self.current_save = None

        # self.save_dir = 'SavedTargets\\'
        # self.target_zone = 5
        # self.ui_update = 100
        # self.trigger_check_rate = None
        # self.check_for_gold_freq = 5
        # self.max_patience = 20
        # self.max_patience_stack = 10
        # self.target_cps = 50
        # self.cps_update_delay = 0.033
        # self.autosave_freq = 5 # min

        # self.p = 0.00003
        # self.i = 0.0050
        # self.d = 0.000000025

        self.run_time = 0

        self.log_level = 0

    def has_user_settings(self):
        return os.path.isfile(self.userdata_file) 

    def update_settings(self, values):
        if values is None:
            return
        for entry in self.entries:
            value = values[entry.input_key]
            if value != '':
                if entry.type == int:
                    if value.replace('-','',1).isdigit() and int(value) >= entry.min and int(value) <= entry.max:
                        self.set(entry.input_key, int(value))
                        self.logger.info(f'Settings.update_settings() - {entry.input_key} updated to {value}')            
                    else:
                        self.logger.warn(f'Settings.update_settings() - invalid value for {entry.input_key} (Should be integer between [{entry.min, entry.max}] but got {value})')            

                elif entry.type == float:
                    if value.replace('.','',1).replace('-','',1).isdigit() and float(value) >= entry.min and float(value) <= entry.max:
                        self.set(entry.input_key, float(value))
                        self.logger.info(f'Settings.update_settings() - {entry.input_key} updated to {value}')            
                    else:
                        self.logger.warn(f'Settings.update_settings() - invalid value for {entry.input_key} (Should be float between [{entry.min, entry.max}] but got {value})')            

                elif entry.type == str:
                    self.set(entry.input_key, str(value))
                    self.logger.info(f'Settings.update_settings() - {entry.input_key} updated to {value}')            

                elif entry.type == bool:
                    self.set(entry.input_key, bool(value))
                    self.logger.info(f'Settings.update_settings() - {entry.input_key} updated to {value}')            
                


    def get(self, key):
        entries = [e for e in self.entries if e.input_key == key]
        if len(entries) > 0 and isinstance(entries[0], SettingEntry) and entries[0].cur_value is not None:
            entry = entries[0]
            if entry.type == int:
                return int(entry.cur_value)
            elif entry.type == float:
                return float(entry.cur_value)
            elif entry.type == bool:
                return str(entry.cur_value).lower() == 'true'
            elif entry.type == str:
                return entry.cur_value
        else:
            self.logger.error(f'Settings.get() - No entries with key "{key}"')
            return None
        
    def set(self, key, value):
        entry = [e for e in self.entries if e.input_key == key]
        if len(entry) > 0 and isinstance(entry[0], SettingEntry):
            entry[0].cur_value = value
        else:
            self.logger.error(f'Settings.set() - No entries with key "{key}"')

    def add_entry(self, entry:SettingEntry) -> SettingEntry:
        if entry in self.entries:
            self.logger.warn(f'Settings.add_entry() - {entry.input_key} is already in list')
        else:
            self.entries.append(entry)
            self.logger.info(f'Settings.add_entry() - {entry.input_key} setting entry added')
        return entry        

    def reset_userdata(self):
        if self.has_user_settings():
            self.logger.info(f'Settings.reset_userdata() - Userdata preferences cleared')
            os.remove(self.userdata_file)
            self.load()
        else:
            self.logger.info(f'Settings.reset_userdata() - No userdata preferences found')

    def save(self):
        data = ET.Element('Settings')
        for entry in self.entries:
            el = ET.SubElement(data, 'Setting')
            el.set('name', str(entry.input_key))
            el.set('value', str(entry.cur_value))
        
        b_xml = ET.tostring(data)

        with open(self.userdata_file, "wb") as f:
            f.write(b_xml)
            self.logger.info(f'Settings.save() - Settings saved to {self.userdata_file}')

    def load(self):
        if self.has_user_settings():
            file=self.userdata_file
        else:
            file=self.defaultdata_file

        self.logger.info(f'Settings.load() - Loading data from {file}')

        with open(file, 'r') as f:
            data = f.read()
            
        bs_data = BeautifulSoup(data, 'xml')
        
        for entry in bs_data.find_all('Setting'):
            matching_entry = [e for e in self.entries if e.input_key == entry['name']]
            if len(matching_entry) > 0:
                matching_entry[0].cur_value = entry['value']
                self.logger.info(f'Settings.load() - Loaded setting entry ({entry["name"]}:{entry["value"]})')
            else:
                self.logger.warn(f'Settings.load() - Found setting with no entry ({entry["name"]})')
