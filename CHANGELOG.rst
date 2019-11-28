v0.8.9
======

* Passwords are now stored in the system keyring rather than in plain text.

  **Note:** You will have to re-enter your password in the *Configure Servers*
  dialog to make Sublime Music successfully connect to your server again.

* The play queue now behaves properly when there are many instances of the same
  song in the play queue.

* **Infrastructure**:

  * Added a ``Pipfile`` and made the CI/CD build use it for testing.
  * Upgraded the Flatpak dependencies on ``org.gnome.Platform`` and
    ``org.gnome.Sdk`` to ``3.34`` which allows us to have much faster Flatpak
    build times.
  * Added ``mypy`` tests to the build process.

v0.8.8
======

* Removed the ``gobject`` dependency from ``setup.py`` which hopefully fixes the
  issue with AUR installs.
* Don't scrobble songs until 5 seconds into the song.
* Added "Play All" and "Shuffle All" to the Artists view.
* Don't load the device list every single time the Devices button is pressed.
* Indicator for the currently active device in the Devices list.
* **Bug Fixes:**

  * Fixed a few of the icons.

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
