libremsonic
===========

A \*sonic client for the Linux Desktop.

Built using Python and GTK+.

Design Decisions
================

- The ``server`` module is stateless. The only thing that it does is allow the
  module's user to query the Airsonic server via the API.
