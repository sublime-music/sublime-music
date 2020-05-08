#! /usr/bin/env python

import re
import sys
from pathlib import Path

from termcolor import cprint

todo_re = re.compile(r"\s*#\s*TODO:?\s*")
accounted_for_todo = re.compile(r"\s*#\s*TODO:?\s*\((#\d+)\)")
print_re = re.compile(r"\s+print\(.*\)")


def noqa_re(error_id: str = ""):
    return re.compile(rf"#\s*noqa(:\s*{error_id})?\s*\n$")


def eprint(*strings):
    cprint(" ".join(strings), "red", end="", attrs=["bold"])


def check_file(path: Path) -> bool:
    print(f"Checking {path.absolute()}...")  # noqa: T001
    file = path.open()
    valid = True

    for i, line in enumerate(file, start=1):
        if todo_re.match(line) and not accounted_for_todo.match(line):
            eprint(f"{i}: {line}")
            valid = False

        if print_re.search(line) and not noqa_re("T001").search(line):
            eprint(f"{i}: {line}")
            valid = False

    file.close()
    return valid


valid = True
for path in Path("sublime").glob("**/*.py"):
    valid &= check_file(path)
    print()  # noqa: T001

sys.exit(0 if valid else 1)
