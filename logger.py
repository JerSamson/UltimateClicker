from singleton import Singleton
from enum import Enum

class LogType(Enum):
    INFO    =   0
    WARN    =   1
    ERR     =   2
    DEBUG   =   3


log_hierarchy = {
    LogType.ERR   : 0,
    LogType.WARN  : 1,
    LogType.INFO  : 2,
    LogType.DEBUG : 3
}

class Logger(metaclass=Singleton):
    def __init__(self, log_level=2) -> None:
        self.log_level = log_level
        self.medium = ['terminal']
        self.prefix = {
            LogType.ERR  : "ERROR",
            LogType.WARN : "WARN",
            LogType.INFO : "INFO",
            LogType.DEBUG: "DEBUG"
        }

    def set_log_level(self, lvl:LogType):
        self.log_level = lvl

    def info(self, msg):
        self.log(LogType.INFO, msg)

    def warn(self, msg):
        self.log(LogType.WARN, msg)

    def debug(self, msg):
        self.log(LogType.DEBUG, msg)

    def error(self, msg):
        self.log(LogType.ERR, msg)

    def log(self, logtype:LogType, msg):
        if log_hierarchy[logtype] > self.log_level:
            return False
        
        if 'terminal' in self.medium:
            print(f'{self.prefix[logtype]} - {msg}')
            
        return True

