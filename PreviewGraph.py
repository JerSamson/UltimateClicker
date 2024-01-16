import PySimpleGUI as sg
from Target import *
from singleton import Singleton
from Settings import *
from logger import Logger
from screenrecorder import ScreenRecorder
from PIL import Image

class PreviewGraph(metaclass=Singleton):
    def __init__(self, key='-PREVIEW_GRAPH-') -> None:

        self.settings = Settings()
        self.logger = Logger()
        self.cam = ScreenRecorder()
        self.screenshot_filename = 'preview_screenshot.png'
        self.path = self.settings.userdata_dir + self.screenshot_filename
        self.targets = []

        self.canvas_size=(10,10)

        self.bottom_left    = (0, self.canvas_size[1])
        self.top_right      = (self.canvas_size[0], 0)

        self.screen = None

        self.graph = sg.Graph(canvas_size=self.canvas_size,
            graph_bottom_left=self.bottom_left,
            graph_top_right=self.top_right,
            enable_events=True,
            drag_submits=False, key=key,
            expand_x=True, expand_y=True,
            background_color='white',
            visible=True)
        
    def get_targets_bounding_box(self):
        if len(self.targets) <= 0:
            return
        
        x = [tar.x for tar in self.targets]
        y = [tar.y for tar in self.targets]
        target_zone = self.settings.get(TARGET_ZONE)

        min_x = min(x) - target_zone*4
        max_x = max(x) + target_zone*4
        min_y = min(y) - target_zone*4
        max_y = max(y) + target_zone*4

        region = (min_x, min_y, max_x, max_y)
        return region

    def update(self):
        if len(self.targets) <= 0:
            self.logger.info('PreviewGraph.update() - No targets')
            return
        
        region = self.get_targets_bounding_box()
        width = region[2] - region[0]
        height = region[3] - region[1]

        self.canvas_size = (width, height)
        self.bottom_left = (0, self.canvas_size[1])
        self.top_right   = (self.canvas_size[0], 0)

        self.screen = self.cam.get_screen(region=region ,caller="PreviewGraph")
        image = Image.fromarray(self.screen)
        
        image.save(self.path)

        self.logger.info(f'PreviewGraph.update() - Region: {region}')

    def draw(self):
        self.draw_image()
        self.draw_targets()

    def draw_image(self):
        self.graph.erase()
        if len(self.targets) <= 0:
            self.logger.info('PreviewGraph.draw_image() - No targets')
            self.graph.draw_text('No targets', text_location=sg.TEXT_LOCATION_CENTER, location=(50,50))
            return
        
        self.graph.draw_image(self.path, location=(self.bottom_left[0], self.top_right[1]))

    def draw_targets(self):
        region = self.get_targets_bounding_box()
        for tar in self.targets:
            x = tar.x - region[0]
            y = tar.y - region[1]
            self.logger.info(f'PreviewGraph.draw_targets() - drawing at [{x},{y}]')

            if isinstance(tar, TrackerTarget):
                self.graph.draw_circle((x,y), tar.zone_area, line_color='red', fill_color='white', line_width=3)
            elif isinstance(tar, FastTarget):
                self.graph.draw_line((x-10,y), (x+10,y), color='red', width=3)
                self.graph.draw_line((x,y-10), (x,y+10), color='red', width=3)
            
