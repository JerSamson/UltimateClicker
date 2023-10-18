import ctypes
import winreg
import time

import win32com

# Define the path to the cursor file (CURSOR_FILE_PATH should be the path to your .cur or .ani cursor file)
CIRCLE_CURSOR_FILE = 'red_circle2.cur'
CURSOR_FILE = 'aero_arrow.cur'

BASE_PATH = 'C:\\Windows\\Cursors\\'

defaults = {
    32512: 'aero_arrow.cur',
    32513: 'beam_r.cur',
    32514: 'wait_r.cur',
    32515: 'cross_r.cur',#
    32516: 'up_r.cur',#
    32642: 'size1_r.cur',# or size_nw_se.cur
    32643: 'size2_r.cur',# or size_ne_sw.cur
    32644: 'size3_r.cur',# or size_we.cur
    32645: 'size4_r.cur',# or size_ns.cur
    32646: 'move_r.cur',#
    32648: 'no_r.cur',#
    32649: 'person_r.cur',#
    32650: 'help_r.cur',#
}


def set_cursor_circle():
    for cur in defaults.keys():
        set_global_cursor(cur, CIRCLE_CURSOR_FILE)

def set_cursor_default():
        for cur, file in defaults.items():
            set_global_cursor(cur, file)

# Set the new cursor
def set_global_cursor(cursor, cursor_file):
    file = BASE_PATH + cursor_file
    try:
        # Load the cursor file
        h_cursor = ctypes.windll.user32.LoadImageW(0, file, ctypes.c_uint(2), 32, 32, ctypes.c_uint(0x00000010))

        # Set the new cursor
        ctypes.windll.user32.SetSystemCursor(h_cursor, cursor)  # 32512 is the OCR_NORMAL constant
    except Exception as e:
        print(e)

# set_cursor_circle()
# time.sleep(5)
set_cursor_default()