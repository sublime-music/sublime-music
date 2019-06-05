#! /usr/bin/env python3
import threading
import argparse
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio, Gtk

from .ui import LibremsonicApp


def main():
    app = LibremsonicApp()
    app.run(sys.argv)
