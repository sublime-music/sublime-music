#! /usr/bin/env python3
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .app import LibremsonicApp


def main():
    app = LibremsonicApp()
    app.run(sys.argv)
