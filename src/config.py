#!/usr/bin/env python3

import os
import argparse
from collections import defaultdict

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME
# curl "https://canvas.umd.umich.edu/api/v1/courses?per_page=60&enrollment_type=student&include[]=syllabus_body&include[]=total_scores&include[]=public_description&include[]=course_progress&include[]=sections&include[]=teachers&include[]=term&include[]=favorites" -H 'Authorization: Bearer 1058~9gDGGWUjqY4zlMilrAa0sWRA2h5ZFJ7NSXURcPvVAbWn5HiCEq4mFBTizU3FVRlM' | jq > a.json


class Config:
    """Read and manage Canvas Token configurations"""

    def __init__(self):
        self.map = defaultdict(str)

    def get_token(self) -> str:
        if self.map["TOKEN"] == "":
            print("API Token not found")
            exit()
        return self.map["TOKEN"]

    def get_domain(self) -> str:
        if self.map["domain"] == "":
            print("Domain not found")
            exit()
        if self.map["domain"][-1] != "/":
            self.map["domain"].append("/")
        return self.map["domain"]

    def get_current_term(self) -> str:
        return self.map["term"] if self.map["term"] != "" else ""

    def read_config(self, file) -> None:
        for line in file:
            if "=" in line:
                key, value = line.strip().split("=")
                self.map[key] = value
