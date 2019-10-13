libremsonic
===========

A GTK3 `Revel`_/`Subsonic`_/`Airsonic`_/\*sonic client for the Linux Desktop.

.. _Revel: https://gitlab.com/robozman/revel
.. _Subsonic: http://www.subsonic.org/pages/index.jsp
.. _Airsonic: https://airsonic.github.io/

Built using Python and GTK+.

Design Decisions
----------------

- The ``server`` module is stateless. The only thing that it does is allow the
  module's user to query the Airsonic server via the API.

flatpak Support
---------------

- A flatpak-builder environment must be setup on the build machine to do a
  flatpak build. This includes ``org.gnome.SDK//3.32`` and
  ``org.gnome.Platform//3.32``.
- The ``flatpak`` folder contains the required files to build a flatpak package.
- The repository must be cloned to include submodules as they are used to manage
  some flatpak dependencies.
- The script ``flatpak_build.sh`` will run the required commands to grab the
  remaining dependencies and build the flatpak.
