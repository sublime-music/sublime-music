#! /usr/bin/env python3
import asyncio
import threading
import argparse
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio, Gtk

from .ui import MainWindow
from .server import Server


def main():
    server = Server(name='ohea',
                    hostname='https://airsonic.the-evans.family',
                    username=sys.argv[1],
                    password=sys.argv[2])

    win = MainWindow(server)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
