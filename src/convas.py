#!/usr/bin/env python3

import curses
import json
import os
import time
from collections import namedtuple
from curses import panel, wrapper
from json import loads
from typing import Any, Callable, Dict, List, Tuple

from config import Config
from convas_requests import (
    download_file,
    get_current_course_id,
    get_current_course_name_id_map,
    get_current_course_names,
)
from helper import Logger

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
        self.win_index = 2  # 2 = side_window, 3 = main_window
        self.tab_index = 0  # index of current heading

        self.assignment_info_headings = [
            "Home",
            "Announcements",
            "Assignments",
            "Discussions",
            "Grades",
            "Quizzes",
            "Files",
            "Syllabus",
        ]

        self.window.keypad(1)
        course_assignment_dates = namedtuple(
            "course_assignment_dates", ["created_at", "due_at"]
        )
        self.course_id = course_id
        self.assignment_info: list[dict[str, str]] = loads(
            (open(f"./assignments{course_id}.json").read())
        )  # get_assignments_request(url, headers, self.course_id)
        self.files: list[dict[str, str]] = loads(
            open(f"./files{course_id}.json").read()
        )
        self.quizzes: list[dict[str, str]] = loads(
            open(f"./quizzes{course_id}.json").read()
        )
        self.assignments: list[str] = [
            assignment["name"] for assignment in self.assignment_info
        ]
        self.assignment_id_map: dict[str, str] = {
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
        self.window.clear()
        self.window.refresh()
        rows, cols = self.window.getmaxyx()
        self.side_window = self.window.subwin(rows, int(cols * 0.2), 0, 0)
        self.main_window = self.window.subwin(rows, int(cols * 0.8), 0, int(cols * 0.2))

    def display(self):
        """Print the side_window to the screen"""
        self.side_window.clear()
        self.side_window.border()
        for index, item in enumerate(self.assignment_info_headings):
            msg = "%s" % (item)
            self.side_window.addstr(1 + index, 1, msg, curses.A_NORMAL)
        self.side_window.refresh()
        self.display_main_win(0)
        curses.doupdate()

    def set_position(self, pos: int):
        self.position = pos

    def navigate(self, n: int):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.assignment_info_headings):
            self.position = len(self.assignment_info_headings) - 1

    def display_main_win(self, heading: int):
        entry = self.assignment_info_headings[heading].lower()
        right_side_str, left_side_str, right_offset = None, None, None
        _, cols = self.main_window.getmaxyx()
        if entry == "assignments":
            left_side_str = [assignment["name"] for assignment in self.assignment_info]

        elif entry == "home":
            left_side_str = [assignment["name"] for assignment in self.assignment_info]

        elif entry == "discussions":
            pass

        elif entry == "grades":
            left_side_str = [
                assignment["name"]
                for assignment in self.assignment_info
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]

            right_side_str = [
                f"{assignment['points_possible']}/ {assignment['submission']['score']}"
                for assignment in self.assignment_info
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]

            right_offset = [
                (cols - len(str(right_str)) - 3) for right_str in right_side_str
            ]

        elif entry == "quizzes":
            left_side_str = [quiz["title"][0:20] for quiz in self.quizzes]
            right_side_str = [f"{quiz['due_at'][:10]}" for quiz in self.quizzes]
            right_offset = [
                (cols - len(str(right_str)) - 3) for right_str in right_side_str
            ]

        elif entry == "files":
            left_side_str = [file["display_name"] for file in self.files]
            Logger.info(left_side_str)
            right_side_str = [file["updated_at"][:10] for file in self.files]
            right_offset = [
                (cols - len(str(right_str)) - 3) for right_str in right_side_str
            ]

        if not left_side_str:
            return
        self.main_window.clear()
        self.main_window.border()
        for index, item in enumerate(left_side_str):
            self.main_window.addstr(1 + index, 1, item)
        if right_side_str:
            Logger.info(right_side_str)
            for index, item in enumerate(right_side_str):
                self.main_window.addstr(
                    1 + index,
                    (right_offset[index] if right_offset is not None else 1),
                    item,
                )
        self.main_window.refresh()
        self.main_window.border()
        curses.doupdate()

    def toggle_side_main_win(self):
        if self.win_index == 2:
            self.win_index = 3
            self.position = 0
            self.display()
            self.run_main_win()

        elif self.win_index == 3:
            self.win_index = 2
            self.position = self.tab_index
            self.display_main_win(self.tab_index)
            self.run()

    def open_url(self, url: str):
        # TODO:
        pass

    def run_main_win(self):

        def main_win_loop(
            left_side_str: List[str],
            bindings: List[Tuple[int, Callable[None, Any]]],
            right_side_str: List[str] | None = None,
            right_offset: int | None = None,
        ):
            self.main_window.clear()
            self.main_window.border()
            while True:
                for index, item in enumerate(left_side_str):
                    mode = (
                        curses.A_NORMAL if index != self.position else curses.A_REVERSE
                    )
                    self.main_window.addstr(1 + index, 1, item, mode)
                if right_side_str and right_offset:
                    for index, item in enumerate(right_side_str):
                        mode = (
                            curses.A_NORMAL
                            if index != self.position
                            else curses.A_REVERSE
                        )
                        self.main_window.addstr(
                            1 + index, (right_offset[index]), item, mode
                        )

                self.main_window.move(self.position + 1, 1)
                self.main_window.refresh()

                key = self.main_window.getch()

                if key == ord("h"):
                    break
                for binding in bindings:
                    if key == binding[0]:
                        binding[1]()
                        continue

        entry = self.assignment_info_headings[self.tab_index].lower()
        self.main_window.clear()
        self.main_window.border()
        _, cols = self.main_window.getmaxyx()
        if entry == "assignments":
            assignments = [assignment["name"] for assignment in self.assignment_info]
            while True:
                for index, assignment in enumerate(assignments):
                    mode = (
                        curses.A_NORMAL if index != self.position else curses.A_REVERSE
                    )
                    self.main_window.addstr(1 + index, 1, assignment, mode)

                self.main_window.border()
                self.main_window.refresh()

                key = self.window.getch()
                if key == curses.KEY_UP or key == ord("k"):
                    self.navigate(-1)
                elif key == curses.KEY_DOWN or key == ord("j"):
                    self.navigate(1)

                # TODO: Add "o" to open in browser
                elif key == ord("h"):
                    break

        elif entry == "home":
            assignments = [assignment["name"] for assignment in self.assignment_info]
            main_win_loop(
                assignments,
                [
                    (ord("k"), lambda: self.set_position(max(0, self.position - 1))),
                    (
                        ord("j"),
                        lambda: self.set_position(
                            min(self.position + 1, len(self.assignment_info) - 1)
                        ),
                    ),
                    (ord("o"), lambda: self.open_url()),
                ],
            )
            # TODO: Add "o" to open in browser

        elif entry == "discussions":
            pass
        elif entry == "grades":
            graded_assignments = [
                assignment
                for assignment in self.assignment_info
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]
            left_side_str = [assignment["name"] for assignment in graded_assignments]
            right_side_str = [
                f"{assignment['points_possible']}/ {assignment['submission']['score']}"
                for assignment in graded_assignments
            ]

            main_win_loop(
                left_side_str,
                [
                    (
                        ord("j"),
                        lambda: self.set_position(
                            min(self.position + 1, len(self.assignment_info) - 1)
                        ),
                    ),
                    (ord("k"), lambda: self.set_position(max(self.position - 1, 0))),
                ],
                right_side_str,
                right_offset=[
                    (cols - len(str(right_str)) - 3) for right_str in right_side_str
                ],
            )

        elif entry == "quizzes":
            left_side_str = [quiz["title"][0:20] for quiz in self.quizzes]
            right_side_str = [f"{quiz['due_at'][:10]}" for quiz in self.quizzes]
            left_offset = [
                (cols - len(str(right_str)) - 3) for right_str in right_side_str
            ]
            # TODO:

        elif entry == "files":
            files = [file for file in self.files]
            self.main_window.clear()
            self.main_window.border()
            while True:
                for index, file in enumerate(files):
                    left_side_str = " %s" % (file["display_name"])
                    right_side_str = " %s" % (file["updated_at"][:10])
                    _, cols = self.main_window.getmaxyx()
                    mode = (
                        curses.A_NORMAL if index != self.position else curses.A_REVERSE
                    )
                    self.main_window.addstr(
                        index + 1, cols - len(right_side_str) - 3, right_side_str, mode
                    )
                    self.main_window.addstr(1 + index, 1, left_side_str, mode)
                self.main_window.move(self.position + 1, 1)
                self.main_window.refresh()
                key = self.main_window.getch()
                if key == curses.KEY_UP or key == ord("k"):
                    self.position = max(self.position - 1, 0)
                elif key == curses.KEY_DOWN or key == ord("j"):
                    self.position = min(self.position + 1, len(files) - 1)
                elif key == ord("d"):
                    if not file["url"]:
                        return
                    # TODO: prompt for file name (maybe default to the same name? )
                    download = download_file(
                        file["id"], self.course_id, file["display_name"], headers={}
                    )
                    if not download:
                        pass
                    # TODO: return errro
                elif key == ord("h"):
                    break

        elif entry == "syllabus":
            pass

        self.toggle_side_main_win()

    def run(self):
        """Loop for selecting tab"""
        for index, item in enumerate(self.assignment_info_headings):
            if index == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL
            msg = "%d. %s" % (index, item[0])
            self.side_window.addstr(1 + index, 1, msg, mode)
        while True:
            for index, item in enumerate(self.assignment_info_headings):
                mode = curses.A_REVERSE if index == self.position else curses.A_NORMAL
                msg = "%s" % (item)
                self.side_window.addstr(1 + index, 1, msg, mode)
            self.side_window.move(self.position + 1, 1)
            self.side_window.refresh()
            self.side_window.border()
            curses.doupdate()

            key = self.side_window.getch()
            if key == curses.KEY_UP or key == ord("k"):
                self.navigate(-1)

            elif key == curses.KEY_DOWN or key == ord("j"):
                self.navigate(1)

            elif key == ord("l"):
                self.toggle_side_main_win()

            elif key == ord("\t"):
                self.switch_to_statusbar_callback(self)

            elif key in [curses.KEY_ENTER, ord("\n")]:
                self.tab_index = self.position
                br = self.display_main_win(int(self.position))
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
        self,
        courses,
        height: int,
        width: int,
        course_ids,
        update_callback,
        change_win_callback,
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
        status_offset = 1
        self.window.clear()
        self.window.border()
        for index, course in enumerate(self.courses):
            status_offset += 2
            msg = "%d.%s" % (index, course[0])
            self.window.addstr(1, status_offset + index, msg, curses.A_NORMAL)
            self.window.addstr(1, status_offset + index + 3, "")
            status_offset += len(course[0])
        self.window.refresh()
        curses.doupdate()

    def run(self) -> CourseSubMenu | Menu:
        self.window.scrollok(True)
        return self.focus()

    def focus(self) -> CourseSubMenu | Menu:
        while True:
            status_offset = 1
            self.window.clear()
            self.window.border()
            for index, course in enumerate(self.courses):
                status_offset += 2
                if index == self.position:
                    mode = curses.A_REVERSE
                else:
                    mode = curses.A_NORMAL
                msg = "%d.%s" % (index, course[0])
                self.window.addstr(1, status_offset + index, msg, mode)
                self.window.addstr(1, status_offset + index + 3, "")
                status_offset += len(course[0])
            self.window.refresh()
            curses.doupdate()

            key = self.window.getch()
            if key in [curses.KEY_ENTER, ord("\n")]:
                submenu = self.update_callback(
                    self.course_ids[self.position]
                )  # creates a new CourseSubMenu object
                self.prev_win = submenu
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
        self.status_bar: StatusBar = None
        # TODO:
        self.command_panel = panel.new_panel(stdscreen)

    @staticmethod
    def switch_win_callback(switch_to_statusbar, statusbar, win):
        if switch_to_statusbar:
            win.display()
            selected = statusbar.focus()
            statusbar.display()
            if selected:
                selected.run()
        else:
            statusbar.display()
            win.run()

    def run(self) -> None:
        """Main loop"""
        main_window = curses.newwin(self.height - 3, self.width, 0, 0)
        main_window.border()
        self.status_bar = StatusBar(
            self.course_names,
            self.height,
            self.width,
            self.course_ids,
            lambda course_id: CourseSubMenu(
                main_window,
                course_id,
                lambda win: self.switch_win_callback(True, self, win),
            ),
            self.switch_win_callback,
        )
        self.status_bar.__init__(
            self.course_names,
            self.height,
            self.width,
            self.course_ids,
            lambda course_id: CourseSubMenu(
                main_window,
                course_id,
                lambda win: self.switch_win_callback(True, self.status_bar, win),
            ),
            self.switch_win_callback,
        )

        splash = r"""
 ________  ________  ________   ___      ___ ________  ________ 
|\   ____\|\   __  \|\   ___  \|\  \    /  /|\   __  \|\   ____\
\ \  \___|\ \  \|\  \ \  \\ \  \ \  \  /  / | \  \|\  \ \  \___|_
 \ \  \    \ \  \\\  \ \  \\ \  \ \  \/  / / \ \   __  \ \_____  \
  \ \  \____\ \  \\\  \ \  \\ \  \ \    / /   \ \  \ \  \|____|\  \
   \ \_______\ \_______\ \__\\ \__\ \__/ /     \ \__\ \__\____\_\  \
    \|_______|\|_______|\|__| \|__|\|__|/       \|__|\|__|\_________\
                                                          |__________|
        """

        try:
            Logger.info(f"Convas initialized with {self.height}x{self.width}")
            y_position = (self.height - 3 * 6) // 2
            x_position = int(max(len(line) for line in splash.splitlines())) // 2 - 5
            for i, line in enumerate(splash.split("\n")):
                self.screen.addstr(y_position + i, x_position, line)
            self.screen.refresh()
            self.status_bar.display()
            selected = self.status_bar.run()
            self.status_bar.display()
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
