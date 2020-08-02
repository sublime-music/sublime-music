from pathlib import Path
from typing import Union


def resolve_path(*joinpath_args: Union[str, Path]) -> Path:
    roots = (Path(__file__).parent, Path("/usr/share/sublime-music"))
    for root in roots:
        if (fullpath := root.joinpath(*joinpath_args).resolve()).exists():
            return fullpath

    raise FileNotFoundError(
        f"{Path(*joinpath_args)} could not be found in any of the following "
        "directories: {', '.join(roots)}"
    )
