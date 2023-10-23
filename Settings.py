from singleton import Singleton

class settingsEntry:
    def __init__(self, name) -> None:
        pass

class Settings(metaclass=Singleton):
    def __init__(self) -> None:
        self.save_dir = 'SavedTargets\\'
        self.target_zone = 5
        self.ui_update = 0.1
        self.trigger_check_rate = None
        self.check_for_gold_cookie = True
        self.max_patience = 20
        self.max_patience_stack = 10
        self.target_cps = 100
        self.cps_update_delay = 0.5