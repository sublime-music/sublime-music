#! /usr/bin/env python3
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

    # print(server.ping())
    # print(server.get_license())
    print(server.get_music_folders())
    # print(server.get_indexes())
    # print()
    # print(server.get_music_directory(599))
    # print(server.get_genres())

    # win = MainWindow()
    # win.connect("destroy", Gtk.main_quit)
    # win.show_all()
    # Gtk.main()
