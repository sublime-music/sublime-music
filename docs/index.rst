.. image:: ../logo/logo.png
   :width: 800px
   :alt: Sublime Music logo

Welcome to Sublime Music's documentation!
=========================================

Sublime Music is a native, GTK3
`Subsonic`_/`Airsonic`_/`Revel`_/`Gonic`_/`Navidrome`_/\*sonic client for the
Linux Desktop.

.. _Subsonic: http://www.subsonic.org/pages/index.jsp
.. _Airsonic: https://airsonic.github.io/
.. _Revel: https://gitlab.com/robozman/revel
.. _Gonic: https://github.com/sentriz/gonic
.. _Navidrome: https://www.navidrome.org/

.. figure:: ./_static/screenshots/play-queue.png
   :align: center
   :target: ./_static/screenshots/play-queue.png

   The Albums tab of Sublime Music with the Play Queue opened. :doc:`More
   Screenshots <./screenshots>`

Features
--------

* Switch between multiple Subsonic-API-compliant servers.
* Play music through Chromecast devices on the same LAN.
* Offline Mode where Sublime Music will not make any network requests.
* DBus MPRIS interface integration for controlling Sublime Music via clients
  such as ``playerctl``, ``i3status-rust``, KDE Connect, and many commonly used
  desktop environments.
* Browse songs by the sever-reported filesystem structure, or view them
  organized by ID3 tags in the Albums, Artists, and Playlists views.
* Intuitive play queue.
* Create/delete/edit playlists.
* Download songs for offline listening.

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

Or if you want to store your passwords in the system keyring instead of in
plain-text::

    pip install sublime-music[keyring]

.. note::

   Sublime Music requires Python 3.8. Please make sure that you have that
   installed. You may also need to use ``pip3`` instead of ``pip`` if you are on
   an OS that hasn't deprecated Python 2 yet.

.. toctree::
   :numbered:
   :maxdepth: 1
   :caption: Contents:

   screenshots.rst
   settings.rst
   adapter-api.rst
   api/sublime.rst

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
