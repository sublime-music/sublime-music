v0.8.7
======

* **Flatpak support!** Everything works with Flatpak now, and the Flatpak is
  configured to use the local ``XDG`` directories.
* Switch between multiple Subsonic API compliant servers.
* Fixed a few of the icons to make them use the ``-symbolic`` version.
* Infrastructure:

  * Automatically cut a release when a ``v*`` tag is present. (This creates a
    PyPi release and a new release in the Releases tab.)
  * Protected the ``v*`` tag so that only maintainers can deploy releases.

v0.8.6
======

* Pre-beta release
* First release to be released to the AUR
* Everything is more or less working. Most of the main user flows are fully
  supported.
* Browse songs using Album, Artist, and Playlist views.
* Connect to a Subsonic API compliant server.
* Play music through Chromecasts on the same LAN.
* DBus MPRIS interface integration for controlling Sublime Music via
  ``playerctl``, ``i3status-rust``, KDE Connect, and other DBus MPRIS clients.
* Play queue.
* Create/delete/edit Playlists.
* Cache songs for offline listening.
