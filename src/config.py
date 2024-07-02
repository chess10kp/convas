
#!/usr/bin/env python3

import os
import argparse

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME


class Config:
    """Read and manage Canvas Token configurations"""

    def __init__(self, token):
        self.token = token

    def get_token(self) -> str:
        return self.token

    def read_config(): 
        pass
