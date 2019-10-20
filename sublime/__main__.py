#! /usr/bin/env python3
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: F401

from .app import SublimeMusicApp


def main():
    app = SublimeMusicApp()
    app.run(sys.argv)
