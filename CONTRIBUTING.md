# Contributing

Contributions are welcome! You can engage with the project in many ways:

* GitHub: [create an issue][ghissues] or [submit a PR][ghpr] on [GitHub][gh].
* Matrix: join our [Matrix chat][matrix].

## Issue Reporting

You can report issues or propose features by creating an [issue on
GitHub][ghissues].

*Please note that as of right now, I (Sumner) am basically the only contributor
to this project, so my response time to your issue may be anywhere from instant
to infinite.*

When reporting a bug, please be as specific as possible, and include steps to
reproduce. Additionally, you can run Sublime Music with the `-m` flag to
enable logging at different levels. For the most verbose logging, run Sublime
Music with `debug` level logging:
```
sublime-music -m debug
```

Using `info` level logging may also suffice.

## Code

If you want to propose a code change, please submit a [pull request][ghpr]. If
it is good, I will merge it in.

To get an overview of the Sublime Music code structure, I recommend taking a
look at the [`sublime_music` package
documentation](https://docs.sublimemusic.app/api/sublime_music.html).

### Requirements

**WIP:** Please create an PR with any other dependencies that you had to install
to develop the app. In general, the requirements are:

- Python 3.10 (I recommend you install this via [Pyenv][pyenv])
- GTK3
- GLib
- libmpv

#### Specific Requirements for Various Distros/OSes

* **NixOS:** use the `shell.nix` (optionally with direnv)
* **Arch Linux:** `pacman -S libnm-glib libnotify python-gobject gobject-introspection`
* **macOS (Homebrew):** `brew install mp3 gobject-introspection pkg-config pygobject3 gtk+3 adwaita-icon-theme`

### Dependency Management

This project uses [pip-tools][] and [flit][] to manage dependences for both the
core package as well as for development. You only need to install `pip-tools` or
`flit` if you want to change any of the project's dependencies.

### Installation

It is recommended to develop within a virtual environment. See [the docs for
setting up a virtual
environment](https://docs.python.org/3/library/venv.html#creating-virtual-environments)

Then, after activating your virtual environment, run:
```
$ pip install -r all-requirements.txt
$ pip install -e .
```
to install the development dependencies as well as install `sublime-music` into
the virtual environment as editable.

### Running

Run:
```
$ sublime-music
```
to launch the application.

### Code Style

This project follows [black][] strictly. The *only* exception is maximum line
length, which is 99 for this project (in accordance with `black`'s defaults).
Lines that contain a single string literal are allowed to extend past the
maximum line length limit.

This project uses [flake8][], [isort][], [mypy][], and [black][] to do static
analysis of the code and to enforce a consistent (and as deterministic as
possible) code style.

The linting checks are enforced at commit-time using [pre-commit][]. The
pre-commit hooks can be installed using:
```
$ pre-commit install --install-hooks
```

Although you can technically do all of the formatting yourself, it is
recommended that you use the following tools (they are included in
`all-requirements.txt`). The pre-commit hooks and CI process uses these to check
all commits, so you will probably want these so you don't have to wait for
results of the build before knowing if your code is the correct style.

* [`flake8`][flake8] is used for linting. The following
  additional plugins are also used:

  * `flake8-annotations`: enforce type annotations on function definitions.
  * `flake8-bugbear`: enforce a bunch of fairly opinionated styles.
  * `flake8-comprehensions`: enforce usage of comprehensions wherever possible.
  * `flake8-pep3101`: no `%` string formatting.
  * `flake8-print`: to prevent using the `print` function. The more powerful
    `logging` should be used instead. In the rare case that you actually want to
    print to the terminal (the `--version` flag for example), then just disable
    this check with a `# noqa` or a `# noqa: T001` comment.

* [`isort`][isort] is used to sort the imports consistently.

* [`mypy`][mypy] is used for type checking. All type errors must be resolved.

* [`black`][black] is used for auto-formatting. The CI process runs `black
  --check` to make sure that you've run `black` on all files (or are just good
  at manually formatting).

* `TODO` statements must include an associated issue number (in other words, if
  you want to check in a change with outstanding TODOs, there must be an issue
  associated with it to fix it).

The CI process runs all of the above checks on the code. You can run the same
checks that the lint job runs yourself with the following commands:
```
$ flake8
$ isort . --check --diff
$ mypy sublime_music tests/**/*.py
$ black --check .
$ ./cicd/custom_style_check.py
```

### Commit Message Format

Commits should be reasonably self-contained, that is, each commit should make
sense in isolation. Amending and force pushing is encouraged to help maintain
this.

Commit messages should be formatted as follows:

```
{component}: {short description}

{long description}
```

### Testing

This project uses `pytest` for testing. Tests can be added in the docstrings of
the methods that are being tested or in the `tests` directory. 100% test
coverage is **not** a goal of this project, and will never be. There is a lot of
code that just doesn't need tested, or is better if just tested manually (for
example most of the UI code).

#### Simulating Bad Network Conditions

One of the primary goals of this project is to be resilient to crappy network
conditions. If you have good internet, you can simulate bad internet with the
`REQUEST_DELAY` environment variable. This environment variable should be two
values, separated by a `,`: the lower and upper limit for the delay to add to
each network request. The delay will be a random number of seconds between the
lower and upper bounds. For example, the following will run Sublime Music and
every request will have an additional 3-5 seconds of latency:
```
$ REQUEST_DELAY=3,5 sublime-music
```

### GitHub Actions Workflows

This project uses two GitHub Actions workflows for building, testing, and
deploying the application to PyPi. A brief description of each of the workflows
is as follows:

* `deploy.yaml` - lint, build, and (if a release) deploy the project to PyPi
* `pages.yaml` - build and deploy the package documentation to GitHub Pages

[black]: https://github.com/psf/black
[flake8]: https://github.com/pycqa/flake8
[flit]: https://github.com/pypa/flit
[gh]: https://github.com/sublime-music/sublime-music
[ghissues]: https://github.com/sublime-music/sublime-music/issues
[ghpr]: https://github.com/sublime-music/sublime-music/pulls
[isort]: https://pycqa.github.io/isort/
[matrix]: https://matrix.to/#/!veTDkgvBExJGKIBYlU:matrix.org?via=matrix.org
[mypy]: http://mypy-lang.org/
[pip-tools]: https://github.com/jazzband/pip-tools
[pyenv]: https://github.com/pyenv/pyenv
[pre-commit]: https://pre-commit.com/
