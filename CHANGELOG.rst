v0.8.11
=======

* Added a logo. It's pretty bad, but it's something.
* Added a ``.desktop`` file for the app.
* Standardized the way that command line parameters are handled to use Python's
  ``argparse`` instead of the GTK argument parsing.

* **Infrastructure**

  * Added build step for logo at various different sizes.

v0.8.10
=======

* Converted to use use ``logging`` instead of ``print`` statements. Log file and
  level configurable using the ``-l|--logfile`` and ``-m|--loglevel``
  parameters.
* Added busy-wait on Chromecast retrieval when already getting Chromecasts.

* **Bug Fix:** Sublime Music no longer crashes when selecting a server for the
  first time.

* **Documentation**

  * Added automated documentation of the ``sublime`` Python module using Sphinx
    and automated parameter documentation using ``sphinx-autodoc-typehints``.
  * Started documenting more of the classes including type hints.
  * Added some screenshots.

* **Infrastructure**

  * Auto-deploy of documentation to GitLab Pages:
    https://sumner.gitlab.io/sublime-music.
  * Code coverage report now available for latest ``master`` at
    https://sumner.gitlab.io/sublime-music/htmlcov.
  * Lint step also disallows ``print()`` statements in code.

v0.8.9
======

**Note:** this release does not have Flatpak support due to a dependency issue
that I haven't been able to crack. Please install from PyPi or the AUR. (If you
are a Flatpak expert, I would greatly appreciate help fixing the issue. See
#79.)

* Global Search

  * Search for and go to Songs, Artists, Albums, and Playlists.
  * Works online and offline (when online, the search results from the server
    are included).
  * Uses a fuzzy matching algorithm for ranking results.

* Browse by filesystem structure via the "Browse" tab.

* Passwords are now stored in the system keyring rather than in plain text.

  **Note:** You will have to re-enter your password in the *Configure Servers*
  dialog to make Sublime Music successfully connect to your server again.

* The play queue now behaves properly when there are many instances of the same
  song in the play queue.

* The play queue can now be reordered, and songs can be added and removed from
  it. Right click also works on the play queue.

* The Local Network SSID and Local Network Address settings now actually work.
  It only checks the SSID on startup or new server connect for now.

* ``CacheManager`` now returns RAM results immediately instead of using a
  future. This means it returns data faster to the UI if it's already cached.

* **Bug Fixes:**

  * Pressing ESC on the Playlist edit dialog no longer deletes the playlist.
  * DBus functions no longer block on `CacheManager` results which was causing
    long startup times.

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
