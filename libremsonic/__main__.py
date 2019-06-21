#! /usr/bin/env python3
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from .app import LibremsonicApp
from .server import Server


def main():
    server = Server('ohea', 'https://airsonic.the-evans.family', 'sumner',
           'O}/UieSb[nzZ~l[X1S&zzX1Hi')

    print(server.get_license())
    # app = LibremsonicApp()
    # app.run(sys.argv)
