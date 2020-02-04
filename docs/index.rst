Welcome to Sublime Music's documentation!
=========================================

Sublime Music is a GTK3 `Revel`_/`Subsonic`_/`Airsonic`_/\*sonic client for the
Linux Desktop.

.. _Revel: https://gitlab.com/robozman/revel
.. _Subsonic: http://www.subsonic.org/pages/index.jsp
.. _Airsonic: https://airsonic.github.io/

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

Install the |AUR Package|_. Example using ``yay``::

    yay -S sublime-music

.. |AUR Package| replace:: ``sublime-music`` package
.. _AUR Package: https://aur.archlinux.org/packages/sublime-music/

**Via Flatpak**:

In the future, you will be able to install via Flathub. For now, if you want to
try the Flatpak, you will have to install it manually by visiting the Releases_
page and downloading the ``.flatpak`` file from there.

Then, you can install Sublime Music with::

    sudo flatpak install sublime-music.flatpak

and run it by executing::

    flatpak run com.sumnerevans.SublimeMusic

.. _Releases: https://gitlab.com/sumner/sublime-music/-/releases

**Via PyPi**::

    pip install sublime-music

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   screenshots.rst
   api/sublime.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
