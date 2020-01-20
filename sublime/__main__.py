#! /usr/bin/env python3
import argparse
import logging

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: F401

import sublime
from .app import SublimeMusicApp


def main():
    parser = argparse.ArgumentParser(description='Sublime Music')
    parser.add_argument(
        '-v',
        '--version',
        help='show version and exit',
        action='store_true',
    )
    parser.add_argument(
        '-l',
        '--logfile',
        help='the filename to send logs to',
    )
    parser.add_argument(
        '-m',
        '--loglevel',
        help='the minium level of logging to do',
        default='WARNING',
    )

    args, unknown_args = parser.parse_known_args()
    if args.version:
        print(f'Sublime Music v{sublime.__version__}')
        return

    min_log_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(min_log_level, int):
        logging.error(f'Invalid log level: {args.loglevel.upper()}.')
        min_log_level = logging.WARNING

    logging.basicConfig(
        filename=args.logfile,
        level=min_log_level,
        format='%(asctime)s:%(levelname)s:%(name)s:%(module)s:%(message)s',
    )

    app = SublimeMusicApp()
    app.run(unknown_args)
