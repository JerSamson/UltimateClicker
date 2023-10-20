from queue import *

class UnitQueue(Queue):
    def __init__(self, maxsize: int = 1) -> None:
        super().__init__(maxsize)

    def has_one(self):
        return len(self.queue) == 1

    def tryPut(self, tar):
        try:
            self.put_nowait(tar)
            return True
        except:
            return False

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
        ''' Check in the queue for a higher priority target. 
        If one if found, the provided target is put back in the queue (If not None) and the higher priority target is poped from the front of the PriorityQueue
        Returns None if none is found
    '''
        with self.mutex:
            if len(self.queue) <= 0:
                return None
            
        potential_target = self.queue[0]
        if potential_target is not None and (tar is not None and potential_target[1].priority < tar[1].priority):
            if tar is not None:
                self.put_nowait(tar)
            return self.get_nowait()
        else:
            return None

    def empty_queue(self):
        with self.mutex:
            self.queue.clear()

    def clean_queue(self, set2=None):
        '''Removes targets that are either not triggered anymore or already handled

        If another queue is passed, it will update it at the same time.
    '''
        with self.mutex:
            for t in self.queue:
                if not t[1].check_trigger() or t[1].handled:
                    if set2 is not None and t[1] in set2:
                        idx = set2.index(t[1])
                        set2[idx] = t[1]
                        print(f'INFO - ClickerQueue.clean_queue() - Updated ID[{t[1].targetid}] from provided queue')

                    print(f'INFO - ClickerQueue.clean_queue() - Removed ID[{t[1].targetid}] from queue')
                    self.queue.remove(t)

            return set2
    
    def add_if_unique(self, tar):
            if not self.is_in_queue(tar):
                self.put_nowait(tar)
                print(f'INFO - ClickerQueue.add_if_unique() - Added ID[{tar[1].targetid}] to queue')
                return True
            print(f'WARN - ClickerQueue.add_if_unique() - ID[{tar[1].targetid}] was already in queue')
            return False

    def first_id(self):
        with self.mutex:
            try:
                return self.queue[0][1].targetid
            except:
                return None

    def is_empty(self):
        with self.mutex:
            return len(self.queue) == 0

    def is_in_queue(self, tar):
        with self.mutex:
            return tar in self.queue    