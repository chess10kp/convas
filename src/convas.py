#!/usr/bin/env python

from re import sub
import curses
import os
import platform
import subprocess
from curses import panel
from inspect import getfullargspec
from json import loads
from typing import Any, Callable, Dict, List, Optional, Tuple
from html import unescape
from config import Config
from convas_requests import (
    download_file,
    get_current_course_id,
    get_current_course_names,
    get_discussions,
)
from helper import Logger, show_panel, show_panel_hide_on_keypress

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME
BORDER = 1

with open(CONFIG_FILE) as file:
    for line in file:
        if "=" in line:
            key, value = line.strip().split("=")
            config = Config(value)

if "config" not in globals():
    raise Exception("Unable to read config file")

url = "https://canvas.umd.umich.edu/api/v1/courses"

headers = {"Authorization": f"Bearer {config.get_token()}"}


class Menu(object):
    def __init__(self, items, stdscreen):
        self.window = stdscreen.subwin(0, 0)
        self.position = 0

    def navigate(self, n):
        raise NotImplementedError

    def display(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError


class CourseSubMenu(Menu):
    def __init__(
        self,
        window: Any,
        course_id: int,
        switch_to_statusbar_callback: Callable[Any, None],
        gutter_callback: Callable[None, None],
        keybind_help: Callable[List[Tuple[str, str]], None],
    ):
        self.window = window
        self.window.scrollok(True)
        self.window.keypad(1)
        self.win_index = 2  # 2 = side_window, 3 = main_window
        self.tab_index = 0
        self.gutter_mode = gutter_callback
        self.set_keybind_help = keybind_help
        self.tabs = [
            "Home",
            "Announcements",
            "Assignments",
            "Discussions",
            "Grades",
            "Quizzes",
            "Files",
        ]
        self.announcements = None
        self.quizzes = None
        self.files = None
        rows, cols = self.window.getmaxyx()
        self.side_window = self.window.subwin(rows, int(cols * 0.2), 0, 0)
        self.main_win = self.window.subwin(rows, int(cols * 0.8), 0, int(cols * 0.2))
        self.main_win.scrollok(True)
        self.main_win_panel = panel.new_panel(self.main_win)
        self.main_win_panel.top()
        self.main_win_popup = self.window.subwin(
            int(rows * 0.8), int(cols * 0.6), 0, int(cols * 0.2)
        )
        self.main_win_popup_panel = panel.new_panel(self.main_win)
        self.main_win_start = 0
        self.main_win_end = 0
        self.course_id = course_id
        self.assignments: list[dict[str, str]] = loads(
            (open(f"./assignments{course_id}.json").read())
        )
        self.switch_to_statusbar_callback = switch_to_statusbar_callback

        def file_exists(filename: str) -> bool:
            return subprocess.run(["ls", filename]).returncode == 0

        if file_exists(f"./files{course_id}.json"):
            self.files: list[dict[str, str]] = loads(
                open(f"./files{course_id}.json").read()
            )
        if file_exists(f"./quizzes{course_id}.json"):
            self.quizzes: list[dict[str, str]] = loads(
                open(f"./quizzes{course_id}.json").read()
            )
        if file_exists(f"./announcements{course_id}.json"):
            self.announcements = loads(open(f"./announcements{course_id}.json").read())

        if not isinstance(self.files, List):
            self.tabs.remove("Files")
        if not isinstance(self.quizzes, List):
            self.tabs.remove("Quizzes")
        if not isinstance(self.announcements, List):
            self.tabs.remove("Announcements")

        super().__init__(
            [
                [
                    assignment["name"],
                    lambda: self.display_assignment_info(assignment["id"]),
                ]
                for assignment in self.assignments
            ],
            window,
        )
        self.window.clear()
        self.window.refresh()

    def display(self):
        """Print the side_window to the screen"""
        self.side_window.clear()
        self.side_window.border()
        for index, item in enumerate(self.tabs):
            msg = "%s" % (item)
            self.side_window.addstr(1 + index, 1, msg, curses.A_NORMAL)
        self.side_window.refresh()

    def set_position(self, pos: int):
        self.position = pos

    def navigate(self, n: int):
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.tabs):
            self.position = len(self.tabs) - 1

    def display_main_win(self, heading: int):
        entry = self.tabs[heading].lower()
        rows_per_item = 1
        right_side_str, left_side_str, right_offset = None, None, None
        rows, cols = self.main_win.getmaxyx()
        if entry == "assignments":
            left_side_str = [assignment["name"] for assignment in self.assignments]

        elif entry == "home":
            graded_assignments = [
                assignment
                for assignment in self.assignments
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]
            right_side_str = [
                f"{assignment['points_possible']}/ {assignment['submission']['score']}"
                for assignment in self.assignments
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]
            current_grade = []

            # TODO: figure out how to get current grade
            # { "braille_up", {
            # 	" ", "⢀", "⢠", "⢰", "⢸",
            # 	"⡀", "⣀", "⣠", "⣰", "⣸",
            # 	"⡄", "⣄", "⣤", "⣴", "⣼",
            # 	"⡆", "⣆", "⣦", "⣶", "⣾",
            # 	"⡇", "⣇", "⣧", "⣷", "⣿"
            # }},
            # {"braille_down", {
            # 	" ", "⠈", "⠘", "⠸", "⢸",
            # 	"⠁", "⠉", "⠙", "⠹", "⢹",
            # 	"⠃", "⠋", "⠛", "⠻", "⢻",
            # 	"⠇", "⠏", "⠟", "⠿", "⢿",
            # 	"⡇", "⡏", "⡟", "⡿", "⣿"
            # }},
            # {"block_up", {
            # 	" ", "▗", "▗", "▐", "▐",
            # 	"▖", "▄", "▄", "▟", "▟",
            # 	"▖", "▄", "▄", "▟", "▟",
            # 	"▌", "▙", "▙", "█", "█",
            # 	"▌", "▙", "▙", "█", "█"
            # }},
            # {"block_down", {
            # 	" ", "▝", "▝", "▐", "▐",
            # 	"▘", "▀", "▀", "▜", "▜",
            # 	"▘", "▀", "▀", "▜", "▜",
            # 	"▌", "▛", "▛", "█", "█",
            # 	"▌", "▛", "▛", "█", "█"
            # }},
            # {"tty_up", {
            # 	" ", "░", "░", "▒", "▒",
            # 	"░", "░", "▒", "▒", "█",
            # 	"░", "▒", "▒", "▒", "█",
            # 	"▒", "▒", "▒", "█", "█",
            # 	"▒", "█", "█", "█", "█"
            # }},
            # {"tty_down", {
            # 	" ", "░", "░", "▒", "▒",
            # 	"░", "░", "▒", "▒", "█",
            # 	"░", "▒", "▒", "▒", "█",
            # 	"▒", "▒", "▒", "█", "█",
            # 	"▒", "█", "█", "█", "█"
            # }}

            left_side_str = [assignment["name"] for assignment in self.assignments]

        # fmt: off
        elif entry == "announcements":
            left_side_str = [
                [announcement["user_name"], announcement["title"], ""]
                for announcement in self.announcements
            ]
            right_side_str = [
                [announcement["created_at"][:10], "", ""]
                for announcement in self.announcements
            ]
            right_offset = [
                [(cols - len(str(right_str)) - 3), 0, 0] for right_str in right_side_str
            ]
            rows_per_item = 3
        elif entry == "discussions":
            discussions = get_discussions(self.assignments)
            left_side_str = [assignment["name"] for assignment in discussions]
        elif entry == "grades":
            left_side_str = [
                assignment["name"]
                for assignment in self.assignments
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]
            right_side_str = [
                f"{assignment['points_possible']}/ {assignment['submission']['score']}"
                for assignment in self.assignments
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
            right_side_str = [file["updated_at"][:10] for file in self.files]
            right_offset = [
                (cols - len(str(right_str)) - 3) for right_str in right_side_str
            ]
        # fmt: on

        if not left_side_str:
            return
        self.main_win.clear()
        self.main_win.border()

        max_rows = rows - 2
        self.main_win_end = (
            min(
                (len(left_side_str) - self.main_win_start),
                (max_rows - rows_per_item) // rows_per_item,
            )
            + 1
        )

        for index, item in enumerate(
            left_side_str[self.main_win_start : self.main_win_end]
        ):
            if isinstance(item, str):
                self.main_win.addstr(1 + index, 1, item)
            else:
                for i in range(rows_per_item):
                    self.main_win.addstr(rows_per_item * index + i + 1, 1, item[i])
        if right_side_str:
            for index, item in enumerate(
                right_side_str[self.main_win_start : self.main_win_end]
            ):
                if isinstance(item, str):
                    self.main_win.addstr(
                        1 + index,
                        (right_offset[index] if right_offset is not None else 1),
                        item,
                    )
                else:
                    for i in range(rows_per_item):
                        self.main_win.addstr(
                            1 + rows_per_item * index + i,
                            (right_offset[index][i] if right_offset is not None else 1),
                            item[i],
                        )
        self.main_win.refresh()

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

    def open_url(self, current_os, url: str):
        if current_os == "Linux":
            subprocess.run("xdg_open %s" % (url))
        elif current_os == "Windows":
            subprocess.run("start msedge %s" % (url))
        elif current_os == "darwin":
            subprocess.run("open %s" % (url))
        else:
            # I'm guessing you're probably using firefox on a BSD
            for path in ["/usr/bin", "/usr/local/bin"]:
                if os.path.exists(os.path.join(path, "firefox")):
                    subprocess.run("firefox %s" % (url))

    def main_win_panel_render(self, content: str | List[str]):
        """Display a panel over the main window with custom content"""
        rows, cols = self.main_win.getmaxyx()
        self.main_win_panel.hide()
        self.main_win_popup.clear()
        self.main_win_popup.border()
        if isinstance(content, list):
            for row in content:
                self.main_win_popup.addstr(row)
        elif isinstance(content, str):
            self.main_win_popup.addstr(content)
        self.main_win_popup.refresh()
        show_panel_hide_on_keypress(self.main_win_popup_panel, self.main_win)
        self.main_win_panel.show()

    def run_main_win(self):
        self.set_keybind_help(
            [
                ("j", "next"),
                ("k", "prev"),
                (":", "cmd mode"),
                ("h", "switch to side panel"),
                ("o", "open in browser"),
            ]
        )

        def main_win_loop(
            left_side_str: List[str],
            bindings: List[Tuple[int, Callable[None, Any] | Callable[str, Any], str]],
            right_side_str: List[str] | None = None,
            right_offset: int | None = None,
            args: Optional[List[str]] = [],
        ):
            rerender = 1
            has_right = right_side_str is not None

            def rerender_main_win():
                self.main_win.border()
                for index in range(self.main_win_start, self.main_win_end):
                    left = left_side_str[self.main_win_start + index]
                    right = (
                        right_side_str[self.main_win_start + index]
                        if has_right
                        else None
                    )
                    offset = (
                        right_offset[self.main_win_start + index] if has_right else None
                    )
                    if isinstance(left, str):
                        self.main_win.addstr(1 + index, 1, left[index])
                        self.main_win.addstr(
                            1 + index * rows_per_item,
                            (offset),
                        )
                    else:
                        for i in range(rows_per_item):
                            self.main_win.addstr(
                                rows_per_item * index + i + 1, 1, left[i]
                            )
                            self.main_win.addstr(
                                1 + rows_per_item * index + i,
                                (offset[i] if offset is not None else 1),
                                right[i],
                            )
                self.main_win.move(self.position * rows_per_item + BORDER, BORDER)
                return 0  # return 0 to stop rerendering

            while True:
                if rerender:
                    rerender = rerender_main_win()
                for index in range(self.main_win_start, self.main_win_end):
                    if not (
                        self.position == index
                        or self.position - 1 == index
                        or self.position + 1 == index
                    ):  # rerender only if the entry is the previous or the next one of self.position
                        continue
                    mode = (
                        curses.A_NORMAL if index != self.position else curses.A_REVERSE
                    )
                    left = left_side_str[self.main_win_start + index]
                    right = (
                        right_side_str[self.main_win_start + index]
                        if has_right
                        else None
                    )
                    offset = (
                        right_offset[self.main_win_start + index] if has_right else None
                    )
                    if isinstance(left, str):
                        self.main_win.addstr(1 + index, 1, left, mode)
                        self.main_win.addstr(
                            1 + index * rows_per_item,
                            (offset[index]),
                            right[index],
                            mode,
                        )
                    else:
                        for i in range(rows_per_item):
                            self.main_win.addstr(
                                rows_per_item * index + i + 1, 1, left[i], mode
                            )
                            self.main_win.addstr(
                                1 + rows_per_item * index + i,
                                (offset[i] if offset is not None else 1),
                                right[i],
                                mode,
                            )

                self.main_win.move(self.position * rows_per_item + 1, 1)
                self.main_win.refresh()
                key = self.main_win.getch()

                if key == ord("h"):
                    break
                elif key == ord(":"):
                    self.gutter_mode()

                for binding in bindings:
                    if key == binding[0]:
                        callback_signature_args = getfullargspec(binding[1]).args
                        if callback_signature_args == []:
                            binding[1]()
                            rerender = 1
                        elif (
                            len(callback_signature_args) == 1
                            and callback_signature_args[0] == "url"
                        ):
                            binding[1](args[self.position])
                            rerender = 0

        entry = self.tabs[self.tab_index].lower()
        rows_per_item = 1
        rows, cols = self.main_win.getmaxyx()
        if entry == "assignments":
            assignments = [assignment["name"] for assignment in self.assignments]
            while True:
                for index, assignment in enumerate(assignments):
                    mode = (
                        curses.A_NORMAL if index != self.position else curses.A_REVERSE
                    )
                    self.main_win.addstr(1 + index, 1, assignment, mode)
                self.main_win.refresh()
                key = self.window.getch()
                if key == curses.KEY_UP or key == ord("k"):
                    self.navigate(-1)
                elif key == curses.KEY_DOWN or key == ord("j"):
                    self.navigate(1)
                elif key == ord("h"):
                    break
                elif key == ord(":"):
                    self.gutter_mode()

        elif entry == "announcements":
            # TODO: add scrolling for other tabs
            def navigate(n: int):
                if self.position + n < len(
                    left_side_str[self.main_win_start : self.main_win_end]
                ):
                    self.main_win_start = max(0, self.main_win_start + n)
                    self.main_win_end = (
                        min(
                            len(left_side_str[self.main_win_start : self.main_win_end]),
                            self.main_win_end + n,
                        )
                        + 1
                    )
                    self.set_position(self.position + n)

            def show_annoucement(id: int):
                Logger.info("hi")
                message = [
                    sub("<[^<]+?>", "", unescape(anouncement["message"]))
                    for anouncement in self.announcements
                    if anouncement["id"] == id
                ]
                self.main_win_panel_render(message)

            # fmt: off
            left_side_str = [ [announcement["user_name"], announcement["title"], ""] for announcement in self.announcements ]
            right_side_str = [ [announcement["created_at"][:10], "", ""] for announcement in self.announcements ]
            right_offset = [ [(cols - len(str(right_str)) - 3), 0, 0] for right_str in right_side_str ] 
            rows_per_item = 3
            max_rows = rows - 2
            self.main_win_end = ( min((len(left_side_str[self.main_win_start :])), (max_rows - rows_per_item) // rows_per_item,) + 1)
            # fmt: on
            main_win_loop(
                left_side_str,
                [
                    (
                        ord("j"),
                        lambda: self.set_position(
                            min(
                                self.position + 1,
                                len(
                                    left_side_str[
                                        self.main_win_start : self.main_win_end
                                    ]
                                )
                                - 1,
                            )
                        ),
                    ),
                    (ord("k"), lambda: self.set_position(max(self.position - 1, 0))),
                    (
                        ord("o"),
                        lambda: show_annoucement(
                            self.announcements[self.position + self.main_win_start][
                                "id"
                            ]
                        ),
                    ),
                ],
                right_side_str,
                right_offset,
            )
        elif entry == "home":
            assignments = [assignment["name"] for assignment in self.assignments]
            main_win_loop(
                assignments,
                [
                    (
                        ord("k"),
                        lambda: self.set_position(max(0, self.position - 1)),
                        "up",
                    ),
                    (
                        ord("j"),
                        lambda: self.set_position(
                            min(self.position + 1, len(self.assignments) - 1)
                        ),
                        "down",
                    ),
                    (ord("o"), lambda: self.open_url(), "open in browser"),
                ],
            )
            # TODO: Add "o" to open in browser
            # TODO: Remove the cursor from all screens except when entering input

        elif entry == "discussions":
            pass
        elif entry == "grades":
            graded_assignments = [
                assignment
                for assignment in self.assignments
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
                            min(self.position + 1, len(self.assignments) - 1)
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
            right_offset = [
                (cols - len(str(right_str)) - 3) for right_str in right_side_str
            ]
            main_win_loop(
                left_side_str,
                [
                    (
                        ord("j"),
                        lambda: self.set_position(
                            min(self.position + 1, len(self.quizzes) - 1)
                        ),
                    ),
                    (ord("k"), lambda: self.set_position(max(self.position - 1, 0))),
                ],
                right_side_str,
                right_offset,
            )

        elif entry == "files":
            files = [file for file in self.files]
            self.main_win.clear()
            while True:
                for index, file in enumerate(files):
                    left_side_str = " %s" % (file["display_name"])
                    right_side_str = " %s" % (file["updated_at"][:10])
                    _, cols = self.main_win.getmaxyx()
                    mode = (
                        curses.A_NORMAL if index != self.position else curses.A_REVERSE
                    )
                    self.main_win.addstr(
                        index + 1, cols - len(right_side_str) - 3, right_side_str, mode
                    )
                    self.main_win.addstr(1 + index, 1, left_side_str, mode)
                self.main_win.move(self.position + 1, 1)
                self.main_win.refresh()
                key = self.main_win.getch()
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
        self.set_keybind_help(
            [
                ("j", "next"),
                ("k", "prev"),
                (":", "cmd mode"),
                ("l", "switch to main pane"),
            ]
        )
        for index, item in enumerate(self.tabs):
            if index == self.position:
                mode = curses.A_REVERSE
            else:
                mode = curses.A_NORMAL
            msg = "%d. %s" % (index, item[0])
            self.side_window.addstr(1 + index, 1, msg, mode)
        while True:
            for index, item in enumerate(self.tabs):
                mode = curses.A_REVERSE if index == self.position else curses.A_NORMAL
                msg = "%s" % (item)
                self.side_window.addstr(1 + index, 1, msg, mode)
            self.side_window.move(self.position + 1, 1)
            self.side_window.border()
            self.side_window.refresh()

            key = self.side_window.getch()
            if key == curses.KEY_UP or key == ord("k"):
                self.navigate(-1)

            elif key == curses.KEY_DOWN or key == ord("j"):
                self.navigate(1)

            elif key == ord("l"):
                self.toggle_side_main_win()

            elif key == ord("\t"):
                self.switch_to_statusbar_callback(self)

            elif key == ord(":"):
                self.gutter_mode()

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


class StatusBar(Menu):
    def __init__(
        self,
        courses: List[str],
        height: int,
        width: int,
        course_ids: List[int],
        update_callback: Callable[int, None],
        change_win_callback: Callable[Any, None],
        set_keybind_help: Callable[List[Tuple[str, str]], None],
        display_binds: Callable[Tuple[Any, Any], None],
    ):
        self.window = curses.newwin(3, width, height - 3, 0)
        self.position = 0
        self.course_ids = course_ids
        self.courses = [
            (
                (course[: course.find("(")], course)
                if (course.find("(") != -1)
                else course
            )
            for course in courses
        ]  # ))
        self.update_callback = update_callback
        self.change_win_callback = change_win_callback
        self.keybinds = []
        self.cmds = {
            "help": lambda: display_binds((curses.A_BOLD, curses.A_NORMAL)),
            "h": lambda: display_binds((curses.A_BOLD, curses.A_NORMAL)),
            "quit": lambda: None,
            "q": lambda: None,
        }
        self.set_keybind_help = set_keybind_help

    def navigate(self, n: int) -> None:
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.courses):
            self.position = len(self.courses) - 1

    def display(self) -> None:
        self.window.clear()
        self.window.border()
        status_offset = 1
        for index, course in enumerate(self.courses):
            status_offset += 2
            msg = "%d.%s " % (index, course[0])
            self.window.addstr(1, status_offset + index, msg, curses.A_NORMAL)
            self.window.addstr(1, status_offset + index + 3, "")
            status_offset += len(course[0])
        self.window.refresh()

    def run(self) -> CourseSubMenu | Menu:
        self.window.scrollok(True)
        return self.focus()

    def focus(self) -> CourseSubMenu | Menu:
        self.set_keybind_help([("j", "next"), ("k", "prev"), (":", "cmd mode")])
        while True:
            cursor, left_offset = 3, 3
            self.window.clear()
            self.window.border()
            for index, course in enumerate(self.courses):
                mode = curses.A_REVERSE if index == self.position else curses.A_NORMAL
                if self.position == index:
                    cursor = left_offset + index
                msg = "%d.%s" % (index, course[0])
                self.window.addstr(1, left_offset + index, msg + " " * 2, mode)
                left_offset += len(course[0]) + 2
            self.window.refresh()
            self.window.move(1, cursor)
            key = self.window.getch()
            if key in [curses.KEY_ENTER, ord("\n")]:
                submenu = self.update_callback(self.course_ids[self.position])
                self.prev_win = submenu
                submenu.display()
                return submenu
            elif key == curses.KEY_RIGHT or key == ord("j"):
                self.navigate(1)
            elif key == curses.KEY_LEFT or key == ord("k"):
                self.navigate(-1)
            elif key == ord("\t"):
                break
            elif key == curses.KEY_BACKSPACE:
                break
            elif key == ord(":"):
                self.gutter_mode()
        self.window.refresh()

    @staticmethod
    def eval_command(cmds: Dict[str, Callable[None, None]], cmd: str) -> bool:
        if cmd in cmds.keys():
            cmds[cmd]()
            return True
        return False

    def gutter_mode(self) -> None:
        input = TextInput(self.window, lambda cmd: self.eval_command(self.cmds, cmd))
        input.run()
        self.display()


class TextInput:
    def __init__(self, window: Any, eval_cmd: Callable[str, bool]):
        self.window = window
        self.validate = eval_cmd

    def run(self) -> None:
        buffer = ""
        cursor = 1
        self.window.clear()
        self.window.border()
        while True:
            self.window.addstr(1, 1, buffer)
            self.window.move(1, cursor)
            self.window.refresh()
            key = self.window.getch()
            if chr(key).isalpha():
                buffer = buffer[:cursor] + chr(key) + buffer[cursor:]
                cursor += 1
            elif key == curses.KEY_BACKSPACE or key == 127:
                buffer = buffer[:-1]
                cursor = max(1, cursor - 1)
                self.window.clear()
                self.window.border()
            elif key == 2:  # C-b
                cursor = max(1, cursor - 1)
            elif key == 6:  # C-f
                cursor = min(cursor + 1, len(buffer) + 1)
            elif key == 1:  # C-a
                cursor = 1
            elif key == 5:  # C-e
                cursor = len(buffer) + 1  # includes border
            elif key == 11:  # C-k
                buffer = buffer[: cursor - 1]
                self.window.clear()
                self.window.border()
            elif key == 27:  # Esc
                return ""
            elif key == ord("\n"):
                if self.validate(buffer):
                    return buffer
            else:
                self.window.addstr(str(key))


class Convas(object):
    def __init__(self, stdscreen):
        self.url = "https://canvas.umd.umich.edu/api/v1/courses"
        self.screen = stdscreen
        self.course_info = loads(open("data.json").read())
        self.course_names: List[str] = get_current_course_names(self.course_info)
        self.course_ids: List[str] = get_current_course_id(self.course_info)
        self.height, self.width = stdscreen.getmaxyx()
        self.status_bar: StatusBar = None

        self.keybind_win = curses.newwin(self.height - 3, int(self.width * 0.3), 0, 0)
        self.keybind_panel = panel.new_panel(self.keybind_win)
        self.message_win = curses.newwin(self.height - 3, int(self.width * 0.3), 0, 0)
        self.message_panel = panel.new_panel(self.message_win)

        self.content_win = curses.newwin(self.height - 3, self.width, 0, 0)
        self.content_panel = panel.new_panel(self.content_win)
        self.content_panel.top()
        self.current_win_keybinds = []
        self.keybind_win.border()

        self.current_os = platform.system()

        panel.update_panels()
        curses.doupdate()

    @staticmethod
    def switch_win_callback(switch_to_statusbar: bool, statusbar: StatusBar, win: Any):
        if switch_to_statusbar:
            win.display()
            selected = statusbar.focus()
            statusbar.display()
            if selected:
                selected.run()
        else:
            statusbar.display()
            win.run()

    def set_keybind_help(self, binds: List[Tuple[str, str]]) -> None:
        self.keybinds = binds

    def display_binds(self, opts: Tuple[Any, Any] = (curses.A_NORMAL, curses.A_NORMAL)):
        """Display keybinds with self.keybind_panel"""
        Logger.info("Displaying keybinds")
        self.keybind_win.clear()
        rows = 1 + 2  # 2 for borders
        self.keybind_win.addstr(1, 1, "Keybinds")
        for index, keybind in enumerate(self.keybinds):
            self.keybind_win.addstr(
                index + 2, 2, keybind[0][: int(self.width * 0.3)], opts[0]
            )
            self.keybind_win.addstr(
                index + 2,
                len(keybind[0]) + 4,
                keybind[1][: int(self.width * 0.3) - len(keybind[0])],
                opts[1],
            )
            rows += 1
        self.keybind_win.resize(rows, self.height - 3)
        self.keybind_win.border()
        self.keybind_win.refresh()
        curses.curs_set(0)
        show_panel_hide_on_keypress(self.keybind_panel, self.keybind_win)
        curses.curs_set(1)

    def run(self) -> None:
        self.status_bar = StatusBar(
            self.course_names,
            self.height,
            self.width,
            self.course_ids,
            lambda course_id: CourseSubMenu(
                self.content_win,
                course_id,
                lambda win: self.switch_win_callback(True, self.status_bar, win),
                self.status_bar.gutter_mode,
                self.set_keybind_help,
            ),
            self.switch_win_callback,
            self.set_keybind_help,
            self.display_binds,
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
