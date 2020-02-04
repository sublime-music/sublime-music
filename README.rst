Sublime Music
=============

**Click HERE_ for user documentation**

.. _HERE: https://sumner.gitlab.io/sublime-music/

This README is intended for developers and other contributors looking to
understand how to contribute to this project.

Requirements
------------

- Python 3.7
- GTK3
- GLib
- Probably other things... Please create an MR with any other dependencies that
  you had to install to develop the app.

This project uses a ``Pipfile`` for managing dev dependencies. Make sure that
you have Pipenv_ (and Pyenv_ if necessary) set up properly, then run::

    pipenv install --dev

to install the development dependencies as well as install ``sublime-music``
into the virtual environment as editable.

.. _Pipenv: https://pipenv.readthedocs.io/
.. _Pyenv: https://github.com/pyenv/pyenv

Building the flatpak
--------------------

*(currently broken)*

- A flatpak-builder environment must be setup on the build machine to do a
  flatpak build. This includes ``org.gnome.SDK//3.34`` and
  ``org.gnome.Platform//3.34``.
- The ``flatpak`` folder contains the required files to build a flatpak package.
- The script ``flatpak_build.sh`` will run the required commands to grab the
  remaining dependencies and build the flatpak.
