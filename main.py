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
    """Read and manage Canvas LMS configurations"""

    def __init__(self, token):
        self.token = token

    def get_token(self) -> str:
        return self.token


with open(CONFIG_FILE) as file:
    for line in file:
        if "=" in line:
            key, value = line.strip().split("=")
            config = Config(value)

if "config" not in globals():
    raise Exception("Unable to read config file")

url = "https://canvas.umd.umich.edu/api/v1/courses"

headers = {"Authorization": f"Bearer {config.get_token()}"}


def get_paginated_responses(url, headers) -> list[str] | None:
    next_page = url
    data = []
    while next_page:
        response = request.urlopen(next_page, headers=headers)
        if response.status_code == 404:
            return None
        elif response.status_code != 200:
            print(f"Error: {response.status_code}")
            return None
        response_data = response.read().decode("utf-8")
        response.close()
        data.extend(response_data)
        next_page = response.links.get("next", {}).get("url")

    return data


def get_course_names(json_obj) -> list[str]:
    return [course["name"] for course in json_obj]


def get_current_courses(json_obj) -> list[Dict[str, str]]:
    return [
        course
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_current_course_names(json_obj) -> list[str]:
    return [
        course["course_code"]
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_current_course_name_id_map(json_obj) -> dict[str, str]:
    return {
        course["name"]: course["id"]
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    }


def get_current_course_id(json_obj) -> list[str]:
    return [
        course["id"]
        for course in json_obj
        if course["created_at"][:10] == json_obj[-1]["created_at"][:10]
    ]


def get_request(url, headers):
    return request.urlopen(url, headers=headers)


def get_todo_items(url, headers, course_id: int):
    return request.urlopen(f"{url}/{course_id}/todo", headers=headers)


def get_quizzes(url: str, headers, course_id: int):
    quizzes = get_paginated_responses(f"{url}/{course_id}/quizzes", headers=headers)
    return quizzes


def get_files(url: str, headers, course_id: int):
    files = get_paginated_responses(f"{url}/{course_id}/files", headers)
    return files


def get_file_names(file_obj) -> list[str]:
    return [file["display_name"] for file in file_obj]


def get_file_download(file_obj) -> list[str]:
    return [file["url"] for file in file_obj]


def get_file_names_download(file_obj):
    return {file["display_name"]: file["url"] for file in file_obj}


def get_assignments_request(url, headers, course_id: int):
    print("Getting assignments for %s" % course_id, end="\n")
    assignments = get_paginated_responses(f"{url}/{course_id}/assignments", headers)
    with open(f"assignments{course_id}.json", "w") as file:
        json.dump(assignments, file)
    return assignments


with open("data.json") as file:
    data = file.read()
    all_courses = json.loads(data)


class Menu(object):
    def __init__(self, items, stdscreen):
        self.window = stdscreen.subwin(0, 0)
        # self.window.keypad(1)
        self.panel = panel.new_panel(self.window)
        self.panel.hide()
        panel.update_panels()
        self.position = 0
        self.items = items
        self.items.append(("exit", "exit"))

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.items):
            self.position = len(self.items) - 1

    def display(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()
        curses.doupdate()
        for index, item in enumerate(self.items):
            msg = "%d. %s" % (index, item[0])
            self.window.addstr(1 + index, 1, msg, curses.A_NORMAL)
        self.window.refresh()
        panel.update_panels()
        curses.doupdate()

    def run(self):
        self.panel.top()
        self.panel.show()
        self.window.clear()
        while True:
            self.window.refresh()
            curses.doupdate()
            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL
                msg = "%d. %s" % (index, item[0])
                self.window.addstr(1 + index, 1, msg, mode)
            key = self.window.getch()
            if key in [curses.KEY_ENTER, ord("\n")]:
                if self.position == len(self.items) - 1:
                    break
                else:
                    self.items[self.position][1]()
            elif key == curses.KEY_UP or key == ord("k"):
                self.navigate(-1)
            elif key == curses.KEY_DOWN or key == ord("j"):
                self.navigate(1)
        curses.doupdate()
        for index, item in enumerate(self.items):
            if index == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL

            msg = "%d. %s" % (index, item[0])
            self.window.addstr(1 + index, 1, msg, mode)
        self.window.refresh()
        panel.update_panels()
        curses.doupdate()


class CourseSubMenu(Menu):
    """Submenu for Course details"""
    def __init__(self, stdscreen, course_id):
        self.window = stdscreen.subwin(0, 0)
        self.window.keypad(1)
        course_assignment_dates = namedtuple(
            "course_assignment_dates", ["created_at", "due_at"]
        )
        self.course_id = course_id
        self.assignment_info = loads(
            (open(f"./assignments{course_id}.json").read())
        )  # get_assignments_request(url, headers, self.course_id)
        self.assignments = [assignment["name"] for assignment in self.assignment_info]
        self.assignment_dates = {
            assignment["name"]: course_assignment_dates(
                created_at=assignment["created_at"], due_at=assignment["due_at"]
            )
            for assignment in self.assignment_info
        }
        self.assignment_descriptions = {
            assignment["name"]: [
                assignment["description"],
                assignment["points_possible"],
            ]
            for assignment in self.assignment_info
        }
        super().__init__(
            [
                [assignment, lambda: self.print_assignment_info(self.course_id)]
                for assignment in self.assignments
            ],
            stdscreen,
        )

    def display(self):
        self.window.clear()
        curses.doupdate()
        for index, item in enumerate(self.items):
            msg = "%d. %s" % (index, item[0])
            self.window.addstr(1 + index, 1, msg, curses.A_NORMAL)
        self.window.refresh()
        curses.doupdate()

    def run(self):
        self.window.clear
        self.window.refresh()
        for index, item in enumerate(self.items):
            if index == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL
            msg = "%d. %s" % (index, item[0])
            self.window.addstr(1 + index, 1, msg, mode)
        self.window.refresh()
        curses.doupdate()
        while True:
            self.window.refresh()
            for index, item in enumerate(self.items):
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL
                msg = "%d. %s" % (index, item[0])
                self.window.addstr(1 + index, 1, msg, mode)
            self.window.refresh()
            curses.doupdate()
            key = self.window.getch()
            if key in [curses.KEY_ENTER, ord("\n")]:
                if self.position == len(self.items) - 1:
                    break
                else:
                    self.items[self.position][1]()
            elif key == curses.KEY_UP or key == ord("k"):
                self.navigate(-1)
            elif key == curses.KEY_DOWN or key == ord("j"):
                self.navigate(1)
        self.window.refresh()
        curses.doupdate()

    def print_assignment_info(self, assignment: int):
        # [ ] TODO: get the information about the assignment
        # [ ] this would date it is posted, due date, and points
        # [ ] print out the assignment
        # [ ] send the information back to the main window and let it display the informtion
        self.screen.refresh()


class StatusBar(Menu):
    """Statusbar Class using newwin"""

    def __init__(
        self, courses, height, width, course_ids, update_callback, 
        change_win_callback
    ):
        self.window = curses.newwin(3, width, height - 3, 0)
        self.position = 0
        self.course_ids = course_ids
        self.courses = [
            (course[: course.find("(")], course) if (course.find("(") != -1) else course
            for course in courses
        ]
        self.update_callback = update_callback

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.courses):
            self.position = len(self.courses) - 1

    def display(self):
        self.window.clear()
        curses.doupdate()
        status_offset = 2
        for index, course in enumerate(self.courses):
            msg = "%d. %s" % (index, course[0])
            self.window.addstr(1, status_offset + index, msg, curses.A_NORMAL)
            status_offset += len(course[0])
        self.window.border()
        self.window.refresh()

    def run(self) -> CourseSubMenu | Menu:
        while True:
            curses.doupdate()
            status_offset = 1
            for index, course in enumerate(self.courses):
                status_offset += 2
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL
                msg = "%d. %s" % (index, course[0])
                self.window.addstr(1, status_offset + index, msg, mode)
                self.window.addstr(1, status_offset + index + 3, "")
                status_offset += len(course[0])
            self.window.refresh()
            curses.doupdate()
            key = self.window.getch()
            if key in [curses.KEY_ENTER, ord("\n")]:
                subMenu = self.update_callback(self.course_ids[self.position])
                subMenu.display()
                return subMenu
            elif key == ord("\t"): 
                break
            elif key == curses.KEY_BACKSPACE:
                break
            elif key == curses.KEY_LEFT or key == ord("k"):
                self.navigate(-1)
            elif key == curses.KEY_RIGHT or key == ord("j"):
                self.navigate(1)
            elif key == curses.KEY_BTAB:
                self.change_win_callback()

        self.window.border()
        self.window.refresh()


class Convas(object):
    def __init__(self, stdscreen):
        self.url = "https://canvas.umd.umich.edu/api/v1/courses"
        self.screen = stdscreen
        self.course_info = loads(open("data.json").read())
        self.course_names: list[str] = get_current_course_names(self.course_info)
        self.course_name_id_map: dict[str, str] = get_current_course_name_id_map(
            self.course_info
        )
        self.course_ids: list[str] = get_current_course_id(self.course_info)
        self.course_id: int | None = None
        self.course_menu = None
        self.height, self.width = stdscreen.getmaxyx()

    def switch_win_callback(is_statusbar, statusbar, win): 
        if is_statusbar: 
            win.display()
            # TODO: add callback to switch focus to the statusbar from the current window and  vice versa
        else: 
            statusbar.display()
            win.run()


    def run(self):
        main_window = curses.newwin(self.height - 3, self.width, 0, 0)
        course_menu_creator = lambda course_id: CourseSubMenu(main_window, course_id)
        main_window.border(2)
        statusbar = StatusBar(
            self.course_names,
            self.height,
            self.width,
            self.course_ids,
            course_menu_creator,
            self.switch_win_callback
        )
        splash = """
_________                                    
\_   ___ \  ____   _______  _______    ______
/    \  \/ /  _ \ /    \  \/ /\__  \  /  ___/
\     \___(  <_> )   |  \   /  / __ \_\___ \ 
 \______  /\____/|___|  /\_/  (____  /____  >
        \/            \/           \/     \/ 
        """
        try:
            self.screen.addstr(0, int(self.width / 2), splash)
            self.screen.refresh()
            statusbar.display()

            # select course
            selected = statusbar.run()
            statusbar.display()
            if selected : 
                selected.run()
        except KeyboardInterrupt:
            pass


def main(stdscr):
    if curses.has_colors():
        curses.start_color()
    convas = Convas(stdscr)
    convas.run()


if __name__ == "__main__":
    curses.wrapper(main)
