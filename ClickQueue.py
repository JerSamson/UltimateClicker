from queue import PriorityQueue


class ClickQueue(PriorityQueue):
    def get_current_queue(self):
        with self.mutex:
            return self.queue
        
    def get_if_any(self):
        try:
            return self.get_nowait()
        except:
            return None

    def change_if_higher_priority(self, tar):
            with self.mutex:
                if len(self.queue) <= 0:
                    return None
                
            potential_target = self.queue[0]
            if potential_target is not None and potential_target[1].priority < tar[1].priority:
                self.put_nowait(tar)
                return self.get_nowait()
            else:
                return None

    def empty_queue(self):
        with self.mutex:
            self.queue.clear()

    def refresh_queue(self):
        changed = False
        with self.mutex:
            for t in self.queue:
                if not t[1].check_trigger():
                    self.queue.remove(t)
                    changed = True
            return changed
    
    def add_if_unique(self, tar):
            if not self.is_in_queue(tar):
                self.put_nowait(tar)
                print(f'INFO - ClickerQueue Added ID[{tar[1].targetid}] to queue')
                return True
            return False

    def is_empty(self):
        with self.mutex:
            return len(self.queue) == 0

    def is_in_queue(self, tar):
        with self.mutex:
            return tar in self.queue    