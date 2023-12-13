from singleton import Singleton
import PySimpleGUI as sg

class SettingEntry:
    def __init__(self, text, input_key, cur_val_key, cur_value, tooltip=None, text_width=20, text_color='light gray') -> None:
        self.text = text
        self.input_key = input_key
        self.cur_val_key = cur_val_key
        self.cur_value = cur_value
        self.text_color = text_color
        self.text_width = text_width
        self.tooltip = tooltip
        
    def layout(self):
        return [
            sg.Text(text=self.text, size=(self.text_width,1), tooltip=self.tooltip),
            sg.InputText(key=self.input_key, size=(15,1)),
            sg.Text(key=self.cur_val_key, text=self.cur_value, text_color=self.text_color, auto_size_text=True)
            ]

class Settings(metaclass=Singleton):
    def __init__(self) -> None:
        self.current_save = None
        self.save_dir = 'SavedTargets\\'
        self.target_zone = 5
        self.ui_update = 100
        self.trigger_check_rate = None
        self.check_for_gold_cookie = True
        self.check_for_gold_freq = 5
        self.max_patience = 20
        self.max_patience_stack = 10
        self.target_cps = 50
        self.cps_update_delay = 0.033
        self.autosave_freq = 5 # min

        self.p = 0.00003
        self.i = 0.0050
        self.d = 0.000000025

        self.run_time = 0

        self.log_level = 0