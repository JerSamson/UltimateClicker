from Target import *
from threading import Lock, Thread
import time
from RepeatedTimer import RepeatedTimer
import ctypes
from ClickQueue import *
# def ctype_async_raise(target_tid, exception):
#     ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(target_tid), ctypes.py_object(exception))
#     # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc
#     if ret == 0:
#         raise ValueError("Invalid thread ID")
#     elif ret > 1:
#         # Huh? Why would we notify more than one threads?
#         # Because we punch a hole into C level interpreter.
#         # So it is better to clean up the mess.
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")
    
class SelfDestructException(Exception):
    pass

class ClickHandler:
    def __init__(self) -> None:
        self.click_queue = ClickQueue()
        self.OneQueue = UnitQueue()
        self.targets = []
        self.fast_target = None
        self.running = False
        self.has_update = False
        self.handle_lock = Lock()
        self.add_wait_lock = Lock()
        self.fast_thread = None
        self.main_thread = None
        self.trigger_thread = None
        self.id_cnt = 0
        self.using_smart_wait = True
        self.additionnal_wait = 0
        self.patience_level   = 5 #s
        self.patience_resolution   = 1
        self.waiting = False
        self.wait_prog = 0
        self.next_target = None
        self.last_click = None
        self.wait_resolution = 5
        self.handling_one = False

    def wait(self, delay):
        if delay <= 1:
            time.sleep(delay)
        else:
            for i in range(delay):
                for j in range(self.wait_resolution):
                    time.sleep(1/self.wait_resolution)
                    if not self.running:
                        print('INFO - Aborted wait because ClickHandler is not running anymore')
                        return

    def increment_patience(self, inc):
        self.add_wait_lock.acquire()
        try:
            if self.additionnal_wait + inc < 10 and self.additionnal_wait + inc >= 0:
                self.additionnal_wait += inc
                # print(f'Patience {("+" if inc >= 0 else "-")}{abs(inc)}\t({self.additionnal_wait})')
        except Exception as e:
            print(f'Increment patience failed ({e})')
        finally:
            self.add_wait_lock.release()

    def get_additionnal_wait(self):
        self.add_wait_lock.acquire()
        w = self.additionnal_wait
        self.add_wait_lock.release()
        return w
    
    def has_fast_target(self):
        return self.fast_target is not None and self.fast_target.enable
 
    def has_tracker_targets(self):
        return len([t for t in self.targets if isinstance(t, TrackerTarget) and t.enable]) > 0

    # def empty_queue(self):
    #     while not self.click_queue.qsize() == 0:
    #         self.get_from_queue()

    def stop(self):
        self.running = False
        self.handling_one = False

        for tar in self.targets:
            tar.stop()
        self.click_queue.empty_queue()
        
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
        tar.targetid = self.id_cnt
        self.id_cnt+=1
        self.targets.append(tar)
        self.has_update = True

    def is_in_queue(self, tar):        
        return self.click_queue.is_in_queue(tar)

    def add_to_queue_if_new(self, tar):
        return self.click_queue.add_if_unique(tar)
       
    def get_fast_targets(self):
        return [tar for tar in self.targets if isinstance(tar, FastTarget) and tar.enable]

    def allocate_single_fast_target(self):
        potentials_targets = self.get_fast_targets()
        n_pot = len(potentials_targets)
        if n_pot == 0:
            self.fast_target = None
        elif n_pot == 1:
            self.fast_target = potentials_targets[0]
        else:
            for i in range(n_pot):
                if i == 1:
                    self.fast_target = potentials_targets[i]
                else:
                    potentials_targets[i].enable = False
        self.has_update = True

    def get_from_queue(self):
        return self.click_queue.get_if_any()

    def clear_targets(self):
        self.stop()
        self.targets.clear()
        self.click_queue.empty_queue()
        self.next_target=None
        self.fast_target=None
        self.id_cnt = 0
        self.has_update = True

    def remove_target(self, tar):
        if tar is self.fast_target:
            self.fast_target = None
        self.targets.remove(tar)
        self.has_update = True

    def wait_additionnal_time(self):
        add_wait = self.get_additionnal_wait()

        if add_wait <= 0:
            return False
        
        i = 0
        self.waiting = True
        while add_wait > 0 and self.running:
            self.has_update = True
            for i in range(1, self.patience_level*self.patience_resolution+1):
                if not self.running:
                    self.next_target = None
                    break
                self.wait_prog = self.patience_level - i/self.patience_resolution
                self.has_update = True
                self.wait(1/self.patience_resolution)

            self.wait_prog = self.patience_level
            self.increment_patience(-1)
            self.has_update = True
            self.click_queue.clean_queue()
            self.change_if_higher_priority()
            add_wait = self.get_additionnal_wait()
            self.has_update = True

        self.waiting = False
        self.has_update = True
        print('INFO - Done waiting.')
        return True
    
    def update_thread(self):
        print('INFO - ClickHandler.update_thread() thread started')
        if self.running:
            try:


                for tar in self.targets:
                    if tar.enable and tar.check_trigger():
                        if self.next_target is None or tar is not self.next_target[1]:
                            if self.add_to_queue_if_new((tar.priority, tar)):
                                self.increment_patience(1)
                                print(f'INFO - Added increment for target {tar.targetid}')
                                self.has_update = True

                if not self.click_queue.is_empty() and not self.OneQueue.has_one():
                    if self.OneQueue.tryPut(self.next_target):
                        print(f'INFO - Starting handling thread (predicted ID: {self.click_queue.first_id()})')
                        self.increment_patience(1)
                        Thread(target=self.handle_one, name='HandleOne', daemon=True).start()

                self.targets = self.click_queue.clean_queue(self.targets)

            except Exception as e:
                print(f'ERROR - ClickHandler.update_thread() - thread failed ({e})')
            finally:
                print('INFO - ClickHandler.update_thread() thread finished')


    def handle_task(self, task):
        result = False
        try:
            self.handle_lock.acquire()
            result = task.handle()
        except Exception as e:
            print('Task was too much to handle')
        finally:
            self.handle_lock.release()
            return result
        
    def fast_click_thread(self):
        if not self.has_fast_target():
            print('WARN - ClickHandler.fast_click_thread() - No fast target. Skipping.')
            return
        print('INFO - ClickHandler.fast_click_thread() thread started')
        while self.running:
            self.handle_task(self.fast_target)
            if not self.running: break
        print('INFO - ClickHandler.fast_click_thread() thread finished')

    def change_if_higher_priority(self):
        pot = self.click_queue.change_if_higher_priority(self.next_target)
        if pot is not None:
            print(f'INFO - Changed target to {pot[1].targetid}')
            self.next_target = pot
            self.has_update = True

    def handle_one(self):
        try:
            print('INFO - ClickHandler.handle_one() thread started')
            self.handling_one = True
            self.next_target = self.get_from_queue()
            self.has_update = True

            if self.next_target is not None and self.next_target[1].triggered:
                print(f'INFO - Handle_one() - Got a target ID[{self.next_target[1].targetid}]')
                self.wait_additionnal_time()

                if self.next_target is not None:

                    if self.handle_task(self.next_target[1]):
                        self.last_click = self.next_target[1]
                    else:
                        print(f'ERROR - Handling target {self.next_target[1].targetid} failed')

                    # # self.wait(0.2)
                    # self.next_target[1].check_trigger()

                    self.next_target = None
                    self.has_update = True
                    self.handling_one = False

                self.click_queue.clean_queue()
        except Exception as e:
            print(f'ERROR - ClickHandler.handle_one() thread failed ({e})')
        finally:
            self.OneQueue.get()
            self.has_update = True
            self.handling_one = False
            print('INFO - ClickHandler.handle_one() thread finished')

    def run(self):
        print('INFO - ClickHandler.Run() thread started')
        self.additionnal_wait = 0

        self.allocate_single_fast_target()
        if self.has_fast_target():
            self.fast_thread = Thread(target=self.fast_click_thread, name='FastClick')
            self.fast_thread.start()

        if self.has_tracker_targets():
            #TODO Could be parameter on UI
            tracker_Interval = self.patience_level #self.patience_level/2
            self.trigger_thread = RepeatedTimer(tracker_Interval, self.update_thread, name='UpdateThread')
            if not self.trigger_thread.is_running:
                self.trigger_thread.start()

        if self.has_fast_target():
            self.fast_thread.join()
        elif self.has_tracker_targets():
            while self.running:
                time.sleep(1)

        if self.trigger_thread.is_running:
            print('INFO - ClickHandler.run() - Sending stop command to trigger thread')
            self.trigger_thread.stop()

        self.stop()
        self.next_target=None

        print('INFO - ClickHandler.Run() thread finished')