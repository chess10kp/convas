
#!/usr/bin/env python3

import curses
import json
import os
import re
import subprocess
import time
from collections import namedtuple
from curses import panel, wrapper
from json import loads
from typing import Dict, Generator, Tuple
from enum import Enum
from urllib import error, request

# while keydown != ord('q'):
# stdscr.clear()
# height,width = stdscr.getmaxyx()
#
# if keydown == curses.KEY_DOWN :
# stdscr.addstr(keydown)
#
#
# title = "'%s"[:width-1] % height
# title_x_pos = int((width // 2) - (len(title) // 2) )
# stdscr.addstr(height//2, width//2, str(keydown))


HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME


class Config:
    """Read and manage Canvas Token configurations"""

    def __init__(self, token):
        self.token = token

    def get_token(self) -> str:
        return self.token
