#!/usr/bin/env python3

import curses
import json
import os
import time
from collections import namedtuple
from curses import panel, wrapper
from json import loads

from config import Config
from convas_requests import (
    get_current_course_id,
    get_current_course_name_id_map,
    get_current_course_names,
)
from helper import Logger

# from urllib import error, request


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

with open(CONFIG_FILE) as file:
    for line in file:
        if "=" in line:
            key, value = line.strip().split("=")
            config = Config(value)

if "config" not in globals():
    raise Exception("Unable to read config file")

url = "https://canvas.umd.umich.edu/api/v1/courses"

headers = {"Authorization": f"Bearer {config.get_token()}"}

with open("data.json") as file:
    data = file.read()
    all_courses = json.loads(data)


class Menu(object):
    def __init__(self, items, stdscreen):
        """
        items: [str, function on click]
        stdscreen: the screen instance
        """
        self.window = stdscreen.subwin(0, 0)
        self.window.keypad(1)
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
        self.window.clear()
        curses.doupdate()
        for index, item in enumerate(self.items):
            msg = "%d. %s" % (index, item[0])
            self.window.addstr(1 + index, 1, msg, curses.A_NORMAL)
        self.window.refresh()
        curses.doupdate()

    def run(self):
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
        curses.doupdate()


class CourseSubMenu(Menu):
    """Submenu for Course details"""

    def __init__(self, stdscreen, course_id, switch_to_statusbar_callback):
        self.window = stdscreen.subwin(0, 0)
        # handle arrow keys
        self.window.keypad(1)
        course_assignment_dates = namedtuple(
            "course_assignment_dates", ["created_at", "due_at"]
        )
        self.course_id = course_id
        self.assignment_info: list[dict[str, str]] = loads(
            (open(f"./assignments{course_id}.json").read())
        )  # get_assignments_request(url, headers, self.course_id)
        self.assignments: list[str] = [
            assignment["name"] for assignment in self.assignment_info
        ]
        self.assignment_id_map: list[dict[str, str]] = {
            assignment["id"]: assignment["name"] for assignment in self.assignment_info
        }
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
        self.switch_to_statusbar_callback = switch_to_statusbar_callback
        super().__init__(
            [
                [
                    assignment["name"],
                    lambda: self.display_assignment_info(assignment["id"]),
                ]
                for assignment in self.assignment_info
            ],
            stdscreen,
        )
        self.assignment_info_headings = [
            "Home",
            "Announcements",
            "Assignments",
            "Discussions",
            "Grades",
            "People",
            "Files",
            "Syllabus",
        ]

        self.window.clear()
        self.window.refresh()
        rows, cols = self.window.getmaxyx()
        self.side_window = self.window.subwin(rows, int(cols * 0.2), 0, 0)
        self.main_window = self.window.subwin(rows, int(cols * 0.8), 0, int(cols * 0.2))

    def display(self):
        """Print the menu to the screen without focusing on the menu"""
        self.window.clear()
        self.window.refresh()
        self.side_window.border()
        self.main_window.border()
        curses.doupdate()

    def navigate(self, n):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.assignment_info_headings):
            self.position = len(self.assignment_info_headings) - 1

    def assignment_info_callback(self, heading: int):
        entry = self.assignment_info_headings[heading].lower()
        self.main_window.clear()
        self.main_window.border()
        if entry == "assignments":
            pass
        elif entry == "home":
            assignments = [assignment["name"] for assignment in self.assignment_info]
            for index, item in (enumerate(assignments)):
                self.main_window.addstr(1+index, 1, item)
        elif entry == "discussions":
            pass
        elif entry == "grades":
            pass
        elif entry == "people":
            pass
        elif entry == "files":
            pass
        elif entry == "syllabus":
            pass
        self.main_window.refresh()
        curses.doupdate()

    def run(self):
        """Print list of courses and run the main loop"""
        Logger.info(self.assignment_info)
        for index, item in enumerate(self.assignment_info_headings):
            if index == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL
            msg = "%d. %s" % (index, item[0])
            self.side_window.addstr(1 + index, 1, msg, mode)
        while True:
            self.side_window.refresh()
            for index, item in enumerate(self.assignment_info_headings):
                mode = curses.A_REVERSE if index == self.position else curses.A_NORMAL
                msg = "%s" % (item)
                self.side_window.addstr(1 + index, 1, msg, mode)
            self.side_window.refresh()
            curses.doupdate()
            key = self.side_window.getch()
            if key == curses.KEY_UP or key == ord("k"):
                self.navigate(-1)
            elif key == curses.KEY_DOWN or key == ord("j"):
                self.navigate(1)

            elif key == ord("\t"):
                self.switch_to_statusbar_callback(self)

            elif key in [curses.KEY_ENTER, ord("\n")]:
                if self.position == len(self.assignment_info_headings) - 1:
                    break
                else:
                    br = self.assignment_info_callback(int(self.position))
                    if br:
                        break
        self.side_window.refresh()
        curses.doupdate()

    #
    # def create_scrollable_container(stdscreen, height, width, y, x, contents):
    #     container = stdscreen.subwin(height, width, y, x)
    #     container.scrollok(True)  # Enable scrolling
    #     container.box()  # Draw a box around the container
    #     for i, line in enumerate(contents):
    #         container.addstr(i + 1, 1, line)  # Add content to the container
    #     return container

    def display_assignment_info(self, assignment_id: int) -> int:
        assignment_name = self.assignment_id_map[assignment_id]
        assignment_description = self.assignment_descriptions
        print(assignment_description)
        created_at, due_at = self.assignment_dates[assignment_name]
        assignment_points = [
            assignment["points_possible"] for assignment in self.assignment_info
        ]

        self.window.clear()
        self.window.refresh()

        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)
        for index, entry in enumerate(self.assignment_info_headings):
            self.side_window.addstr(
                int(index) + 1, 2, entry, curses.A_BOLD | curses.color_pair(1)
            )

        Logger.info(assignment_description)
        Logger.info(self.assignment_info)

        time.sleep(3)
        exit()
        return 1


class StatusBar(Menu):
    """Statusbar Class using newwin"""

    def __init__(
        self, courses, height : int, width : int , course_ids , update_callback, change_win_callback
    ):
        self.window = curses.newwin(3, width, height - 3, 0)
        self.position = 0
        self.course_ids = course_ids
        self.courses = [
            (course[: course.find("(")], course) if (course.find("(") != -1) else course
            for course in courses
        ]
        self.update_callback = update_callback
        self.change_win_callback = change_win_callback

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
                submenu = self.update_callback(self.course_ids[self.position]) # creates a new CourseSubMenu object
                self.prev_win  = submenu
                submenu.display()
                return submenu
            elif key == ord("\t"):
                break
            elif key == curses.KEY_BACKSPACE:
                self.change_win_callback(False, self, self.prev_win)
            elif key == curses.KEY_LEFT or key == ord("k"):
                self.navigate(-1)
            elif key == curses.KEY_RIGHT or key == ord("j"):
                self.navigate(1)

        self.window.border()
        self.window.refresh()


class Convas(object):
    """Class to store parent window"""

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

    def switch_win_callback(self, switch_to_statusbar, statusbar, win):
        if switch_to_statusbar:
            win.display()
            selected = statusbar.run()
            statusbar.display()
            if selected:
                selected.run()
        else:
            statusbar.display()
            win.run()

    def run(self):
        """Main loop"""
        main_window = curses.newwin(self.height - 3, self.width, 0, 0)
        main_window.border(2)
        statusbar = StatusBar(
            self.course_names,
            self.height,
            self.width,
            self.course_ids,
            lambda course_id: CourseSubMenu(main_window, course_id, lambda win:  self.switch_win_callback(True,self,  win)),
            self.switch_win_callback,
        )
        splash = """
  ___   ___   __  __ __ __  ___   __ 
 //    // \\  ||\ || || || // \\ (( \
((    ((   )) ||\\|| \\ // ||=||  \\ 
 \\__  \\_//  || \||  \V/  || || \_))
        """

        try:
            self.screen.addstr(0, int(self.width / 2), splash)
            self.screen.refresh()
            statusbar.display()

            # select course
            selected = statusbar.run()
            statusbar.display()
            if selected:
                selected.run()
        except KeyboardInterrupt:
            pass


def main(stdscr):
    curses.use_default_colors()
    convas = Convas(stdscr)
    convas.run()


if __name__ == "__main__":
    curses.wrapper(main)
