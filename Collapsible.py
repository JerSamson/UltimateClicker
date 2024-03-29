import PySimpleGUI as sg

SYMBOL_UP =    '▲'
SYMBOL_DOWN =  '▼'

def collapse(layout, key, start_collapsed=True):
    """
    Helper function that creates a Column that can be later made hidden, thus appearing "collapsed"
    :param layout: The layout for the section
    :param key: Key used to make this seciton visible / invisible
    :return: A pinned column that can be placed directly into your layout
    :rtype: sg.pin
    """
    return sg.pin(sg.Column(layout, key=key, visible=not start_collapsed))


class Collapsible:
    def __init__(self, title, layout, layout_key, event_key:str, start_collapsed=True) -> None:
        if not event_key.startswith('-COLLAPSE_'):
            raise Exception(f"Collabsible layout's event_key should start with '-COLLAPSE_'. (Got {event_key})")
        
        self.title = title
        self.layout_key = layout_key
        self.event_key = event_key
        self.collapsed = start_collapsed

        self.collapsible_section = [sg.Sizer(0,0), collapse(layout, layout_key, start_collapsed)]
        self.permanent_section = [sg.Sizer(0,0), sg.T(SYMBOL_UP, enable_events=True, k=event_key, visible=not start_collapsed), sg.T(title, enable_events=True, k=event_key+'Title', visible=not start_collapsed)]
