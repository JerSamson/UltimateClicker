from ctypes import Array
from enum import IntEnum
import time
import PySimpleGUI as sg
from singleton import Singleton
from Settings import Settings

event_colors = {
    'cps'           :   'red',
    'update_thread' :   'blue',
    'GoldenCookie'  :   'gold',
    'HandleOne'     :   'green'
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

        self.canvas_size=(500,100)

        self.bottom_left    = (0,0)
        self.top_right      = (60, 1000)

        self.max_entry_display = 60

        self.entries = []

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
        self.entries.clear()

    def is_cps_entry(self, entry):
        return isinstance(entry, CpsEntry)

    def is_event_entry(self, entry):
        return isinstance(entry, EventEntry)
    
    def has_cps_entries(self):
        return len(self.cps_entries()) > 0

    def has_event_entries(self):
        return len(self.event_entries()) > 0
    
    def cps_entries(self):
        return [entries for entries in self.entries if self.is_cps_entry(entries)]

    def event_entries(self):
        return [entries for entries in self.entries if self.is_event_entry(entries)]

    def add_entry(self, entry):
        if len(self.entries) >= self.max_entry_display:
            self.entries.pop(0)

        self.entries.append(entry)
        self.new_entries = True

    def normalize_timestamp(self, entry):
        if self.has_cps_entries():
            cps_entries = self.cps_entries()

            if len(cps_entries) > 0:
                min_cps_timestamp = min([_entry.timestamp for _entry in cps_entries])
            else:
                min_cps_timestamp = time.time()

            entry.normalized_timestamp = int(round((entry.timestamp - min_cps_timestamp), 3)*1000)

        elif self.has_event_entries():
            event_entries = self.event_entries()

            if len(event_entries) > 0:
                min_event_timestamp = min([_entry.timestamp for _entry in event_entries])
            else:
                min_event_timestamp = time.time()

            entry.normalized_timestamp = int(round((entry.timestamp - min_event_timestamp), 3)*1000)
            print(f'INFO - event_graph.normalize_timestamp - EventEntry normalized to {entry.normalized_timestamp}')
    

    def adapt_graph_size(self):
        if self.has_cps_entries():
            cps_entries = self.cps_entries()

            max_cps_entry = max([entry.cps for entry in cps_entries])
            max_cps_entry = max([max_cps_entry, self.settings.target_cps])

            max_cps_timestamp = max([entry.normalized_timestamp for entry in cps_entries])
            min_cps_timestamp = min([entry.normalized_timestamp for entry in cps_entries])

            bottom_left_x = min_cps_timestamp
            bottom_left_y = 0
            self.bottom_left = (bottom_left_x, bottom_left_y)

            top_right_x = max_cps_timestamp
            top_right_y = max_cps_entry + 50

            self.top_right = (top_right_x, top_right_y)

            self.graph.BottomLeft = self.bottom_left
            self.graph.TopRight = self.top_right

        elif self.has_event_entries():
            event_entries = self.event_entries()
            max_timestamp = max([entry.normalized_timestamp for entry in event_entries])
            min_timestamp = min([entry.normalized_timestamp for entry in event_entries])

            bottom_left_x = min_timestamp if min_timestamp > 0 else -1
            bottom_left_y = self.bottom_left[1]
            self.bottom_left = (bottom_left_x, bottom_left_y)

            top_right_x = int(max_timestamp*1.3)
            top_right_y = self.top_right[1]
            self.top_right = (top_right_x, top_right_y)
            
            self.graph.BottomLeft = self.bottom_left
            self.graph.TopRight = self.top_right

        print(f'INFO - event_graph.adapt_graph_size() - Graph size: x:[{self.graph.BottomLeft[0]}, {self.graph.TopRight[0]}] y:[{self.graph.BottomLeft[1]}, {self.graph.TopRight[1]}]')


    def draw_cps(self):
        last_x = 0
        last_y = 0

        cps_entries = self.cps_entries()

        if self.settings.target_cps > 0: # Draw target line
            self.graph.draw_line((self.graph.BottomLeft[0], self.settings.target_cps), (self.top_right[0], self.settings.target_cps))

        if len(cps_entries) > 1:
            last_y = cps_entries[0].cps

        for entry in cps_entries:
            self.normalize_timestamp(entry)
            self.graph.draw_line((last_x, last_y), (entry.normalized_timestamp, entry.cps), color=event_colors['cps'], width=2)
            last_x = entry.normalized_timestamp
            last_y = entry.cps
            # print(f'INFO - CPSGRAPH - New line from ({last_x},{last_y}) to {entry}')

    def draw_event(self):
        for entry in self.event_entries():
            self.normalize_timestamp(entry)
            color = event_colors[entry.name]

            if entry.normalized_timestamp > self.bottom_left[0]:
                print(f'INFO - event_graph.draw_event() - Drawing {entry.name} event at normalized ts {entry.normalized_timestamp}')
                self.graph.draw_line((entry.normalized_timestamp, self.graph.BottomLeft[1]), (entry.normalized_timestamp, self.graph.TopRight[1]), color=color, width=2)
            else:
                self.entries.remove(entry)

    def update(self):
        if self.has_new_entries():
            self.graph.erase()
            self.adapt_graph_size()

            if self.has_cps_entries():
                self.draw_cps()

            if self.has_event_entries():
                self.draw_event()