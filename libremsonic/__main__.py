#! /usr/bin/env python3
import argparse
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .ui import MainWindow


def main():
    win = MainWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
