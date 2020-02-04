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

Install the Sublime Music app locally (commands may differ from what is
described below, this is merely an outline)::

    pip install -e . --user
    pip install -r dev-requirements.txt

Building the flatpak
--------------------

*(currently broken)*

- A flatpak-builder environment must be setup on the build machine to do a
  flatpak build. This includes ``org.gnome.SDK//3.34`` and
  ``org.gnome.Platform//3.34``.
- The ``flatpak`` folder contains the required files to build a flatpak package.
- The script ``flatpak_build.sh`` will run the required commands to grab the
  remaining dependencies and build the flatpak.
