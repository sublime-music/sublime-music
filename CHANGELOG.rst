v0.11.4
=======

Improved the way that the version is retrieved for building the documentation to
make it easier to package for the AUR.

v0.11.2
=======

**Bug Fixes**

* Fixes bug where search didn't work in certain situations. (#253)
* Fixed bug when you deleted a song and then re-downloaded it.
* Fixed issue where all of the next N songs started downloading at once instead
  of one at a time when prefetching songs for the play queue.
* Improved performance of the searching for songs in the playlist list. (#28)

v0.11.1
=======

**Feature Improvements**

* Albums are sorted by year on the Artists detail view. (Contributed by
  @sentriz.)
* If the server doesn't support it, the Load Play Queue button on the Play Queue
  popup is now hidden. (#203)
* If the server doesn't support them, the "by year" and "by genre" sort options
  on the Albums tab are disabled. (#203)
* The app ID has been changed from ``com.sumnerevans.SublimeMusic`` to
  ``app.sublimemusic.SublimeMusic``. (#170)
* Better errors are shown on the Configure Provider dialog when there are SSL
  errors connecting to the Subsonic server. (#236)
* Playlists are prefetched on server connect to avoid lots of cache miss errors
  on the DBus diffing.

**Bug Fixes**

* Fixed issue where users couldn't log in to LMS due to Sublime Music always
  sending version number "1.15.0" instead of figuring out what version of the
  API the server actually reports.
* Fixed issue where edits to the music provider configurations were applied even
  if ESC was pressed. (#247)
* Fixed issue where pressing next/previous would start playing even if the
  player was paused. (#131)
* Fixed issue where using DBUS to go next/previous ignored when no song was
  playing. (#185)

**Under the Hood**

* Improved the API for getting song URIs from the adapters.

v0.11.0
=======

.. TODO in next release:
.. * A man page has been added. Contributed by @baldurmen.

.. note::

   This version does not have a Flatpak due to issues getting Python 3.8 working
   within the Flatpak environment. See `Issue #218
   <https://gitlab.com/sumner/sublime-music/-/issues/218_>`_

**New Website:** Sublime Music has a website! https://sublimemusic.app

**Distro Packages**

* Sublime Music is now available in Debian Unstable, and hopefully soon in
  Debian Testing.
* *For package maintainers:*

  The following dependencies were added:

  * ``semver``

  The following dependencies were removed:

  * ``pyyaml``

  The following dependencies are now optional:

  * ``pychromecast``
  * ``bottle``

**Feature Improvements**

* Player settings now get applied immediately, rather than after restarting
  Sublime Music.
* Getting the list of Chromecasts for the Device popup now happens much faster.

**Bug Fixes**

* Loading the play queue from the server is now more reliable and works properly
  with Gonic. (Contributed by @sentriz.)
* *Fixed Regression*: The load play queue button in the play queue popup works
  again.
* Caching behavior has been greatly improved.
* The Subsonic adapter disables saving and loading the play queue if the server
  doesn't implement the Subsonic API v1.12.0.

**Under the Hood**

* The API for players has been greatly improved and is now actually documented
  which will enable more player types in the future. Additionally, a Player
  Manager has been put in between the core logic of the app and the player logic
  which will help facilitate easier API transitions in the future.

v0.10.3
=======

This is a hotfix release. I forgot to add the Subsonic logo resources to
``setup.py``. All of the interesting updates happened in `v0.10.2`_.

.. _v0.10.2: https://gitlab.com/sublime-music/sublime-music/-/releases/v0.10.2

v0.10.2
=======

.. note::

   This version does not have a Flatpak due to issues getting Python 3.8 working
   within the Flatpak environment. See `Issue #218
   <https://gitlab.com/sublime-music/sublime-music/-/issues/218_>`_

.. warning::

   This version is not compatible with any previous versions. If you have run a
   previous version of Sublime Music, please delete your cache (likely in
   ``~/.local/share/sublime-music``) and your existing configuration (likely in
   ``~/.config/sublime-music``) and re-run Sublime Music to restart the
   configuration process.

Features
--------

**Improvements to configuring Music Sources**

* The mechanism for adding new *Music Sources* (the *Server* nomenclature has)
  been dropped in favor of the more generic *Music Source*) has been totally
  revamped. It now is a multi-stage dialog that will (in the future) allow you
  to connect to more than just Subsonic-compatible servers.
* The configuration form for Subsonic is no longer just a massive list of
  options. Instead, there is an "Advanced Settings" section that is collapsed by
  default.
* The configuration dialog automatically checks if you can connect to the server
  and shows you any errors which means there is no need to click "Test
  Connection to Server" any more!
* Adding and removing music sources is now done directly in the server popup
  (see below for details).

**Offline Mode**

* You can enable *Offline Mode* from the server menu.
* Features that require network access are disabled in offline mode.
* You can still browse anything that is already cached offline.

**Albums Tab Improvements**

* The Albums tab is now paginated with configurable page sizes.
* You can sort the Albums tab ascending or descending.
* Opening an closing an album on the Albums tab now has a nice animation and the
  album details panel is visually inset.
* The "Go to Album" functionality from the context menu is much more reliable.
* The album results can now be served from the cache much more often meaning
  less latency when trying to load albums (this is a byproduct of the Offline
  Mode work).

**Player Controls**

* The amount of the song that is cached is now shown while streaming a song.
* The notification for resuming a play queue is now a non-modal notification
  that pops up right above the player controls.

**New Icons**

* The Devices button now uses the Chromecast logo. It uses a different icon
  depending on whether or not you are playing on a Chromecast.
* Custom icons for "Add to play queue", and "Play next" buttons. Thanks to
  `@samsartor`_ for contributing the SVGs!
* A new icon for indicating the connection state to the Subsonic server.
  Contributed by `@samsartor`_.
* A new icon for that data wasn't able to be loaded due to being offline.
  Contributed by `@samsartor`_.

.. _@samsartor: https://gitlab.com/samsartor

**Application Menus**

* **Settings**

  * Settings are now in the popup under the gear icon rather than in a separate
    popup window.

* **Downloads**

  * A new Downloads popup shows the currently downloading songs.
  * You can now cancel song downloads and retry failed downloads.
  * You can now clear the cache (either the entire cache or just the song files)
    via options in the Downloads popup.

* **Server**

  * A new Server popup shows the connection state to the server in both the icon
    and the popup.
  * You can enable *Offline Mode* from this menu.
  * You can edit the current music source's configuration, switch to a different
    music source, or add a whole new music source via this menu.

**Other Features**

* You can now collapse the Artist details and the Playlist details so that you
  have more room to view the actual content.

Under The Hood
--------------

This release has a ton of under-the-hood changes to make things more robust
and performant.

* The cache is now stored in a SQLite database.
* The cache and configuration no longer get corrupted when Sublime Music fails
  to write to disk due to errors.
* A generic `Adapter API`_ has been created which means that Sublime Music is no
  longer reliant on Subsonic. This means that in the future, more backends can
  be added.

.. _Adapter API: https://sublime-music.gitlab.io/sublime-music/adapter-api.html

v0.9.2
======

* **Flatpak support is back!** After resolving a build error that's been
  plaguing us since **v0.8.9**, we once again have a Flatpak build!

  The Flatpak now also exports a ``.desktop`` file and an AppStream manifest
  file.

* The ``keyring`` dependency is now optional.
* The ``.desktop`` file doesn't hard-code the exec path anymore.

v0.9.1
======

* **macOS Support Alpha:** support for macOS is now in alpha. There is very
  little documentation, and quite a few hacks, but core functionality works.
* Sublime Music is more resilient to certain libraries or functionalities not
  existing on the system. (Namely libnotify, NetworkManager, and DBus)
* Sublime Music now prompts you to confirm you actually want to delete the
  playlist. (#81)
* Playlist and Artist info now scroll with the rest of the content which makes
  Sublime Music usable on smaller screens. (#152)
* Worked with deluan_ to support the Navidrome_ server.

* **Bug Fixes**

  * Sublime Music no longer explodes when you say "don't save password" in your
    keyring notification popup.
  * The ``NM`` library is used instead of the deprecated ``NetworkManager`` and
    ``NMClient``. (Contributed by @anarcat.)
  * Sublime Music will crash less often due to missing dependencies.
  * Fixed some bugs where the state of the application wouldn't update when you
    deleted/downloaded songs from certain parts of the application.

.. _deluan: https://www.deluan.com/
.. _Navidrome: https://www.navidrome.org/

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
    https://sublime-music.gitlab.io/sublime-music.
  * Code coverage report now available for latest ``master`` at
    https://sublime-music.gitlab.io/sublime-music/htmlcov.
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
