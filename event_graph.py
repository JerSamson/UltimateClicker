from enum import IntEnum
import math
import statistics
import time
import PySimpleGUI as sg
from singleton import Singleton
from Settings import *
from numba import jit
from logger import Logger

event_colors = {
    'cps'           :   'red',
    'update_thread' :   'blue',
    'GoldenCookie'  :   'gold',
    'HandleOne'     :   'green',
    'SecondMarker'  :   'gray90',
    'autosave'      :   'SkyBlue1',
    '5SecondMarker' :   'black'
}

class EntryType(IntEnum):
    cps       = 1
    event     = 2


class GraphEntry:
    def __init__(self, _type, timestamp, name) -> None:
        self.type = _type
        self.timestamp = timestamp
        self.normalized_timestamp = 0
        self.name = name

class CpsEntry(GraphEntry):
    def __init__(self, timestamp, cps) -> None:
        self.cps = cps
        super().__init__(EntryType.cps, timestamp, 'cps')

class EventEntry(GraphEntry):
    def __init__(self, timestamp, name) -> None:
        super().__init__(EntryType.event, timestamp, name)

class EventGraph(metaclass=Singleton):
    def __init__(self, key='-EVENTGRAPH-') -> None:

        self.settings = Settings()
        self.logger = Logger()

        self.canvas_size=(500,100)

        self.bottom_left    = (0,0)
        self.top_right      = (100, 1000)

        self.max_entry_display = 100

        self.event_entries = []
        self.cps_entries = []
        # self.n_sec_entry = 0

        self.graph = sg.Graph(canvas_size=self.canvas_size,
            graph_bottom_left=self.bottom_left,
            graph_top_right=self.top_right,
            enable_events=True,
            drag_submits=False, key=key,
            expand_x=False, expand_y=True,
            background_color='white',
            visible=False)

        self.new_entries = False

    def has_new_entries(self):
           res = self.new_entries
           self.new_entries = False
           return res
    
    def erase(self):
        self.graph.erase()

    def clear_entries(self):
        self.cps_entries.clear()
        self.event_entries.clear()

    def is_cps_entry(self, entry):
        return isinstance(entry, CpsEntry)

    def is_event_entry(self, entry):
        return isinstance(entry, EventEntry)
    
    def has_cps_entries(self):
        return len(self.cps_entries) > 0

    def has_event_entries(self):
        return len(self.event_entries) > 0
    
    def min_cps_entry_timestamp(self):
        if len(self.cps_entries) > 0:
            return min([entry.timestamp for entry in self.cps_entries])
        else:
            return 0
        
    def max_cps_entry(self):
        if len(self.cps_entries) > 0:
            return max([entry.cps for entry in self.cps_entries])
        else:
            return 0
        
    def min_cps_entry(self):
        if len(self.cps_entries) > 0:
            return min([entry.cps for entry in self.cps_entries])
        else:
            return 0
        
    def max_cps_entry_timestamp(self):
        if len(self.cps_entries) > 0:
            return max([entry.timestamp for entry in self.cps_entries])
        else:
            return 0
        
    def add_cps_entry(self, entry):
        if len(self.cps_entries) >= self.max_entry_display:
            self.cps_entries.pop(0)

        self.cps_entries.append(entry)
        self.new_entries = True

    def add_event_entry(self, entry):
        self.event_entries.append(entry)
        self.new_entries = True

    def normalize_timestamp(self, entry):
        if self.has_cps_entries():

            if len(self.cps_entries) > 0:
                min_cps_timestamp = min([_entry.timestamp for _entry in self.cps_entries])
            else:
                min_cps_timestamp = time.time()

            entry.normalized_timestamp = int(round((entry.timestamp - min_cps_timestamp), 3)*1000)

        elif self.has_event_entries():
            if len(self.event_entries) > 0:
                min_event_timestamp = min([_entry.timestamp for _entry in self.event_entries])
            else:
                min_event_timestamp = time.time()

            entry.normalized_timestamp = int(round((entry.timestamp - min_event_timestamp), 3)*1000)

            self.logger.debug(f'event_graph.normalize_timestamp - EventEntry [{entry.name}] normalized to {entry.normalized_timestamp}')            
    

    def adapt_graph_size(self):
        if self.has_cps_entries():
            target_cps = self.settings.get(TARGET_CPS)
            max_cps_entry = max([entry.cps for entry in self.cps_entries])
            max_cps_entry = max([max_cps_entry, target_cps])

            max_cps_timestamp = max([entry.normalized_timestamp for entry in self.cps_entries])
            min_cps_timestamp = min([entry.normalized_timestamp for entry in self.cps_entries])

            bottom_left_x = min_cps_timestamp
            bottom_left_y = 0
            self.bottom_left = (bottom_left_x, bottom_left_y)

            top_right_x = max_cps_timestamp

            if target_cps > 0 and max_cps_entry < max_cps_entry + target_cps:
                top_right_y = max_cps_entry + target_cps
            else:
                top_right_y = max_cps_entry + 50
            self.top_right = (top_right_x, top_right_y)

            self.graph.BottomLeft = self.bottom_left
            self.graph.TopRight = self.top_right

        elif self.has_event_entries():
            max_timestamp = max([entry.normalized_timestamp for entry in self.event_entries])
            min_timestamp = min([entry.normalized_timestamp for entry in self.event_entries])

            bottom_left_x = min_timestamp if min_timestamp > 0 else -1
            bottom_left_y = self.bottom_left[1]
            self.bottom_left = (bottom_left_x, bottom_left_y)

            top_right_x = int(max_timestamp*1.3)
            top_right_y = self.top_right[1]
            self.top_right = (top_right_x, top_right_y)
            
            self.graph.BottomLeft = self.bottom_left
            self.graph.TopRight = self.top_right

        self.logger.debug(f'event_graph.adapt_graph_size() - Graph size: x:[{self.graph.BottomLeft[0]}, {self.graph.TopRight[0]}] y:[{self.graph.BottomLeft[1]}, {self.graph.TopRight[1]}]')            


    def draw_cps(self):
        target_cps = self.settings.get(TARGET_CPS)
        if target_cps > 0: # Draw target line
            self.graph.draw_line((self.graph.BottomLeft[0], target_cps), (self.top_right[0], target_cps), width=1)

        if len(self.cps_entries) > 0:
            points = []
            for entry in self.cps_entries:
                self.normalize_timestamp(entry)
                points.append((entry.normalized_timestamp, entry.cps))
            self.graph.draw_lines(points=points, color=event_colors['cps'], width=2)

    def draw_event(self):
        for entry in self.event_entries:
            self.normalize_timestamp(entry)
            color = event_colors[entry.name]
    
            # if entry.normalized_timestamp < self.bottom_left[0]:
            #     self.entries.remove(entry)

            # self.graph.draw_lines([(entry.normalized_timestamp, self.graph.BottomLeft[1])])

            if entry.normalized_timestamp > self.bottom_left[0] and entry.normalized_timestamp < self.top_right[0]:
                self.logger.debug(f'event_graph.draw_event() - Drawing {entry.name} event at normalized ts {entry.normalized_timestamp}')
                if entry.name == '5SecondMarker':
                    ratio = 0.1
                    self.graph.draw_line((entry.normalized_timestamp, self.graph.BottomLeft[1]), (entry.normalized_timestamp, (self.graph.TopRight[1]-self.graph.BottomLeft[1])*ratio), color=color, width=4)
                    self.graph.draw_line((entry.normalized_timestamp, self.graph.TopRight[1]), (entry.normalized_timestamp, self.graph.TopRight[1]*(1-ratio)), color=color, width=4)
                    # self.event_entries.remove(entry)
                else:
                    self.graph.draw_line((entry.normalized_timestamp, self.graph.BottomLeft[1]), (entry.normalized_timestamp, self.graph.TopRight[1]), color=color, width=2)

            elif entry.normalized_timestamp < self.bottom_left[0] or entry.name == 'SecondMarker':
                self.event_entries.remove(entry)

    def draw_seconds(self):
        # TODO: Optimize that
        min = int(math.floor(self.min_cps_entry_timestamp()))
        max = int(math.ceil(self.max_cps_entry_timestamp()))
        ts_range = max - min 

        self.logger.debug(f'event_graph.draw_seconds() - range={ts_range}')

        for i in range(ts_range):
            sec_entry = EventEntry(min+i, 'SecondMarker')
            # if sec_entry not in self.event_entries:
            #     if self.n_sec_entry / 5 == 1:
            #         self.add_event_entry(EventEntry(min+i, '5SecondMarker'))
            self.add_event_entry(sec_entry)

    def seconds_to_days_etc(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        return f'{int(days)}d{int(hours)}h{int(minutes)}m{int(seconds)}s'

    def draw_runtime(self):
        text = self.seconds_to_days_etc(self.settings.run_time)
        self.graph.DrawText(text, location=(0,0), text_location=sg.TEXT_LOCATION_BOTTOM_LEFT, font=('Terminal'))

    def draw_stats(self):
        cps_vals = [val.cps for val in self.cps_entries]
        text = f'[{self.min_cps_entry()}, {self.max_cps_entry()}] pstdev:{round(statistics.pstdev(cps_vals, self.settings.get(TARGET_CPS)), 2)}'
        self.graph.DrawText(text, location=(0,self.top_right[1]-5), text_location=sg.TEXT_LOCATION_TOP_LEFT, font=('Terminal'), color='gray')

    @jit(target_backend='cuda', forceobj=True)
    def update(self):
        if self.has_new_entries():
            self.graph.erase()
            self.adapt_graph_size()

            self.draw_seconds()

            if self.has_event_entries():
                self.draw_event()

            if self.has_cps_entries():
                self.draw_cps()
                if self.settings.get(ADVANCED_GRAPH_INFO):
                    self.draw_stats()

            self.draw_runtime()