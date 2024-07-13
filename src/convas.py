#!/usr/bin/env python

# pyright: reportUnknownVariableType=false

import curses
import time
import os
import platform
import subprocess
from curses import panel
from inspect import getfullargspec
from json import loads, dumps
from typing import Any, Callable
from config import Config
from convas_requests import (
    download_file,
    get_current_course_id,
    get_current_course_names,
    get_discussions,
    get_course_info,
    get_assignments_request,
    get_announcements_request,
    get_files_request,
    get_quizzes_request,
)
from helper import (
    Logger,
    show_panel_hide_on_keypress,
    show_panel,
    hide_panel,
    clean_up_html,
)
import locale

import argparse

locale.setlocale(locale.LC_ALL, "")

HOME = os.path.expanduser("~")
CONFIG_FILE = "%s/.config/convas/config" % HOME
BORDER = 1
DEV = 1

try:
    with open(CONFIG_FILE) as file:
        config = Config()
        config.read_config(file)
except FileNotFoundError:
    print("Unable to read config file")
    exit()

if "config" not in globals():
    raise Exception("Unable to read config file")
    exit()

headers = {"Authorization": f"Bearer {config.get_token() if config else None}"}


class Menu(object):
    def __init__(self, _, stdscreen):
        self.window = stdscreen.subwin(0, 0)
        self.position = 0

    def navigate(self, _) -> None:
        raise NotImplementedError

    def display(self) -> None:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError


class CourseSubMenu(Menu):
    def __init__(
        self,
        cache_dir,
        window: Any,
        course_id: int,
        course_info: dict[str, str],
        switch_to_statusbar_callback: Callable[[Any], None],
        gutter_callback: Callable[[None], None],
        keybind_help: Callable[[list[tuple[str, str]]], None],
        notify: Callable[[str, str], bool],
    ):
        self.window = window
        self.course_info = course_info
        rows, cols = self.window.getmaxyx()
        self.cache_dir = cache_dir
        self.current_os = platform.system()
        self.window.scrollok(True)
        self.window.keypad(1)
        self.win_index = 2  # 2 = side_window, 3 = main_window
        self.tab_index = 0
        self.gutter_mode = gutter_callback
        self.set_keybind_help = keybind_help
        self.notify = notify
        self.tabs = [
            "Home",
            "Announcements",
            "Assignments",
            "Quizzes",
            "Files",
        ]
        self.announcements: list[dict[str, str]] | None = None
        self.quizzes: list[dict[str, str]] | None = None
        self.files: list[dict[str, str]] | None = None
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
        self.main_rerender = 0
        self.switch_to_statusbar_callback = switch_to_statusbar_callback

        def file_exists(filename: str) -> bool:
            return subprocess.run(["ls", filename]).returncode == 0

        self.assignments: list[dict[str, str]] = loads(
            (open(f"{self.cache_dir}assignments{course_id}.json").read())
        )

        if file_exists(f"{self.cache_dir}files{course_id}.json"):
            self.files: list[dict[str, str]] = loads(
                open(f"{self.cache_dir}files{course_id}.json").read()
            )
        if file_exists(f"{self.cache_dir}quizzes{course_id}.json"):
            self.quizzes: list[dict[str, str]] = loads(
                open(f"{self.cache_dir}quizzes{course_id}.json").read()
            )
        if file_exists(f"{self.cache_dir}announcements{course_id}.json"):
            self.announcements = loads(
                open(f"{self.cache_dir}announcements{course_id}.json").read()
            )

        if not isinstance(self.files, list):
            self.tabs.remove("Files")
        if not isinstance(self.quizzes, list):
            self.tabs.remove("Quizzes")
        if not isinstance(self.announcements, list):
            self.tabs.remove("Announcements")

        self.dashboard_win = self.window.subwin(
            rows, int(cols * 0.8), 0, int(cols * 0.2)
        )
        self.dashboard_panel = panel.new_panel(self.dashboard_win)

        def display_assignment_info(self):
            return None

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

    def initialize_dashboard(self):
        rows, cols = self.dashboard_win.getmaxyx()
        srows, scols = self.dashboard_win.getbegyx()

        self.dashboard_heading = self.dashboard_win.subwin(1, cols, srows + 1, scols)
        self.dashboard_course_info = self.dashboard_win.subwin(
            int(rows * 0.4) - 2, int(cols * 0.3), srows + 2, scols
        )
        self.dashboard_announcement = self.dashboard_win.subwin(
            int(rows * 0.6) + 1, int(cols * 0.3), srows + int(rows * 0.4), scols
        )
        self.upcoming_assignments = self.dashboard_win.subwin(
            int(rows * 0.6) + 1,
            int(cols * 0.35),
            srows + int(rows * 0.4),
            scols + int(cols * 0.3),
        )
        self.completed_assignments = self.dashboard_win.subwin(
            int(rows * 0.6) + 1,
            int(cols * 0.35),
            srows + int(rows * 0.4),
            scols + int(cols * 0.65),
        )

        syllabus = self.course_info["syllabus_body"]
        if syllabus:
            self.dashboard_syllabus = self.dashboard_win.subwin(
                int(rows * 0.4) - 2, int(cols * 0.7), srows + 2, scols + int(cols * 0.3)
            )
            self.dashboard_syllabus.border()
            self.wrap_content_around_win(
                "Syllabus\n" + clean_up_html(syllabus), self.dashboard_syllabus, True
            )
            self.dashboard_syllabus.refresh()
        else:  # if no syllabus, expand course_info
            self.dashboard_course_info.resize(int(rows * 0.4) - 2, cols)
            self.dashboard_course_info.border()

        title = ""
        msg = ""
        date = ""
        if self.announcements and len(self.announcements):
            latest_announcement = self.announcements[-1]
            msg = clean_up_html(latest_announcement["message"])
            title = latest_announcement["title"]
            date = latest_announcement["created_at"][:10]

        self.wrap_content_around_win(
            [
                "Latest Announcement\n",
                (f"Title: { title }") if title != "" else "No announcements",
                (f"Date: {date}") if len(date) else "",
                msg,
            ],
            self.dashboard_announcement,
            True,
        )

        upcoming_assignments = [""]
        completed_assignments = [""]
        if self.assignments and len(self.assignments):
            completed_assignments = [
                assignment["name"]
                for assignment in self.assignments
                if "submission" not in assignment.keys()
            ]
            upcoming_assignments = [
                assignment["name"]
                for assignment in self.assignments
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]
        self.wrap_content_around_win(
            ["Upcoming assignments", " "]
            + (
                upcoming_assignments
                if len(upcoming_assignments)
                else ["No upcoming assignments"]
            ),
            self.upcoming_assignments,
            True,
        )
        self.wrap_content_around_win(
            ["Completed assignments", " "]
            + (
                completed_assignments
                if len(completed_assignments)
                else ["No completed assignments"]
            ),
            self.completed_assignments,
            True,
        )

        course_full_name = self.course_info["name"]
        self.dashboard_heading.addstr(0, 1, f"{ course_full_name }")

        teacher = self.course_info["teachers"][0]["display_name"]
        started_at = self.course_info["term"]["start_at"][:10]
        score = str(
            list(
                filter(
                    lambda enrollment: enrollment["type"] == "student",
                    self.course_info["enrollments"],
                )
            )[0]["computed_current_score"]
        )
        course_info_content = [
            f"Started at: { started_at }",
            f"Instructor: { teacher }",
            f"Score: { score }",
            f"Course ID: {self.course_id}",
        ]
        self.wrap_content_around_win(course_info_content, self.dashboard_course_info)

        self.dashboard_announcement.border()
        self.completed_assignments.border()
        self.dashboard_course_info.border()
        self.upcoming_assignments.border()

        self.dashboard_heading.noutrefresh()
        self.dashboard_announcement.noutrefresh()
        self.completed_assignments.noutrefresh()
        self.upcoming_assignments.noutrefresh()
        self.dashboard_win.refresh()

    def display(self):
        """Print the side_window to the screen"""
        self.side_window.erase()
        self.side_window.border()
        for index, item in enumerate(self.tabs):
            msg = "%s" % (item)
            self.side_window.addstr(1 + index, 1, msg, curses.A_NORMAL)
        self.side_window.refresh()
        self.initialize_dashboard()

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
        right_side_str: list[str, str] | None = None
        left_side_str: list[str, str] | None = None
        right_offset: list[str, str] | None = None
        rows, cols = self.main_win.getmaxyx()
        if entry == "assignments":
            max_rows = rows - 2
            left_side_str = [["Assignment Name", ""]] + [
                (
                    [assignment["name"], ""]
                    if len(assignment["name"]) < 30
                    else [assignment["name"][:30] + "...", ""]
                )
                for assignment in self.assignments
            ]
            right_side_str = [["Points   Created at", ""]]

            for assignment in self.assignments:
                if ("submission" in assignment.keys()) and assignment["submission"][
                    "submitted_at"
                ] != 0:
                    points = (
                        f"{assignment['submission']['score']}{assignment['points_possible']}",
                    )
                else:
                    points = f"{assignment['points_possible']}"
                right_side_str += [[f"{points}   {assignment['created_at'][:10]}", ""]]
                right_offset = [
                    [(cols - len(str(right_str[0])) - 3), 0]
                    for right_str in right_side_str
                ]
            rows_per_item = 2
            self.main_win_end = min(
                (len(left_side_str) - self.main_win_start),
                (max_rows - rows_per_item) // rows_per_item,
            )

        elif entry == "home":
            # TODO: change initalize_dashboard to just be show_hide
            hide_panel(self.main_win_panel, self.main_win)
            self.initialize_dashboard()
            show_panel(self.main_win_panel)
            return
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
                [assignment["name"], assignment["submission"]["submitted_at"][:10], ""]
                for assignment in self.assignments
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != 0
            ]
            right_side_str = [
                [
                    f"{assignment['points_possible']}/ {assignment['submission']['score']}",
                    "",
                    "",
                ]
                for assignment in self.assignments
                if ("submission" in assignment.keys())
                and assignment["submission"]["submitted_at"] != -1
            ]
            right_offset = [
                [(cols - len(str(right_str)) - 3), 0, 0] for right_str in right_side_str
            ]
            rows_per_item = 3

        elif entry == "quizzes":
            left_side_str = [["Quiz name", ""]] + [
                [quiz["title"][0:20], ""] for quiz in self.quizzes
            ]
            right_side_str = [["Date created", ""]] + [
                [f"{quiz['due_at'][:10]}", ""] for quiz in self.quizzes
            ]
            right_offset = [
                [(cols - len(str(right_str)) - 3), 0] for right_str in right_side_str
            ]
            rows_per_item = 2

        elif entry == "files":
            left_side_str = [["Filename", ""]] + [
                [file["display_name"][:30], ""] for file in self.files
            ]
            right_side_str = [["filetype  " + "created_at", ""]] + [
                [f"{file['mime_class']}  {file['updated_at'][:10]} ", ""]
                for file in self.files
            ]
            right_offset = [
                [(cols - len(str(right_str[0])) - 3), 0] for right_str in right_side_str
            ]
            rows_per_item = 2

        if not left_side_str:
            return
        self.main_win.erase()
        self.main_win.border()

        max_rows = rows - 2
        self.main_win_end = min(
            (len(left_side_str) - self.main_win_start),
            (max_rows - rows_per_item) // rows_per_item,
        )
        for index, item in enumerate(
            left_side_str[self.main_win_start : self.main_win_end]
        ):
            if isinstance(item, str):
                if item != "":
                    self.main_win.addstr(1 + index, 1, item)
                else:
                    self.main_win.hline(index + 1, 1, curses.ACS_HLINE, cols - 2)
            else:
                for i in range(len(item)):
                    if item[i] != "":
                        self.main_win.addstr(rows_per_item * index + i + 1, 1, item[i])
                    else:
                        self.main_win.hline(
                            rows_per_item * index + i + 1, 1, curses.ACS_HLINE, cols - 2
                        )
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
                    for i in range(len(item)):
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

    def open_url(self, current_os: str, url: str):
        if current_os == "Linux":
            cmd = ("xdg-open %s" % (url),)
        elif current_os == "Windows":
            cmd = ("start msedge %s" % (url),)
        elif current_os == "darwin":
            cmd = ("open %s" % (url),)
        else:
            # I'm guessing you're probably using firefox on a BSD
            for path in ["/usr/bin", "/usr/local/bin"]:
                if os.path.exists(os.path.join(path, "firefox")):
                    cmd = ("firefox %s" % (url),)
                else:
                    self.notify("No browser found")
        subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def wrap_content_around_win(
        self, content: str | list[str], win: Any, is_header=False
    ):
        h, w = win.getmaxyx()
        Logger.info(f" {h} {w}")
        linenm = 1
        bolden = curses.A_BOLD if is_header else curses.A_NORMAL
        if isinstance(content, list):
            for row in content:
                row = clean_up_html(row)
                row = row.replace("\n", "")
                lines = (len(row) + w + BORDER * 2 - 1) // w
                start = 0
                end = w - 2
                for line in range(lines):
                    if linenm + line == h:
                        return
                    win.addstr(linenm, 1, row[start:end], bolden)
                    bolden = curses.A_NORMAL

                    linenm += 1
                    start = end
                    end += w - BORDER
        elif isinstance(content, str):
            content = clean_up_html(content)
            lines = (len(content) + w + BORDER * 2 - 1) // w
            start = 0
            end = w - BORDER * 2
            for line in range(lines):
                Logger.info(lines)
                if linenm == h - 2:
                    return
                try:
                    win.addstr(linenm + line, 1, content[start : end + 1], bolden)
                    bolden = curses.A_NORMAL
                except curses.error:
                    win.border()
                start = end
                end += w - BORDER * 2
        win.noutrefresh()

    def main_win_panel_render(self, content: str | list[str]):
        """Display a panel over the main window with custom content"""
        self.main_win_panel.hide()
        self.main_win_popup.erase()
        self.main_win_popup.border()
        h, w = self.main_win_popup.getmaxyx()
        if isinstance(content, list):
            for row in content:
                lines = (len(row) + w + 2 - 1) // w
                s = 0
                e = w - 2
                for line in range(lines):
                    self.main_win_popup.addstr(line + 1, 1, row[s:e])
                    s = e
                    e += w - 2
        elif isinstance(content, str):
            lines = (len(content) + w + 2 - 1) // w
            s = 0
            e = w - 2
            for line in range(lines):
                self.main_win_popup.addstr(line + 1, 1, content[s:e])
                s = e
                e += w - 2
        self.main_win_popup.refresh()
        show_panel_hide_on_keypress(self.main_win_popup_panel, self.main_win)

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
            left_side_str: list[str] | list[list[str]],
            bindings: list[tuple[int, Callable[[None], Any] | Callable[str, Any], str]],
            right_side_str: list[str] | None = None,
            right_offset: int | None = None,
            args: list[str] | None = None,
        ):
            self.main_rerender = 1
            has_right = right_side_str is not None

            def rerender_main_win():
                self.main_win.border()
                for index in range(self.main_win_start, self.main_win_end):
                    left = left_side_str[index]
                    right = right_side_str[index] if has_right else None
                    offset = right_offset[index] if has_right else None
                    if isinstance(left, str):
                        self.main_win.addstr(1 + index, 1, left[index])
                        self.main_win.addstr(
                            1 + index * rows_per_item,
                            (offset if offset is not None else 1),
                            left[index],
                        )
                    else:
                        for i in range(rows_per_item):
                            if left[i] != "":
                                self.main_win.addstr(
                                    rows_per_item * (index - self.main_win_start)
                                    + i
                                    + 1,
                                    1,
                                    left[i],
                                )
                            else:
                                self.main_win.hline(
                                    rows_per_item * (index - self.main_win_start)
                                    + i
                                    + 1,
                                    1,
                                    curses.ACS_HLINE,
                                    cols - 2,
                                )
                            if has_right:
                                self.main_win.addstr(
                                    1
                                    + rows_per_item * (index - self.main_win_start)
                                    + i,
                                    (offset[i] if offset is not None else 1),
                                    right[i] if right else "",
                                )
                return 0  # return 0 to stop rerendering all entries again

            while True:
                if self.main_rerender:
                    self.main_win.erase()
                    self.main_rerender = rerender_main_win()
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
                    left = left_side_str[index]
                    right = right_side_str[index] if has_right else ""
                    offset = right_offset[index] if has_right else 1
                    if isinstance(left, str):
                        self.main_win.addstr(1 + index, 1, left, mode)
                        self.main_win.addstr(
                            1 + index * rows_per_item,
                            (offset),
                            right,
                            mode,
                        )
                    else:
                        for i in range(rows_per_item):
                            self.main_win.addstr(
                                rows_per_item * (index - self.main_win_start) + i + 1,
                                1,
                                left[i],
                                mode,
                            )
                            if has_right:
                                self.main_win.addstr(
                                    1
                                    + rows_per_item * (index - self.main_win_start)
                                    + i,
                                    (offset[i] if offset is not None else 1),
                                    right[i],
                                    mode,
                                )

                self.main_win.refresh()
                key = self.main_win.getch()

                if key == ord("h"):
                    self.main_win_render = 1
                    self.main_win_start = 0
                    self.main_win_end = 0
                    break
                elif key == ord(":"):
                    self.gutter_mode()

                for binding in bindings:
                    if key == binding[0]:
                        callback_signature_args = getfullargspec(binding[1]).args
                        if callback_signature_args == []:
                            binding[1]()
                            self.main_rerender = 1
                        elif (
                            len(callback_signature_args) == 1
                            and callback_signature_args[0] == "url"
                        ):
                            binding[1](args[self.position])
                            self.main_rerender = 0

        entry = self.tabs[self.tab_index].lower()
        rows_per_item = 1
        rows, cols = self.main_win.getmaxyx()

        if entry == "assignments":

            def navigate(n: int):
                if (
                    self.position + n <= self.main_win_end - 1
                    and self.position + n >= self.main_win_start + 1
                ):
                    self.position += n
                elif self.position + n > len(self.assignments) + 1:
                    return
                elif self.main_win_start + 1 > self.position + n:
                    if self.main_win_start + n >= 0:
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1
                elif self.position + n > self.main_win_start + 1:
                    if (
                        self.main_win_start + n + self.position
                        < len(self.assignments) + 1
                    ):
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1

            left_side_str = [["Assignment Name", ""]] + [
                (
                    [assignment["name"], ""]
                    if len(assignment["name"]) < 30
                    else [assignment["name"][:30] + "...", ""]
                )
                for assignment in self.assignments
            ]
            right_side_str = [["Points   Created at", ""]]

            for assignment in self.assignments:
                if ("submission" in assignment.keys()) and assignment["submission"][
                    "submitted_at"
                ] != 0:
                    points = (
                        f"{assignment['submission']['score']}{assignment['points_possible']}",
                    )
                else:
                    points = f"{assignment['points_possible']}"
                right_side_str += [[f"{points}   {assignment['created_at'][:10]}", ""]]
                right_offset = [
                    [(cols - len(str(right_str[0])) - 3), 0]
                    for right_str in right_side_str
                ]
            rows_per_item = 2
            max_rows = rows - 2

            self.main_win_end = min(
                (len(left_side_str) - self.main_win_start),
                (max_rows - rows_per_item) // rows_per_item,
            )
            self.position = 1
            main_win_loop(
                left_side_str,
                [
                    (ord("j"), lambda: navigate(1)),
                    (ord("k"), lambda: navigate(-1)),
                    (
                        ord("o"),
                        lambda: self.open_url(
                            self.current_os,
                            self.assignments[self.main_win_start + self.position][
                                "html_url"
                            ],
                        ),
                    ),
                ],
                right_side_str,
                right_offset,
            )

        elif entry == "announcements":

            def navigate(n: int) -> bool:
                if (
                    self.position + n <= self.main_win_end - 1
                    and self.position + n >= self.main_win_start
                ):
                    self.position += n
                elif (
                    self.position + n + self.main_win_start
                    > len(self.announcements) - 1
                ):
                    return
                elif self.main_win_start > self.position + n:
                    if self.main_win_start + n >= 0:
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1
                elif self.position + n > self.main_win_start:
                    if self.main_win_start + n + self.position < len(
                        self.announcements
                    ):
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1

            def show_annoucement(id: int):
                message = [
                    clean_up_html(anouncement["message"])
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
            self.main_win_end = ( min((len(left_side_str[self.main_win_start :])), (max_rows - rows_per_item) // rows_per_item,) )

            # fmt: on
            main_win_loop(
                left_side_str,
                [
                    (
                        ord("j"),
                        lambda: navigate(1),
                    ),
                    (ord("k"), lambda: navigate(-1)),
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

        elif entry == "quizzes":

            def navigate(n: int):
                if (
                    self.position + n <= self.main_win_end - 1
                    and self.position + n >= self.main_win_start + 1
                ):
                    self.position += n
                elif self.position + n > len(self.quizzes) + 1:
                    return
                elif self.main_win_start + 1 > self.position + n:
                    if self.main_win_start + n >= 0:
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1
                elif self.position + n > self.main_win_start + 1:
                    if self.main_win_start + n + self.position < len(self.quizzes) + 1:
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1

            left_side_str = [["Quiz name", ""]] + [
                [quiz["title"][0:30], ""] for quiz in self.quizzes
            ]
            right_side_str = [["Date created", ""]] + [
                [f"{quiz['due_at'][:10]}", ""] for quiz in self.quizzes
            ]
            right_offset = [
                [(cols - len(str(right_str)) - 3), 0] for right_str in right_side_str
            ]
            max_rows = rows - 2

            rows_per_item = 2
            self.position = 1
            self.main_win_start = 0
            self.main_win_end = min(
                (len(left_side_str[self.main_win_start :])),
                (max_rows - rows_per_item) // rows_per_item,
            )
            main_win_loop(
                left_side_str,
                [
                    (
                        ord("j"),
                        lambda: navigate(1),
                    ),
                    (
                        ord("k"),
                        lambda: navigate(-1),
                    ),
                    (
                        ord("o"),
                        lambda: self.open_url(
                            self.current_os,
                            self.quizzes[self.main_win_start + self.position][
                                "html_url"
                            ],
                        ),
                    ),
                ],
                right_side_str,
                right_offset,
            )

        elif entry == "files":

            def navigate(n: int):
                if (
                    self.position + n <= self.main_win_end - 1
                    and self.position + n >= self.main_win_start + 1
                ):
                    self.position += n
                elif self.position + n > len(self.files) + 1:
                    return
                elif self.main_win_start + 1 > self.position + n:
                    if self.main_win_start + n >= 0:
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1
                elif self.position + n > self.main_win_start + 1:
                    if self.main_win_start + n + self.position < len(self.files) + 1:
                        self.main_win_start += n
                        self.position += n
                        self.main_win_end += n
                        self.main_rerender = 1

            left_side_str = [["Filename", ""]] + [
                [file["display_name"][:30], ""] for file in self.files
            ]
            right_side_str = [["filetype  " + "created_at", ""]] + [
                [f"{file['mime_class']}  {file['updated_at'][:10]} ", ""]
                for file in self.files
            ]
            right_offset = [
                [(cols - len(str(right_str[0])) - 3), 0] for right_str in right_side_str
            ]
            rows_per_item = 2

            def download_file_at_cursor(
                current_os: str, url: str, file_id: str, name: str
            ):
                if current_os == "Linux":
                    download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
                elif current_os == "Windows":
                    download_dir = os.path.join(os.environ["USERPROFILE"], "Downloads")
                elif current_os == "darwin":
                    download_dir = os.path.expanduser("~/Downloads")
                else:
                    download_dir = os.path.expanduser("~/Downloads")
                file_path = os.path.join(download_dir, name)
                download = download_file(
                    url,
                    file_id,
                    course_id=self.course_id,
                    outfile=file_path,
                    headers={},
                )
                if not download:
                    self.notify("Error: ", "file not downloaded")
                    return None
                self.notify("Downloaded", f"{name} downloaded to {download_dir}")

            max_rows = rows - 2
            self.main_win_end = min(
                (len(left_side_str[self.main_win_start :])),
                (max_rows - rows_per_item) // rows_per_item,
            )
            self.position = 1

            main_win_loop(
                left_side_str,
                [
                    (ord("j"), lambda: navigate(1), "down"),
                    (ord("k"), lambda: navigate(-1), "up"),
                    (
                        ord("d"),
                        lambda: download_file_at_cursor(
                            self.current_os,
                            self.files[self.position]["url"],
                            self.files[self.position]["id"],
                            self.files[self.position]["display_name"],
                        ),
                        "down",
                    ),
                ],
                right_side_str,
                right_offset,
            )

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


class StatusBar(Menu):
    def __init__(
        self,
        courses: list[str],
        height: int,
        width: int,
        course_ids: list[str],
        update_callback: Callable[int, None],
        change_win_callback: Callable[Any, None],
        set_keybind_help: Callable[list[tuple[str, str]], None],
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
            "help": lambda: None,
            "h": lambda: None,
            "quit": lambda: None,
            "q": lambda: None,
        }
        self.set_keybind_help = set_keybind_help

    def add_cmd(self, cmd: str, callback: Callable[None, None], alias="") -> None:
        self.cmds[cmd] = callback
        if alias != "":
            self.cmds[alias] = callback

    def navigate(self, n: int) -> None:
        self.position += n
        if self.position < 0:
            self.position = 0
        elif self.position >= len(self.courses):
            self.position = len(self.courses) - 1

    def display(self) -> None:
        self.window.erase()
        self.window.border()
        status_offset = 1
        for index, course in enumerate(self.courses):
            status_offset += 2
            msg = "%d.%s " % (index, course[0])
            self.window.addstr(1, status_offset + index, msg, curses.A_NORMAL)
            self.window.addstr(1, status_offset + index + 3, "")
            status_offset += len(course[0])
        self.window.noutrefresh()

    def run(self) -> CourseSubMenu | Menu:
        self.window.scrollok(True)
        return self.focus()

    def focus(self) -> CourseSubMenu | Menu:
        self.set_keybind_help([("j", "next"), ("k", "prev"), (":", "cmd mode")])
        while True:
            left_offset = 3
            self.window.erase()
            self.window.border()
            for index, course in enumerate(self.courses):
                mode = curses.A_REVERSE if index == self.position else curses.A_NORMAL
                msg = "%d.%s" % (index, course[0])
                self.window.addstr(1, left_offset + index, msg + " " * 2, mode)
                left_offset += len(course[0]) + 2
            self.window.refresh()
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
    def eval_command(cmds: dict[str, Callable[None, None]], cmd: str) -> bool:
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
        curses.curs_set(1)
        buffer = ""
        cursor = 1
        self.window.erase()
        self.window.border()
        while True:
            self.window.addstr(1, 1, buffer)
            self.window.refresh()
            key = self.window.getch()
            if chr(key).isalpha():
                buffer = buffer[:cursor] + chr(key) + buffer[cursor:]
                cursor += 1
            elif key == curses.KEY_BACKSPACE or key == 127:
                buffer = buffer[:-1]
                cursor = max(1, cursor - 1)
                self.window.erase()
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
                curses.curs_set(0)
                return ""
            elif key == ord("\n"):
                if self.validate(buffer):
                    curses.curs_set(0)
                    return buffer


class Convas(object):
    def __init__(self, stdscreen, install: bool = False, reload: bool = False):
        self.current_os = platform.system()
        self.cache_dir = None
        self.get_cache_dir()
        self.url = "https://canvas.umd.umich.edu/api/v1/courses"
        self.screen = stdscreen
        self.make_api_calls(
            get_courses=install,
            get_announcements=install or reload,
            get_assignments=install or reload,
            get_files=install or reload,
            get_quizzes=install or reload,
        )
        self.course_info = loads(open(f"{self.cache_dir}courses.json").read())
        self.course_names: list[str] = get_current_course_names(self.course_info)
        self.course_ids: list[str] = get_current_course_id(self.course_info)
        height, width = stdscreen.getmaxyx()
        self.height = height
        self.width = width
        self.status_bar: StatusBar = None

        self.keybind_win = curses.newwin(self.height - 3, int(self.width * 0.3), 0, 0)
        self.keybind_panel = panel.new_panel(self.keybind_win)
        self.notify_win = curses.newwin(5, int(self.width * 0.3), 0, 0)
        self.notify_panel = panel.new_panel(self.notify_win)

        self.content_win = curses.newwin(self.height - 3, self.width, 0, 0)
        self.content_panel = panel.new_panel(self.content_win)
        self.content_panel.top()
        self.current_win_keybinds = []
        self.keybind_win.border()

        panel.update_panels()
        curses.doupdate()

    def get_cache_dir(self):
        home = os.path.expanduser("~")
        try:
            if self.current_os == "Linux":
                cache_dir = os.path.join(home, ".cache/convas")
            elif self.current_os == "Windows":
                cache_dir = os.path.join(home, "AppData", "Local", "Cache")
            elif self.current_os == "darwin":
                cache_dir = os.path.join(home, "Library", "Caches")
            else:
                cache_dir = os.path.expanduser("~/.cache")
        except Exception as e:
            print(f"Error getting cache directory: {e}")
            exit()

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        self.cache_dir = cache_dir + "/"

    def make_api_calls(
        self,
        get_courses=False,
        get_assignments=False,
        get_announcements=False,
        get_files=False,
        get_quizzes=False,
    ):
        """Method to make all api calls and cache them"""
        domain = config.get_domain()

        def write_json_to_file(filename: str, json_obj: dict[str, str]):
            with open(filename, "w") as file:
                file.write(dumps(json_obj))

        # if the file already exists, then don't write till the user force reloads
        if not os.path.isfile(f"{self.cache_dir}courses.json") or get_courses:
            courses_info = get_course_info(f"{domain}api/v1/courses", headers)
            write_json_to_file(f"{self.cache_dir}courses.json", courses_info)
        else:
            courses_info = loads(open(f"{self.cache_dir}courses.json").read())

        course_ids: list[str] = get_current_course_id(courses_info)
        if get_assignments:
            for id in course_ids:
                assignments = get_assignments_request(f"{domain}api/v1", headers, id)
                write_json_to_file(f"{self.cache_dir}assignments{id}.json", assignments)

        start_date = courses_info[-1]["term"]["start_at"][:10]
        if get_announcements:
            announcements: list[dict[str, str]] = get_announcements_request(
                f"{domain}/api/v1", headers, course_ids, start_date
            )
            for id in course_ids:
                announcement = [
                    announcement
                    for announcement in announcements
                    if announcement["context_code"][7:] == str(id)
                ]  # context_code:  "course_<id>"
                write_json_to_file(
                    f"{self.cache_dir}announcements{id}.json", announcement
                )
        if get_files:
            for course_id in course_ids:
                files: list[dict[str, str]] = get_files_request(
                    f"{domain}/api/v1", headers, course_id
                )
                write_json_to_file(f"{self.cache_dir}files{course_id}.json", files)

        if get_quizzes:
            for course_id in course_ids:
                quizzes: list[dict[str, str]] = get_quizzes_request(
                    f"{domain}/api/v1", headers, course_id
                )
                write_json_to_file(f"{self.cache_dir}quizzes{course_id}.json", quizzes)

    @staticmethod
    def switch_win_callback(switch_to_statusbar: bool, statusbar: StatusBar, win: Any):
        # both win and statusbar have two virtual methods, display and run
        # win.display will display the content of the window without focusing on it
        # win.run will focus on the window and run the selection loop
        # use win.focus if win.run has already been called
        if switch_to_statusbar:
            win.display()
            selected = statusbar.focus()
            statusbar.display()
            if selected:
                selected.run()
        else:
            statusbar.display()
            win.run()

    def set_keybind_help(self, binds: list[tuple[str, str]]) -> None:
        self.keybinds = binds

    def display_binds(self, opts: tuple[Any, Any] = (curses.A_NORMAL, curses.A_NORMAL)):
        """Display keybinds with self.keybind_panel"""
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
        show_panel_hide_on_keypress(self.keybind_panel, self.keybind_win)

    def notify(
        self,
        heading: str,
        msg: str = "",
        opts: tuple[Any, Any] = (curses.A_BOLD, curses.A_NORMAL),
    ) -> bool:
        self.notify_win.clear()
        self.notify_win.border()
        _, w = self.notify_win.getmaxyx()
        cur = 1
        row = 1
        heading_words = heading.split(" ")
        msg_words = msg.split(" ")

        for word in heading_words:
            if cur + len(word) + 1 < w:
                self.notify_win.addstr(row, cur, word + " ")
                cur += len(word) + 1
            elif row < 3:
                cur = 1
                row += 1
            else:
                self.notify_win.addstr(row, w - 4, "...")

        cur = 1
        row += 1
        for word in msg_words:
            if cur + len(word) + 1 < w:
                self.notify_win.addstr(row, cur, word + " ")
                cur += len(word) + 1
            elif row < 6:
                cur = 1
                row += 1
            else:
                self.notify_win.addstr(row, w - 4, "...")

        self.notify_win.border()
        self.notify_win.refresh()
        show_panel_hide_on_keypress(self.notify_panel, self.notify_win)

        return True

    def install(self):
        """call all api calls and cache them"""
        self.notify("Install", "sent install request", opts=(curses.A_BOLD))
        start = time.time()
        self.make_api_calls(True, True, True, True, True)
        end = time.time()
        elapsed = start - end
        self.course_info = loads(open(f"{self.cache_dir}courses.json").read())
        self.course_names: list[str] = get_current_course_names(self.course_info)
        self.course_ids: list[str] = get_current_course_id(self.course_info)
        self.notify(
            "Install",
            "All data has been cached in %s seconds" % elapsed,
            opts=(curses.A_BOLD, curses.A_NORMAL),
        )
        self.run()

    def reload(self):
        self.notify("Reload", "sent reload request", opts=(curses.A_BOLD))
        start = time.time()
        self.make_api_calls(False, True, True, True, True)
        end = time.time()
        elapsed = start - end
        self.window.clear()
        self.notify(
            "Reload",
            "All data has been reloaded in %s seconds" % elapsed,
            opts=(curses.A_BOLD),
        )
        self.run()

    def run(self) -> None:
        curses.curs_set(0)
        self.status_bar = StatusBar(
            self.course_names,
            self.height,
            self.width,
            self.course_ids,
            lambda course_id: CourseSubMenu(
                self.cache_dir,
                self.content_win,
                course_id,
                [course for course in self.course_info if course["id"] == course_id][0],
                lambda win: self.switch_win_callback(True, self.status_bar, win),
                self.status_bar.gutter_mode,
                self.set_keybind_help,
                self.notify,
            ),
            self.switch_win_callback,
            self.set_keybind_help,
        )
        self.status_bar.add_cmd("quit", exit, alias="q")
        self.status_bar.add_cmd(
            "help",
            lambda: self.display_binds(curses.A_BOLD, curses.A_NORMAL),
            alias="h",
        )
        self.status_bar.add_cmd("install", self.install)
        self.status_bar.add_cmd("reload", self.reload)

        splash = r"""
        Convas - The CONsole client for canVAS

        type    :help<CR>    for keybind help
        type    :install<CR> to cache all courses (one time)
        type    :reload<CR> to reload all course information
        """

        try:
            Logger.info(f"Convas initialized with {self.height}x{self.width}")
            y_position = (self.height - 3 * 6) // 2
            x_position = (
                self.width // 2
                - int(max(len(line) for line in splash.split("\n"))) // 2
            )
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install",
        "-i",
        action="store_true",
        help="Run once at the start of the semester to cache courses",
    )
    parser.add_argument(
        "--reload",
        "-r",
        action="store_true",
        help="Reload all course data",
    )
    args = parser.parse_args()
    curses.use_default_colors()
    convas = Convas(stdscr, install=args.install, reload=args.reload)
    convas.run()


if __name__ == "__main__":
    curses.wrapper(main)
