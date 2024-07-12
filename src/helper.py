import logging
from curses import panel
from curses import window, doupdate
from re import sub
from html import unescape
from time import sleep

logging.basicConfig(level=logging.INFO, filename="log")
Logger = logging.getLogger("samplelogger")
Logger.info("Logging Has started")


def show_panel(a_panel: panel):
    a_panel.top()
    a_panel.show()
    panel.update_panels()


def hide_panel(a_panel, win: window):
    a_panel.bottom()
    a_panel.hide()
    panel.update_panels()
    win.clear()


def show_panel_hide_on_keypress(a_panel, win: window):
    a_panel.top()
    a_panel.show()
    panel.update_panels()
    doupdate()
    win.refresh()

    while True:
        if win.getch() != -1:
            a_panel.bottom()
            a_panel.hide()
            panel.update_panels()
            break


def clean_up_html(content: str):
    return sub("<[^<]+?>", "", unescape(content))
