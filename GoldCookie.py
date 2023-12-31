import numpy as np
import re
import cv2
import time
import os
from PIL import Image
from pywinauto import mouse
from pywinauto.application import Application
from Target import GOLDENTARGET
import numpy as np 

from screenrecorder import ScreenRecorder

THRESHOLD_VALUE = 127  # Tweak as needed
# The reference image of the golden cookie
reference_path = os.path.join(os.path.dirname(__file__), 'reference.png')
# A file containing a screenshot with the golden cookie, for testing purposes
cheat_path = os.path.join(os.path.dirname(__file__), 'cheat.jpg')
# When true, will bypass the screenshot function and use the cheat image instead
TESTING = False
# When true, will automatically click the golden cookie when it appears
AUTOCLICK = False

def get_cookie_clicker_screenshot():
    if TESTING:
        img = Image.open(cheat_path).convert('L')
        img = np.array(img)
        ret, img = cv2.threshold(img, THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)
        return img

    try:
        title_pattern = re.compile(r"^.*cookies.*Cookie Clicker.*")
        app = Application().connect(title_re=title_pattern)
    except:
        print('ERROR - get_cookie_clicker_screenshot - Cookie clicker window not found')
        return None
    
    window = app.window(title_re=title_pattern)
    x, y, width, height = window.rectangle().left, window.rectangle(
    ).top, window.rectangle().width(), window.rectangle().height()
    # print("Window position is (", x, ",", y, ")")
    if x < 0:
        x = 0
    if y < 0:
        y = 0

    img = ScreenRecorder().get_screen(region=(x, y, x + width, y + height), caller='screenshot.get_cookie_clicker_screenshot()')
        
    
    img = np.dot(img[...,:3], [0.2989, 0.5870, 0.1140])

    ret, img = cv2.threshold(img, THRESHOLD_VALUE, 255, cv2.THRESH_BINARY)
    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype('uint8')

    return img

def prepare_reference_image(image_path):
    # Open the image and convert it to grayscale
    img = Image.open(image_path).convert('L')
    # Convert the image to a numpy array and apply thresholding
    img_array = np.array(img)
    img_array[img_array < THRESHOLD_VALUE] = 0
    img_array[img_array >= THRESHOLD_VALUE] = 255
    # Create an SIFT object
    sift = cv2.SIFT_create()
    # Detect keypoints and compute their descriptors
    keypoints, descriptors = sift.detectAndCompute(img_array, None)
    # Return the keypoints and descriptors
    return keypoints, descriptors, img_array

def find_golden_cookie(screenshot, kp_reference, des_reference, img_reference):
    sift = cv2.SIFT_create()
    # Finding keypoints and descriptor of the screenshot
    game_screenshot = screenshot
    kp_screenshot, des_screenshot = sift.detectAndCompute(
        game_screenshot, None)
    # create BFMatcher object
    bf = cv2.BFMatcher(cv2.NORM_L2)
    # Match descriptors.
    matches = bf.knnMatch(des_reference, des_screenshot, k=2)
    good_matches = []
    # Lowe's ratio test
    ratio = 0.6
    for match in matches:
        if len(match) == 2 and match[0].distance < match[1].distance * ratio:
            good_matches.append(match[0])
    img_matches = cv2.drawMatches(
        img_reference, kp_reference, screenshot, kp_screenshot, good_matches, None)
    # Obtain the coordinates of the best match
    if len(good_matches) > 0:
        x, y = kp_screenshot[good_matches[0].trainIdx].pt
        # print("Match found")
        return x, y
    else:
        # print("No match found")
        return -1, -1


def click_mouse(x, y):
    mouse.press(button='left', coords=(x, y))
    time.sleep(0.2)
    mouse.release(button='left', coords=(x, y))

def SEEK_GOLDEN_COOKIES():
        # current_x, current_y = win32api.GetCursorPos()

        # print("Mouse position is (", current_x, ",", current_y, ")")
        screenshot = get_cookie_clicker_screenshot()

        if screenshot is None:
            return None

        kp_reference, des_reference, img_reference = prepare_reference_image(
            reference_path)
        x, y = find_golden_cookie(screenshot, kp_reference,
                                des_reference, img_reference)
        if x >= 0 and y >= 0:
            x, y = int(x), int(y)
            # print("******** Cookie found at:", datetime.datetime.now(),
            #     "at (", int(x), ", ", int(y), ")")

            return GOLDENTARGET(x, y)
        else:
            return None

        
