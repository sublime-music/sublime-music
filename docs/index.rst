.. image:: ./logo/logo.png
   :width: 800px
   :alt: Sublime Music logo

Welcome to Sublime Music's documentation!
=========================================

Sublime Music is a GTK3 `Revel`_/`Gonic`_/`Subsonic`_/`Airsonic`_/\*sonic client
for the Linux Desktop.

.. _Revel: https://gitlab.com/robozman/revel
.. _Gonic: https://github.com/sentriz/gonic
.. _Subsonic: http://www.subsonic.org/pages/index.jsp
.. _Airsonic: https://airsonic.github.io/

.. figure:: ./_static/screenshots/play-queue.png
   :width: 80 %
   :align: center
   :target: ./_static/screenshots/play-queue.png

   The Playlist view of Sublime Music with the Play Queue opened. :doc:`More
   Screenshots <./screenshots>`

Features
--------

- Switch between multiple Subsonic-API-compliant servers.
- Play music through Chromecast devices on the same LAN.
- DBus MPRIS interface integration for controlling Sublime Music via DBus MPRIS
  clients such as ``playerctl``, ``i3status-rust``, KDE Connect, and many
  commonly used desktop environments.
- Browse songs by the sever-reported filesystem structure, or view them
  organized by ID3 tags in the Albums, Artists, and Playlists views.
- Intuitive play queue.
- Create/delete/edit playlists.
- Cache songs for offline listening.

Installation
------------

**Via the AUR**:

Install the |AUR Package|_. Example using ``yay``::

    yay -S sublime-music

.. |AUR Package| replace:: ``sublime-music`` package
.. _AUR Package: https://aur.archlinux.org/packages/sublime-music/

.. Uncomment when Flatpak support actually works.
.. **Via Flatpak**:
.. 
.. In the future, you will be able to install via Flathub. For now, if you want to
.. try the Flatpak, you will have to install it manually by visiting the Releases_
.. page and downloading the ``.flatpak`` file from there.
.. 
.. Then, you can install Sublime Music with::
.. 
..     sudo flatpak install sublime-music.flatpak
.. 
.. and run it by executing::
.. 
..     flatpak run com.sumnerevans.SublimeMusic
.. 
.. .. _Releases: https://gitlab.com/sumner/sublime-music/-/releases

**Via PyPi**::

    pip install sublime-music

.. toctree::
   :numbered:
   :maxdepth: 1
   :caption: Contents:

   screenshots.rst
   settings.rst
   api/sublime.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
