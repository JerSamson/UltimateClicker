from Target import *
from queue import Queue
from threading import Thread
import time
from RepeatedTimer import RepeatedTimer

class ClickQueue:
    def __init__(self) -> None:
        self.click_queue = Queue()
        self.targets = []
        self.fast_target = None
        self.running = False
        RepeatedTimer(1, self.update_thread)
        self.id_cnt = 0
    def has_fast_target(self):
        return self.fast_target is not None

    def stop(self):
        self.running = False
        for tar in self.targets:
            tar.stop()

    def start(self):
        self.running = True
        for tar in self.targets:
            tar.start()

    def add_target(self, tar):
        if isinstance(tar, FastTarget):
            if self.fast_target is None:
                self.fast_target = tar
                return
            else:
                print('Only one fast target allowed')
                # raise Exception('Only one fast target allowed')
        
        tar.targetid = self.id_cnt
        self.id_cnt+=1
        self.targets.append(tar)

    def remove_target(self, tar):
        if isinstance(tar, FastTarget):
            if self.fast_target is not None:
                self.fast_target = None
        
        self.targets.remove(tar)


    def update_thread(self):
        if self.running:
            for tar in self.targets:
                if tar.check_trigger() and tar.handled:
                    tar.handled=False
                    self.click_queue.put(tar)

    def get_if_any(self):
        try:
            return self.click_queue.get_nowait()
        except:
            return None
    