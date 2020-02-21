#! /usr/bin/env python

import sys
import re

from pathlib import Path

from termcolor import cprint

print_re = re.compile(r'print\(.*\)')
todo_re = re.compile(r'#\s*TODO:?\s*')
accounted_for_todo = re.compile(r'#\s*TODO:?\s*\((#\d+)\)')


def check_file(path):
    print(f'Checking {path.absolute()}...')
    file = path.open()
    valid = True

    for i, line in enumerate(file, start=1):
        if print_re.search(line) and '# allowprint' not in line:
            cprint(f'{i}: {line}', 'red', end='', attrs=['bold'])
            valid = False

        if todo_re.search(line) and not accounted_for_todo.search(line):
            cprint(f'{i}: {line}', 'red', end='', attrs=['bold'])
            valid = False

    file.close()
    return valid


valid = True
for path in Path('sublime').glob('**/*.py'):
    valid &= check_file(path)
    print()

sys.exit(0 if valid else 1)
