v0.9.1
======

* **macOS Support Alpha:** support for macOS is now in alpha. There is very
  little documentation, and quite a few hacks, but core functionality works.
* Sublime Music is more resilient to certain libraries or functionalities not
  existing on the system. (Namely libnotify, NetworkManager, and DBus)
* Sublime Music now prompts you to confirm you actually want to delete the
  playlist. (#81)

* **Bug Fixes**

  * Sublime Music no longer explodes when you say "don't save password" in your
    keyring notification popup.
  * The ``NM`` library is used instead of the deprecated ``NetworkManager`` and
    ``NMClient``. (Contributed by @anarcat.)
  * Fixed some bugs where the state of the application wouldn't update when you
    deleted/downloaded songs from certain parts of the application.

v0.9.0
======

This is the first ``v0.9.*`` release. I've decided to bump the minor version,
since this is the first release where I feel that all core functionality works.
All of the releases in the ``v0.9.*`` series will build towards the ``v1.0.0``
release.

* New logo that isn't total garbage. By mountdesign_ on Fiverr_. (#110)
* Cover art for a given album is now only stored once at high resolution and
  scaled whenever used.
* The shuffle and repeat buttons are now toggle buttons, and no longer rely on
  the icon theme to provide context as to whether they are activated or not.
  (#125)
* Added support for Replay Gain option which is available from the Application
  Settings dialog. (#137)
* All of the buttons that are only icons now have tooltips describing what they
  do.

* **Bug Fixes**

  * The year inputs on the Albums tab no longer allow for non-numeric inputs,
    and are generally way less janky. (#123)
  * When dealing with track covers, the ``song.coverArt`` property is used
    instead of the ``song.id``. (Contributed by @sentriz.)
  * The Albums tab no longer loads infinitely when there are more than 500
    albums in the results. (Contributed by @sentriz.)
  * The Albums tab doesn't flicker every single time an ``update`` is called
    from the top level. (#114)
  * Fixed issue with setting the title of the "Edit/Add Server" dialog.

* **Infrastructure**

  * Enabled a bunch of flake8 linter extensions including:

    * Enforcing using type hints on all function declarations.
    * Enforcing no ``print`` statements via flake8 instead of my janky script.
    * Enforcing no use of ``%`` style string formatting.

    These changes resulted in a *lot* of code cleanup.

.. _mountdesign: https://www.fiverr.com/mountdesign
.. _Fiverr: https://www.fiverr.com

v0.8.13
=======

**Hotfix Release**: the previous release had a few major bugs which are
show-stoppers. This release fixes them.

* **Bug Fixes**

  * Fixed issue where Browse didn't work the first time you opened the app to
    that tab.
  * Fixed issue where refresh didn't work on the Artists tab.
  * Fixed issue displaying with incorrectly sized cover art in the player
    controls.

* **Infrastructure**

  * All TODOs in the code must now have corresponding issues.

v0.8.12
=======

:Milestone: Beta 3

* When album cover art is not provided by the server, a default album art image
  is used (Contributed by @sentriz.)
* **New Setting**: *Serve locally cached files over the LAN to Chromecast
  devices*: If checked, a local server will be started on your computer which
  will serve your locally cached music files to the Chromecast. If not checked,
  the Chromecast will always stream from the server.
* When serving local files, the internal server now only exposes one song at a
  time via a token and the song's token is randomized.
* The *Sync enabled* setting was renamed to *Play queue sync enabled*.

* **Bug Fixes**

  * Fixed issue where the UI was still in a "Playing" state after removing all
    songs from the play queue.
  * Fixed a multitude of problems where the wrong data would load if you quickly
    move around between cached and un-cached information.
  * When you use the Google Home app to cause the device that Sublime is using
    to "Stop Casting", Sublime now shows as paused.
  * The Chromecast device list are only requested after the first time you click
    on the Devices button.
  * Seeking now works with the mouse and keyboard.

* **Documentation**

  * Updated the CONTRIBUTING document to the current state of the Sublime Music
    codebase.
  * Added documentation for all of the settings available in Sublime Music.

* **Infrastructure**

  * Fixed logo build step.
  * Moved ``player`` module to root instead of being under ``ui.common``.

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
