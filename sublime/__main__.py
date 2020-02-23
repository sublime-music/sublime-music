#! /usr/bin/env python3
import argparse
import logging
import os

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa: F401

import sublime
from sublime.app import SublimeMusicApp


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
    parser.add_argument(
        '-c',
        '--config',
        help='specify a configuration file. Defaults to '
        '~/.config/sublime-music/config.json',
    )

    args, unknown_args = parser.parse_known_args()
    if args.version:
        print(f'Sublime Music v{sublime.__version__}')  # noqa: T001
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

    # Config File
    config_file = args.config
    if not config_file:
        # Default to ~/.config/sublime-music.
        config_folder = (
            os.environ.get('XDG_CONFIG_HOME') or os.environ.get('APPDATA')
            or os.path.join(os.environ.get('HOME'), '.config'))
        config_folder = os.path.join(config_folder, 'sublime-music')
        config_file = os.path.join(config_folder, 'config.json')

    app = SublimeMusicApp(config_file)
    app.run(unknown_args)
