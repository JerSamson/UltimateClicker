from Target import *
from threading import Lock, Thread
import time
from ClickQueue import *
from GoldCookie import SEEK_GOLDEN_COOKIES
from screenrecorder import ScreenRecorder
from Settings import *
from event_graph import EventGraph, EventEntry
from logger import Logger

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
        self.top_priority = 9999
        self.impatientThread = None
        self.last_golden_cookie_pos = None
        self.golden_clicked = 0
        self.settings = Settings()
        self.eventgraph = EventGraph()
        self.cam = ScreenRecorder()
        self.logger = Logger()

    def get_allowed_positions(self):
        #MaybeLock
        self.allowed_positions = [(tar.x, tar.y) for tar in self.targets]
        return self.allowed_positions

    def wait(self, delay):
        if delay <= 1:
            time.sleep(delay)
        else:
            for i in range(math.floor(delay)):
                for j in range(self.wait_resolution):
                    time.sleep(1/self.wait_resolution)
                    if not self.running:
                        self.logger.info('Aborted wait because ClickHandler is not running anymore')
                        return
            time.sleep(delay%1)

    def clear_patience(self):
        with self.add_wait_lock:
            self.additionnal_wait = 0

    def increment_patience(self, inc, tar=None):
        if self.patience_level <= 0:
            return
        
        self.add_wait_lock.acquire()
        try:
            if self.additionnal_wait + inc <= self.settings.get(MAX_PATIENCE_STACK) and self.additionnal_wait + inc >= 0:
                self.additionnal_wait += inc
                if tar is not None:
                    self.logger.info(f'INFO - Added increment for target {tar.targetid}')
                # print(f'Patience {("+" if inc >= 0 else "-")}{abs(inc)}\t({self.additionnal_wait})')
        except Exception as e:
            self.logger.error(f'Increment patience failed ({e})')
        finally:
            self.add_wait_lock.release()

    def get_additionnal_wait(self):
        self.add_wait_lock.acquire()
        w = self.additionnal_wait
        self.add_wait_lock.release()
        return w
    
    def has_fast_target(self):
        return self.fast_target is not None and self.fast_target.enabled
 
    def has_tracker_targets(self):
        if len(self.targets) <= 0:
            return False
        return len([t for t in self.targets if isinstance(t, TrackerTarget) and t.enabled]) > 0

    def stop(self):
        self.next_target=None
        self.running = False
        self.handling_one = False
        self.eventgraph.clear_entries()
        for tar in self.targets:
            tar.stop()
        self.click_queue.empty_queue()
        
    def start(self):
        if self.running:
            return
        
        while self.main_thread is not None and self.main_thread.is_alive():
            time.sleep(1)
            self.logger.warn('ClickerQueue Old thread still alive')
        
        self.running = True

        self.eventgraph.clear_entries()
        for tar in self.targets:
            tar.start()

        self.main_thread = Thread(target=self.run, name='ClickerQueueMain')
        self.main_thread.start()

    def add_target(self, tar):
        tar.targetid = self.id_cnt
        self.id_cnt+=1

        if(tar.priority > 0 and tar.priority < self.top_priority):
            self.top_priority = tar.priority

        self.targets.append(tar)
        self.has_update = True
        self.logger.info(f"ClickHandler.add_target - Target[{tar.targetid}] of type '{type(tar)}' added")

    def is_in_queue(self, tar):        
        return self.click_queue.is_in_queue(tar)

    def add_to_queue_if_new(self, tar):
        return self.click_queue.add_if_unique(tar)
       
    def get_fast_targets(self):
        return [tar for tar in self.targets if isinstance(tar, FastTarget) and tar.enabled]

    def allocate_single_fast_target(self):
        current = self.fast_target
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
                    potentials_targets[i].enabled = False

        if current is not self.fast_target:
            self.has_update = True

    def get_from_queue(self):
        return self.click_queue.get_if_any()

    def clear_targets(self):
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

    def clean_queue(self):
        self.click_queue.clean_queue()
        if self.click_queue.is_empty():
            self.clear_patience()

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
            self.clean_queue()
            self.change_if_higher_priority()
            if self.click_queue.is_empty():
                self.clear_patience()
            if self.click_queue.is_in_queue(self.next_target):
                self.next_target = None 

            if self.next_target is not None and self.next_target[1].priority == self.top_priority:
                # self.clear_patience()
                self.handle_task(self.next_target[1])
                self.increment_patience(-1)
                self.clean_queue()
                if self.click_queue.is_in_queue(self.next_target):
                    self.next_target = None 
                break

            add_wait = self.get_additionnal_wait()
            self.has_update = True

        self.waiting = False
        self.has_update = True
        self.logger.info('ClickHandler.wait_additionnal_time() - Done waiting.')
        return True
    
    def add_event_entry(self, name):
        ts = time.time()
        self.eventgraph.add_event_entry(EventEntry(ts, name))
        self.logger.debug(f'ClickHandler.Add_event_entry - Added {name} entry at timestamp {round(ts,2)}')
        # self.event_history.append((ts, name))

    def try_handle_one(self):
        if not self.click_queue.is_empty() and not self.OneQueue.has_one():
            if self.OneQueue.tryPut(self.next_target):
                self.logger.info(f'Starting handling thread (predicted ID: {self.click_queue.first_id()})')
                self.increment_patience(1)
                Thread(target=self.handle_one, name='HandleOne', daemon=True).start()

        self.clean_queue()
        if self.click_queue.is_in_queue(self.next_target):
            self.next_target = None 

    def update_thread(self, patient=True):
        self.logger.info('ClickHandler.update_thread() - Thread started')
        
        # target_max_x = max([(tar.x + tar.zone_area) for tar in self.targets if isinstance(tar, TrackerTarget)])
        # target_max_y = max([(tar.y + tar.zone_area) for tar in self.targets if isinstance(tar, TrackerTarget)])

        while self.running:
            start = time.time()
            try:
                self.add_event_entry('update_thread')
                self.logger.info('ClickHandler.update_thread() looped ========================')

                screenshot = self.cam.get_screen(caller='ClickHandler.UpdateThread()')
                screenshot_time = round(time.time()-start,2)
                self.logger.debug(f'ClickHandler.update_thread() - Getting screenshot took {screenshot_time}s =-=--=-=-=-=-=-=')

                checking_trig_start = time.time()
                for tar in self.targets:
                    if not isinstance(tar, FastTarget) and tar.enabled and tar.check_trigger(screenshot):
                        if self.next_target is None or tar is not self.next_target[1]:
                            if self.add_to_queue_if_new((tar.priority, tar)):
                                self.increment_patience(1, tar)
                                self.has_update = True

                check_triggers_time = round(time.time()-checking_trig_start,2)
                self.logger.debug(f'ClickHandler.update_thread() - checking triggers took {check_triggers_time}s =-=--=-=-=-=-=-=')

                if self.patience_level > 0:
                    Thread(target=self.try_handle_one, name='TryHandleOne', daemon=True).start()

            except Exception as e:
                self.logger.error(f'ClickHandler.update_thread() - thread failed ({e})')

            check_rate = self.settings.get(TRIGGER_CHECK_RATE)
            tracker_Interval = check_rate if check_rate > 0 else self.patience_level if self.patience_level > 0 else 1 #self.patience_level/2
            stop = time.time()

            execution_time = (stop - start)
            actual_wait_time = tracker_Interval - execution_time
            self.logger.debug(f'ClickHandler.update_thread() - Took {round(stop-start, 2)}s - Waiting time is {actual_wait_time}s =-=--=-=-=-=-=-=')

            if actual_wait_time > 0:
                self.wait(actual_wait_time)
            else:
                self.logger.warn(f'ClickHandler.update_thread() - Execution time was longer than Interval ({tracker_Interval} vs {execution_time})')
                self.logger.warn(f'\tGetting screenshot took {round(screenshot_time*1000, 2)}ms')
                self.logger.warn(f'\tChecking triggers took {round(check_triggers_time*1000, 2)}ms')

        self.logger.info('ClickHandler.update_thread() - thread finished')

    def impatient_thread(self):
        while self.running:
            tar = self.get_from_queue()
            if tar is not None:
                self.handle_task(tar[1])

    def handle_task(self, task):
        result = False
        try:
            self.handle_lock.acquire()
            if not isinstance(task, FastTarget):
                self.add_event_entry('HandleOne')
            result = task.handle()
        except Exception as e:
            self.logger.error(f'HandleTask[{task[1].targetid}] - Task was too much to handle ({e})')
        finally:
            self.handle_lock.release()
            return result
        
    def fast_click_thread(self):
        if not self.has_fast_target():
            self.logger.warn('ClickHandler.fast_click_thread() - No fast target. Skipping.')
            return
        
        self.logger.info('ClickHandler.fast_click_thread() thread started')
        while self.running:

            self.handle_task(self.fast_target)

            if not self.running: break
        self.logger.info('ClickHandler.fast_click_thread() thread finished')

    def change_if_higher_priority(self):
        pot = self.click_queue.change_if_higher_priority(self.next_target)
        if pot is not None:
            print(f'INFO - Changed target to {pot[1].targetid}')
            self.next_target = pot
            self.has_update = True

    def SeekAndClickGOOOOLD(self):
        self.logger.info('ClickHandler.SeekAndClickGOOOOLD() - GOLD DIGGER thread started')
        normal_wait = self.settings.get(GOLD_FREQ)
        streak_cnt = 0
        # TODO : Streak up to near 0 sec delay
        while self.running:
            try:
                start = time.time()
                self.add_event_entry('GoldenCookie')
                self.logger.info('ClickHandler.SeekAndClickGOOOOLD() - SEEKING')
                MaybeACookie = SEEK_GOLDEN_COOKIES()

                if MaybeACookie is not None and self.running:
                    if self.last_golden_cookie_pos is None or self.last_golden_cookie_pos != (MaybeACookie.x, MaybeACookie.y):
                        self.logger.info('ClickHandler.SeekAndClickGOOOOLD() - COOKIE FOUND')

                        self.last_golden_cookie_pos = (MaybeACookie.x, MaybeACookie.y)
                        self.add_target(MaybeACookie)
                        self.handle_task(MaybeACookie)
                        self.remove_target(MaybeACookie)
                        self.golden_clicked += 1
                        self.has_update = True

                        streak_cnt = normal_wait
                        self.logger.info(f'ClickHandler.SeekAndClickGOOOOLD() - STREAK - Updated delay between check to {normal_wait-streak_cnt}s')
                    else:
                        if streak_cnt >= 0.5:
                            streak_cnt -= 0.5
                            self.logger.info(f'ClickHandler.SeekAndClickGOOOOLD() - NON STREAK - Updated delay between check to {normal_wait-streak_cnt}s')

                        self.logger.info('Dismissing golden cookie because it seems to be the same as the last one detected')
                else:
                    if streak_cnt >= 0.5:
                        streak_cnt -= 0.5
                        self.logger.info(f'ClickHandler.SeekAndClickGOOOOLD() - NON STREAK - Updated delay between check to {normal_wait-streak_cnt}s')
                
                stop = time.time()
                actual_wait = (normal_wait-streak_cnt) - (start-stop)
                if actual_wait > 0:
                    self.wait(normal_wait-streak_cnt)
            except:
                pass

        self.logger.info('ClickHandler.SeekAndClickGOOOOLD() - GOLD DIGGER thread finished')
        

    def handle_one(self):
        try:
            self.logger.info('ClickHandler.handle_one() thread started')
            self.handling_one = True
            self.next_target = self.get_from_queue()
            self.has_update = True

            if self.next_target is not None and self.next_target[1].triggered:
                self.logger.info(f'Handle_one() - Got a target ID[{self.next_target[1].targetid}]')

                if self.next_target is not None and not self.next_target[1].priority == self.top_priority:
                    self.wait_additionnal_time()

                if self.next_target is not None:
                    if self.handle_task(self.next_target[1]):
                        self.last_click = self.next_target[1]
                    else:
                        self.logger.error(f'Handling target {self.next_target[1].targetid} failed')

                    self.next_target = None
                    self.has_update = True
                    self.handling_one = False

                self.clean_queue()
                if self.click_queue.is_in_queue(self.next_target):
                    self.next_target = None

        except Exception as e:
            self.logger.error(f'ClickHandler.handle_one() thread failed ({e})')
            raise e
        finally:
            self.OneQueue.get()
            self.has_update = True
            self.handling_one = False
            self.logger.info('ClickHandler.handle_one() thread finished')

    def run(self):
        print('INFO - ClickHandler.Run() thread started')
        self.additionnal_wait = 0
        self.impatientThread = None

        if self.settings.check_for_gold_cookie:
            gold_digger = Thread(target=self.SeekAndClickGOOOOLD, name='GOLD_DIGGER', daemon=True)
            gold_digger.start()

        self.allocate_single_fast_target()
        if self.has_fast_target():
            self.fast_thread = Thread(target=self.fast_click_thread, name='FastClick')
            self.fast_thread.start()

        if self.has_tracker_targets():
            self.trigger_thread = Thread(target=self.update_thread, name='TriggerThread', daemon=True)
            self.trigger_thread.start()

            if self.patience_level <= 0:
                self.impatientThread = Thread(target=self.impatient_thread, daemon=True)
                self.impatientThread.start()

        # RUNNING

        if self.has_fast_target():
            self.fast_thread.join()
        elif self.has_tracker_targets():
            while self.running:
                time.sleep(1)

        if self.settings.check_for_gold_cookie:
            gold_digger.join()

        if self.trigger_thread is not None:
                self.logger.info('ClickHandler.run() - Sending stop command to trigger thread')
                self.trigger_thread.join()

        if self.impatientThread is not None:
            self.logger.info('ClickHandler.run() - Waiting for impatient thread to finish')
            self.impatientThread.join()
            self.logger.info('ClickHandler.run() - Impatient thread finished')

        if self.running:
            self.stop()

        self.logger.info('ClickHandler.Run() thread finished')