#! /usr/bin/env python

import re
import sys
from pathlib import Path

from termcolor import cprint

todo_re = re.compile(r'#\s*TODO:?\s*')
accounted_for_todo = re.compile(r'#\s*TODO:?\s*\((#\d+)\)')


def check_file(path: Path) -> bool:
    print(f'Checking {path.absolute()}...')  # noqa: T001
    file = path.open()
    valid = True

    for i, line in enumerate(file, start=1):
        if todo_re.search(line) and not accounted_for_todo.search(line):
            cprint(f'{i}: {line}', 'red', end='', attrs=['bold'])
            valid = False

    file.close()
    return valid


valid = True
for path in Path('sublime').glob('**/*.py'):
    valid &= check_file(path)
    print()  # noqa: T001

sys.exit(0 if valid else 1)
