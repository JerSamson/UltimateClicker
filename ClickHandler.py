from Target import *
from queue import Queue, PriorityQueue
from threading import Lock, Thread
import time
from RepeatedTimer import RepeatedTimer
import ctypes

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
        self.click_queue = PriorityQueue()
        self.targets = []
        self.event_queue = []
        self.fast_target = None
        self.running = False
        self.has_update = False
        self.handle_lock = Lock()
        self.add_wait_lock = Lock()
        self.queue_lock = Lock()
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
 
    def empty_queue(self):
        while not self.click_queue.qsize() == 0:
            self.get_from_queue()

    def stop(self):
        self.running = False

        for tar in self.targets:
            tar.stop()
        self.empty_queue()
        
    def start(self):
        if self.running:
            return
        
        while self.main_thread is not None and self.main_thread.is_alive():
            time.sleep(1)
            # e = SelfDestructException
            # ctype_async_raise(self.main_thread.native_id, e)
            print('ClickerQueue Old thread still alive')

        
        self.running = True
        for tar in self.targets:
            tar.start()
        self.main_thread = Thread(target=self.run, name='ClickerQueueMain')
        self.main_thread.start()

    def add_target(self, tar):
        # if isinstance(tar, FastTarget):
        #     if self.fast_target is None:
        #         self.fast_target = tar
        #         self.has_update = True
        #     else:
        #         self.fast_target.enable = False
        #         self.fast_target = tar
        # raise Exception('Only one fast target allowed')
        
        tar.targetid = self.id_cnt
        self.id_cnt+=1
        self.targets.append(tar)
        self.has_update = True

    def is_in_queue(self, tar, own_lock = False):
        if own_lock:
             if not self.queue_lock.locked():
                 return
        else:
            self.queue_lock.acquire()
        try:
           res = tar in self.event_queue
        except:
            res = False
        finally:
            if not own_lock:
                self.queue_lock.release() 
        
        return res

    def add_to_queue(self, tar, own_lock = False):
        if own_lock:
             if not self.queue_lock.locked():
                 return
        else:
            self.queue_lock.acquire()
            # print(f'LOCK ACQUIRED (add_to_queue)')

        try:
            if tar in self.event_queue:
                print(f'Warning - Target already in queue ({tar.targetid})')
            else:
                self.click_queue.put(tar, block=True, timeout=1)
                self.event_queue.append(tar)
        except:
            pass
        finally:
            if not own_lock:
                self.queue_lock.release() 
                # print(f'LOCK RELEASED (add_to_queue)')

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

    def add_multiple_to_queue(self, targets, own_lock=False):
        if own_lock:
            #  if not self.queue_lock.locked():
            #      s(elf.queue_lock.acquire)
            pass
        else:
            self.queue_lock.acquire()
            # print(f'LOCK ACQUIRED (add_multiple_to_queue)')

        for tar in targets:
            self.add_to_queue(tar, True)
        if not own_lock:
            self.queue_lock.release() 
            # print(f'LOCK RELEASE (add_multiple_to_queue)')

    def get_from_queue(self, own_lock=False):
        if own_lock:
            #  if not self.queue_lock.locked():
            #      pass
            pass
        else:
            self.queue_lock.acquire()
            # print(f'LOCK ACQUIRED (get_from_queue)')
        try:
            tar = self.click_queue.get_nowait()
        except:
            tar = None
        finally:
            if tar is not None:
                self.event_queue.remove(tar)
        if not own_lock:
            self.queue_lock.release() 
            # print(f'LOCK RELEASE (get_from_queue)')

        return tar

    def clear_targets(self):
        self.stop()
        self.targets.clear()
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
                    break
                self.wait_prog = self.patience_level - i/self.patience_resolution
                self.has_update = True
                self.wait(1/self.patience_resolution)

            self.wait_prog = self.patience_level
            self.increment_patience(-1)
            self.has_update = True
            self.refresh_selection()
            add_wait = self.get_additionnal_wait()
            self.has_update = True

        self.waiting = False
        self.has_update = True
        print('Done waiting.')
        return True
    
    def update_thread(self):
        if self.running:
            try:
                self.queue_lock.acquire()
                if not self.running:
                    return
                for tar in self.targets:
                    if tar.enable and tar.check_trigger():
                        if  not self.is_in_queue((tar.priority, tar), True):
                            if self.next_target is None or tar is not self.next_target[1]:
                                self.increment_patience(1)
                                print(f'Added increment for target {tar.targetid}')
                                self.add_to_queue((tar.priority, tar), True)
                                self.has_update = True
                        else:
                            self.has_update = True
            except Exception as e:
                print(f'ERROR - ClickHandler - Update thread failed ({e})')
            finally:
                self.queue_lock.release()

    def refresh_queue_t(self):
        Thread(target=self.refresh_queue, name='refreshQueue').start()

    def refresh_queue(self):
        try:
            self.queue_lock.acquire()
            # print(f'LOCK ACQUIRED (refresh_queue)')
            temp = []
            while self.click_queue.qsize() > 0:
                task = self.get_from_queue(True)
                if task is not None:
                    if task[1].check_trigger():
                        temp.append(task)
            if not self.next_target in temp:
                self.next_target = None
                self.has_update = True
            self.add_multiple_to_queue(temp, own_lock=True)
            self.has_update = True
        except:
            pass
        finally:
            self.queue_lock.release()
            # print(f'LOCK RELEASED (refresh_queue)')

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
            return
        while self.running:
            self.handle_task(self.fast_target)
            if not self.running: break
        print('INFO - ClickHandler.fast_click_thread() thread finished')

    # def self_destruct(self):
    #     if not self.running and self.main_thread.is_alive():
    #         ctype_async_raise(self.main_thread.native_id, SelfDestructException)

    def refresh_selection(self):
        self.queue_lock.acquire()
        try:
            potential_target = self.get_from_queue(True)
            if potential_target is not None and potential_target[1].priority < self.next_target[1].priority:
                self.add_to_queue(self.next_target, True)
                self.next_target = potential_target
                self.has_update = True
            else:
                self.add_to_queue(potential_target, True)

        except Exception as e:
            print(f'ERROR - refresh_selection failed ({e})')
        finally:
            self.queue_lock.release()

    def run(self):
        try:
            self.additionnal_wait = 0
            self.allocate_single_fast_target()
            if self.has_fast_target():
                self.fast_thread = Thread(target=self.fast_click_thread, name='FastClick')
                self.fast_thread.start()

            #TODO Could be parameter on UI
            tracker_Interval = 1 #self.patience_level/2
            self.trigger_thread = RepeatedTimer(tracker_Interval, self.update_thread)

            if not self.trigger_thread.is_running:
                self.trigger_thread.start()

            while self.running:
                self.next_target = self.get_from_queue()
                self.has_update = True

                if self.next_target is not None and self.next_target[1].check_trigger():
                    self.wait_additionnal_time()

                    # # Change if better priority
                    # self.refresh_selection()

                    self.queue_lock.acquire()
                    if self.next_target is not None:

                        if self.handle_task(self.next_target[1]):
                            self.last_click = self.next_target[1]
                        else:
                            print(f'ERROR - Handling target {self.next_target[1].targetid} failed')

                        self.wait(0.2)
                        self.next_target[1].check_trigger()
                        self.next_target = None
                        self.queue_lock.release()
                        
                        self.refresh_queue_t()
                        self.has_update = True
                    else:
                        self.queue_lock.release()
                else:
                    self.wait(self.patience_level)
        except SelfDestructException:
            print('Self destructed')
            pass
        finally:
            self.stop()
            self.trigger_thread.stop()
            self.next_target=None
            # self.self_destruct_thread.stop()
            if self.has_fast_target():
                self.fast_thread.join(timeout=10)
            print('INFO - ClickHandler.Run() thread finished')