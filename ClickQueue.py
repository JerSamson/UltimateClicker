from Target import *
from queue import Queue, PriorityQueue
from threading import Lock, Thread
import time
from RepeatedTimer import RepeatedTimer

class ClickQueue:
    def __init__(self) -> None:
        self.click_queue = PriorityQueue()
        self.targets = []
        self.fast_target = None
        self.running = False
        self.has_update = False
        self.lock = Lock()
        self.add_wait_lock = Lock()
        self.fast_thread = None
        self.main_thread = None
        self.trigger_thread = None
        self.id_cnt = 0
        self.using_smart_wait = True
        self.additionnal_wait = 0
        self.patience_level   = 5 #s

    def increment_patience(self, inc):
        self.add_wait_lock.acquire()
        if self.additionnal_wait + inc < 10 and self.additionnal_wait + inc >= 0:
            self.additionnal_wait += inc
            print(f'Patience {("+" if inc >= 0 else "-")}{abs(inc)}\t({self.additionnal_wait})')
        self.add_wait_lock.release()

    def get_additionnal_wait(self):
        self.add_wait_lock.acquire()
        w = self.additionnal_wait
        self.add_wait_lock.release()
        return w
    
    def has_fast_target(self):
        return self.fast_target is not None and self.fast_target.enable

    def stop(self):
        self.running = False
        for tar in self.targets:
            tar.stop()
        
    def start(self):
        if self.running:
            return
        
        while self.main_thread is not None and self.main_thread.is_alive():
            time.sleep(1)
            print('ClickerQueue Old thread still alive')

        
        self.running = True
        for tar in self.targets:
            tar.start()
        self.main_thread = Thread(target=self.run, name='ClickerQueueMain')
        self.main_thread.start()

    def add_target(self, tar):
        if isinstance(tar, FastTarget):
            if self.fast_target is None:
                self.fast_target = tar
                self.has_update = True
            else:
                print('Only one fast target allowed')
                # raise Exception('Only one fast target allowed')
        
        tar.targetid = self.id_cnt
        self.id_cnt+=1
        self.targets.append(tar)
        self.has_update = True


    def clear_targets(self):
        self.targets.clear()
        self.fast_target=None
        self.id_cnt = 0
        self.has_update = True

    def remove_target(self, tar):
        if isinstance(tar, FastTarget):
            if self.fast_target is not None:
                self.fast_target = None
        self.targets.remove(tar)
        self.has_update = True

    def wait_additionnal_time(self):
        add_wait = self.get_additionnal_wait()

        if add_wait <= 0:
            return False
        
        while add_wait > 0 and self.running:
            self.increment_patience(-1)
            time.sleep(self.patience_level)
            add_wait = self.get_additionnal_wait()
        print('Done waiting.')
        return True
    def update_thread(self):
        if self.running:
            for tar in self.targets:
                if tar.enable and tar.check_trigger() and tar.handled:
                    tar.handled=False
                    self.increment_patience(1)
                    self.click_queue.put((tar.priority, tar))
                    self.has_update = True

    def handle_task(self, task):
        try:
            self.lock.acquire()
            task.handle()
        except Exception as e:
            print('Task was too much to handle')
        finally:
            self.lock.release()

    def fast_click_thread(self):
        if self.has_fast_target():
            while self.running and self.has_fast_target():
                self.handle_task(self.fast_target)
                if not self.running: break

    def run(self):
        if self.has_fast_target():
            self.fast_thread = Thread(target=self.fast_click_thread, name='FastClick')
            self.fast_thread.start()
            #TODO Could be parameter on UI
            tracker_Interval = 1
            self.trigger_thread = RepeatedTimer(tracker_Interval, self.update_thread)
            if not self.trigger_thread.is_running:
                self.trigger_thread.start()

        while self.running:
            task = self.get_if_any()
            if task is not None and task[1].check_trigger():
                
                if self.wait_additionnal_time():
                    self.click_queue.put(task)
                    continue

                task[1].handled = False
                self.handle_task(task[1])
                self.increment_patience(1)


        self.stop()
        self.trigger_thread.stop()
        if self.has_fast_target():
            self.fast_thread.join(timeout=10)
    def get_if_any(self):
        try:
            return self.click_queue.get_nowait()
        except:
            return None
    