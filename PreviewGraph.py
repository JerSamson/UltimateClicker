import PySimpleGUI as sg
import cv2
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
        self.selected_target = None

        self.hide_app = True
        self.whole_screen_preview = False
        self.fullscreen_ratio = 0.5
        self.default_canvas_size = (10,10)

        self.canvas_size=self.default_canvas_size
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

    def process_click(self, x, y):
        if self.selected_target is None:
            target = self.get_clicked_target(x,y)
            if target is not None:
                self.selected_target = target
                self.draw()
                self.logger.info(f'PreviewGraph.process_click() - Target[{self.selected_target.targetid}] selected')
            else:
                self.logger.info(f'PreviewGraph.process_click() - No target selected at ({x},{y})')
                return
        else:
            if self.whole_screen_preview:
                new_x = int(x/self.fullscreen_ratio)
                new_y = int(y/self.fullscreen_ratio)
            else:
                region = self.get_targets_bounding_box()    
                new_x = x + region[0]
                new_y = y + region[1]

            self.logger.info(f'PreviewGraph.process_click() - New position for target[{self.selected_target.targetid}] : ({new_x},{new_y}) was ({self.selected_target.x, self.selected_target.y})')
            self.selected_target.x = new_x
            self.selected_target.y = new_y

            if isinstance(self.selected_target, TrackerTarget):
                self.selected_target.bg_color_acquisition()

            self.selected_target = None
            self.draw()

    def hide_application(self, winpos, winsize):
        if not self.hide_app or winpos is None or winsize is None:
            return
        if self.whole_screen_preview:
            x = int(winpos[0]*self.fullscreen_ratio)
            y = int(winpos[1]*self.fullscreen_ratio)
            w = int(winsize[0]*self.fullscreen_ratio)
            h = int(winsize[1]*self.fullscreen_ratio)
        else:
            x = winpos[0]
            y = winpos[1]
            w = winsize[0]
            h = winsize[1]
        self.graph.draw_rectangle((x,y), (x+w, y+h), fill_color='black')

    def get_clicked_target(self, x, y):
        region = self.get_targets_bounding_box()
        target_zone = self.settings.get(TARGET_ZONE)
        for tar in self.targets:
            if self.whole_screen_preview:
                act_x = tar.x*self.fullscreen_ratio
                act_y = tar.y*self.fullscreen_ratio
            else:
                act_x = tar.x - region[0]
                act_y = tar.y - region[1]
            dx = abs(x - act_x)
            dy = abs(y - act_y)

            if dx < target_zone and dy < target_zone:
                return tar
        
        return None

    def update(self):
        if len(self.targets) <= 0:
            self.logger.info('PreviewGraph.update() - No targets')
            self.canvas_size=self.default_canvas_size
            self.bottom_left    = (0, self.canvas_size[1])
            self.top_right      = (self.canvas_size[0], 0)
            return
        
        if not self.whole_screen_preview:
            region = self.get_targets_bounding_box()
            width = region[2] - region[0]
            height = region[3] - region[1]
            self.screen = self.cam.get_screen(region=region, caller="PreviewGraph")
        else:
            self.screen = self.cam.get_screen(caller="PreviewGraph")
            width = self.screen.shape[1]
            height = self.screen.shape[0]
            
            self.screen = cv2.resize(self.screen, dsize=(int(width*self.fullscreen_ratio), int(height*self.fullscreen_ratio)), interpolation=cv2.INTER_AREA)

            width = self.screen.shape[0]
            height = self.screen.shape[1]

            region = (0, 0, width, height)

        self.canvas_size = (width, height)
        self.bottom_left = (0, self.canvas_size[1])
        self.top_right   = (self.canvas_size[0], 0)

        image = Image.fromarray(self.screen)
        
        image.save(self.path)

        self.logger.info(f'PreviewGraph.update() - Region: {region}')

    def draw(self, winpos=None, winsize=None):
        self.graph.erase()
        self.draw_image()
        self.hide_application(winpos, winsize)
        self.draw_targets()

    def draw_image(self):
        if len(self.targets) <= 0:
            self.logger.info('PreviewGraph.draw_image() - No targets')
            self.graph.draw_text('No targets', text_location=sg.TEXT_LOCATION_CENTER, location=(300,85), font=('Terminal', 20))
        else:
            self.graph.draw_image(self.path, location=(self.bottom_left[0], self.top_right[1]))

    def draw_targets(self):
        for tar in self.targets:

            if self.whole_screen_preview:
                x = int(tar.x*self.fullscreen_ratio)
                y = int(tar.y*self.fullscreen_ratio)
            else:
                region = self.get_targets_bounding_box()
                x = tar.x - region[0]
                y = tar.y - region[1]

            self.logger.info(f'PreviewGraph.draw_targets() - drawing at [{x},{y}]')


            color = 'red' if tar is not self.selected_target else 'blue'
            if isinstance(tar, TrackerTarget):
                self.graph.draw_circle((x,y), tar.zone_area, line_color=color, fill_color=color, line_width=3)
            elif isinstance(tar, FastTarget):
                self.graph.draw_line((x-10,y), (x+10,y), color=color, width=3)
                self.graph.draw_line((x,y-10), (x,y+10), color=color, width=3)
            
