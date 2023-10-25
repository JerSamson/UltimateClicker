# Ultimate Clicker

## Introduction

This repo contains a target-based auto clicker that can be adapted to multiple tasks

## Requirements

Still in development

## Usage

1. Make sure all the required modules are installed
2. Clone this repository to your local machine
3. Run the script `UI.py` 
4. In the tracker window, click Set Targets
    There, you can set different types of targets:
        "Same" : Will click on target when the area is the same as it was during acquisision
        "Diff" : Will click on target when the area is different as it was during acquisision
        "Change" : Will click on target when the area is different as it was during acquisision. A new reference will be fetched after each trigger
        "FastClick" : Will click at the specified rate specified in settings under "Target CPS" (Or will attempt to)

5. You can save and load you targets. Their click count and the total run time of your save file will be saved as well.
6. By selecting a target in the list, you will be able to see its reference image and you can toggle or delete it by right clicking.
7. Before clicking start, you can set the patience level (Slider above table)
    What patience is:
        When a target becomes triggered, it will add a stack of patience. Before clicking on the next target, the patience has to be depleated.
        The patience slider allows to set the time in seconds that each patience stack will take before depleating.

## Notes
Still under developpement.

## Licensing

This code is licensed under the [MIT License](LICENSE). Feel free to use, modify and distribute it as you like.