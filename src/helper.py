import logging
from curses import panel 

logging.basicConfig(level=logging.INFO, filename="log")
Logger = logging.getLogger("samplelogger")
Logger.info("Logging Has started")

def show_panel(a_panel): 
    a_panel.top()
    a_panel.show()
    panel.update_panels()

def hide_panel(a_panel, win):
    a_panel.bottom()
    a_panel.hide()
    panel.update_panels()
    win.clear() 

def show_panel_hide_on_keypress(a_panel, win): 
    a_panel.top()
    a_panel.show()
    panel.update_panels()
    if win.getch() != -1:
        hide_panel(a_panel, win)
