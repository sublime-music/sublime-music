# Contributing

Contributions are welcome! You can engage with the project in many ways:

* GitLab: [create an issue][glissues] or [submit a MR][glmr] on [GitLab][gl].
* Matrix: join our [Matrix chat][matrix].
* Sourcehut: send patches to the [~sumner/sublime-music-devel][srhtdevel]
  mailing list, start discussions on
  [~sumner/sublime-music-discuss][srhtdiscuss] and/or subscribe to
  [~sumner/sublime-music-announce][srhtannounce] for low-volume announcements
  about the project.

## Issue Reporting

You can report issues or propose features by creating an [issue on
GitLab][glissues] or by sending an email to either the
[~sumner/sublime-music-devel][srhtdevel] or the
[~sumner/sublime-music-discuss][srhtdiscuss] mailing list.

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

If you want to propose a code change, please submit a [merge request][glmr] or
submit a patch to the [~sumner/sublime-music-devel][srhtdevel] mailing list. If
it is good, I will merge it in.

To get an overview of the Sublime Music code structure, I recommend taking a
look at the [`sublime_music` package
documentation](https://sublime-music.gitlab.io/sublime-music/api/sublime_music.html).

### Requirements

**WIP:** Please create an MR/send a patch with any other dependencies that you
had to install to develop the app. In general, the requirements are:

- Python 3.8 (I recommend you install this via [Pyenv][pyenv])
- GTK3
- GLib
- libmpv

#### Specific Requirements for Various Distros/OSes

* **NixOS:** use the `shell.nix` which will also run the `poetry install`
* **Arch Linux:** `pacman -S libnm-glib libnotify python-gobject gobject-introspection`
* **macOS (Homebrew):** `brew install mp3 gobject-introspection pkg-config pygobject3 gtk+3 adwaita-icon-theme`

### Installing

This project uses [Poetry][poetry] to manage dependences for both the core
package as well as for development. Make sure that you have [Poetry][poetry]
(and [Pyenv][pyenv] if necessary) set up properly, then run:
```
$ poetry install
```
to install the development dependencies as well as install `sublime-music` into
the virtual environment as editable.

You likely will want to install extras for Chromecast, keyring, and LAN server
support:
```
$ poetry install -E chromecast -E keyring -E server
```

### Running

With your Poetry virtual environment is activated, run:
```
$ sublime-music
```
to launch the application.

If you do not want to activate the Poetry virtual environment, you can use:
```
$ poetry run sublime-music
```

### Building the flatpak

- A flatpak-builder environment must be setup on the build machine to do a
  flatpak build. This includes `org.gnome.SDK//3.36` and
  `org.gnome.Platform//3.36`.
- The `flatpak` folder contains the required files to build a flatpak package.
- The script `flatpak_build.sh` will run the required commands to grab the
  remaining dependencies and build the flatpak.
- You can install the Flatpak using: `flatpak install sublime-music.flatpak` and
  run it using `flatpak run app.sublimemusic.SublimeMusic`.

### Code Style

This project follows [PEP-8](https://www.python.org/dev/peps/pep-0008/)
**strictly**. The *only* exception is maximum line length, which is 88 for this
project (in accordance with `black`'s defaults). Lines that contain a single
string literal are allowed to extend past the maximum line length limit.

This project uses [flake8][flake8], [mypy][mypy], and [black][black] to do
static analysis of the code and to enforce a consistent (and as deterministic as
possible) code style.

Although you can technically do all of the formatting yourself, it is
recommended that you use the following tools (they are automatically installed
if you are using Poetry). The CI process uses these to check all commits, so you
will probably want these so you don't have to wait for results of the build
before knowing if your code is the correct style.

* [`flake8`][flake8] is used for linting. The following
  additional plugins are also used:

  * `flake8-annotations`: enforce type annotations on function definitions.
  * `flake8-bugbear`: enforce a bunch of fairly opinionated styles.
  * `flake8-comprehensions`: enforce usage of comprehensions wherever possible.
  * `flake8-importorder` (with the `edited` import style): enforce ordering of
    import statements.
  * `flake8-pep3101`: no `%` string formatting.
  * `flake8-print`: to prevent using the `print` function. The more powerful
    `logging` should be used instead. In the rare case that you actually want to
    print to the terminal (the `--version` flag for example), then just disable
    this check with a `# noqa` or a `# noqa: T001` comment.

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

### CI/CD Pipeline

This project uses a CI/CD pipeline for building, testing, and deploying the
application to PyPi. A brief description of each of the stages is as follows:

`build-containers`

* Jobs in this stage are run every month by a Job Schedule. These jobs build the
  containers that some of the other jobs use.

`test`

* Lints the code (see [Code Style](#code-style)).
* Runs unit tests and doctests and produces a code coverage report.

`build`

* Builds the Python dist tar file
* Builds the flatpak.

`deploy`

* Deploys the documentation to GitLab pages. This job only runs on `master`.
* Deploys the dist file to PyPi. This only happens for commits tagged with a tag
  of the form `v*`.

`verify`

* Installs Sublime Music from PyPi to make sure that the raw install from PyPi
  works. This only happens for commits tagged with a tag of the form `v*`.

`release`

* Creates a new [GitLab Release][glrel] using the content from the most recent
  section of the `CHANGELOG`.

[black]: https://github.com/psf/black
[flake8]: https://gitlab.com/pycqa/flake8
[gl]: https://gitlab.com/sublime-music/sublime-music
[glissues]: https://gitlab.com/sublime-music/sublime-music/-/issues
[glmr]: https://gitlab.com/sublime-music/sublime-music/-/merge_requests
[glrel]: https://gitlab.com/sublime-music/sublime-music/-/releases
[matrix]: https://matrix.to/#/!veTDkgvBExJGKIBYlU:matrix.org?via=matrix.org
[mypy]: http://mypy-lang.org/
[poetry]: https:/python-poetry.org/
[pyenv]: https://github.com/pyenv/pyenv
[srhtannounce]: https://lists.sr.ht/~sumner/sublime-music-announce
[srhtdevel]: https://lists.sr.ht/~sumner/sublime-music-devel
[srhtdiscuss]: https://lists.sr.ht/~sumner/sublime-music-discuss
