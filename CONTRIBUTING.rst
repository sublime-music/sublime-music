Contributing
############

Contributions are welcome! Please create an issue, submit a MR, or engage on our
`Matrix chat`_.

.. _Matrix chat: https://matrix.to/#/!veTDkgvBExJGKIBYlU:matrix.org?via=matrix.org

Issue Reporting
===============

You can report issues or propose features using the GitLab Issues feature for
this repository: https://gitlab.com/sumner/sublime-music/issues.

Please note that as of right now, I (Sumner) am basically the only contributor
to this project, so my response time to your issue may be anywhere from instant
to infinite.

Code
====

If you want to propose a code change, please submit a merge request. If it is
good, I will merge it in.

To get an overview of the Sublime Music code structure, I recommend taking a
look at the |docs|_.

.. |docs| replace:: ``sublime`` package documentation
.. _docs: https://sumner.gitlab.io/sublime-music/api/sublime.html

Requirements
------------

- Python 3.7 (I recommend you install this via Pyenv_)
- GTK3
- GLib
- Probably other things... Please create an MR with any other dependencies that
  you had to install to develop the app.

Installing
----------

This project uses a ``Pipfile`` for managing dev dependencies. Make sure that
you have Pipenv_ (and Pyenv_ if necessary) set up properly, then run::

    $ pipenv install --dev

to install the development dependencies as well as install ``sublime-music``
into the virtual environment as editable.

.. _Pipenv: https://pipenv.readthedocs.io/
.. _Pyenv: https://github.com/pyenv/pyenv

Running
-------

If your Pipenv virtual environment is activated, the just run::

    $ sublime-music

to run the application. If you do not want to activate the pipenv virtual
environment, you can use::

    $ pipenv run sublime-music

Building the flatpak
--------------------

*(currently broken)*

- A flatpak-builder environment must be setup on the build machine to do a
  flatpak build. This includes ``org.gnome.SDK//3.34`` and
  ``org.gnome.Platform//3.34``.
- The ``flatpak`` folder contains the required files to build a flatpak package.
- The script ``flatpak_build.sh`` will run the required commands to grab the
  remaining dependencies and build the flatpak.

Code Style
----------

* `PEP-8`_ is to be followed **strictly**.
* `mypy`_ is used for type checking.
* ``print`` statements are not to be used except for when you actually want to
  print to the terminal (which should be rare). In all other cases, the more
  powerful and useful ``logging`` library should be used.

.. _`PEP-8`: https://www.python.org/dev/peps/pep-0008/
.. _mypy: http://mypy-lang.org/

The CI process uses Flake8 and MyPy to lint the Python code. The CI process also
checks for uses of ``print``. You can run the same checks that the lint job runs
yourself with the following commands::

    $ flake8
    $ mypy sublime
    $ ./cicd/custom_style_check.py

CI/CD Pipeline
--------------

This project uses a CI/CD pipeline for building, testing, and deploying the
application to PyPi. A brief description of each of the stages is as follows:

``build-containers``
    * Jobs in this stage are run every month by a Job Schedule. These jobs build
      the containers that some of the other jobs use.

``test``
    * Lints the code using ``flake8`` and ``mypy`` and prevents the use of
      ``print`` except in certain cases.
    * Runs unit tests and doctests and produces a code coverage report.

``build``
    * Builds the Python dist tar file
    * Compiles the logo to multiple different sizes
    * Builds the flatpak.

``deploy``
    * Deploys the documentation to GitLab pages. This job only runs on
      ``master``.
    * Deploys the dist file to PyPi. This only happens for commits tagged with a
      tag of the form ``v*``.

``verify``
    * Installs Sublime Music from PyPi to make sure that the raw install from
      PyPi works.

``release``
    Creates a new `GitLab Release`_ using the content from the most recent
    section of the ``CHANGELOG``.

.. _GitLab Release: https://gitlab.com/sumner/sublime-music/-/releases
