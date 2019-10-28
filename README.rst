Sublime Music
=============

A GTK3 `Revel`_/`Subsonic`_/`Airsonic`_/\*sonic client for the Linux Desktop.

.. _Revel: https://gitlab.com/robozman/revel
.. _Subsonic: http://www.subsonic.org/pages/index.jsp
.. _Airsonic: https://airsonic.github.io/

Built using Python and GTK+.

Features
--------

- Connect to multiple Subsonic-API-compliant servers.
- Play music through Chromecasts on the same LAN.
- DBus MPRIS interface integration for controlling Sublime Music via
  ``playerctl``, ``i3status-rust``, KDE Connect, and other DBus MPRIS clients.
- Browse Albums, Artists, and Playlists.
- Play queue.
- Create/delete/edit Playlists.
- Cache songs for offline listening.

Installation
------------

**Via the AUR**:

Install the ``sublime-music`` package. Example using ``yay``::

    TODO

**Via Flatpak**:

TODO: make a link to the flathub repo so that you can just click on it and go to
the software center for the app.

**Via PyPi**::

    TODO

Development Setup
-----------------

Requirements:

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
^^^^^^^^^^^^^^^^^^^^

- A flatpak-builder environment must be setup on the build machine to do a
  flatpak build. This includes ``org.gnome.SDK//3.32`` and
  ``org.gnome.Platform//3.32``.
- The ``flatpak`` folder contains the required files to build a flatpak package.
- The repository must be cloned to include submodules as they are used to manage
  some flatpak dependencies.
- The script ``flatpak_build.sh`` will run the required commands to grab the
  remaining dependencies and build the flatpak.
