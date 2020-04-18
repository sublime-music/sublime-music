Adapter API
###########

Adapters are an interface between a collection of music data and metadata and
the Sublime Music UI. An adapter exposes a Subsonic-like API to the UI layer,
but can be backed by a variety of music stores including a Subsonic-compatible
server, data on the local filesystem, or even an entirely different service.

This document is designed to help you understand the Adapter API so that you can
create your own custom adapters. This document is best read in conjunction with
the :class:`sublime.adapters.Adapter` documentation. This document is meant as a
guide to tell you a general order in which to implement things.

Terms
=====

**Music Metadata**
  Metadata about a music collection. This includes things like song metadata,
  playlists, artists, albums, filesystem hierarchy, etc.

**Music Data**
  The actual data of a music file. This may be accessed in a variety of
  different ways including via a stream URL, or via the local filesystem.

**Music Source**
  A source of music metadata and music data. This is the most atomic entity that
  the user interacts with. It can be composed of one or two *Adapters*.

**Adapter**
  A module which exposes the Adapter API.

Creating Your Adapter Class
===========================

An adapter is composed of a single Python module. The adapter module can have
arbitrary code, and as many files/classes/functions/etc. as necessary, however
there must be one and only one class in the module which inherits from the
:class:`sublime.adapters.Adapter` class. Normally, a single file with a single
class should be enough to implement the entire adapter.

After you've created the class, you will want to implement the following
functions and properties first:

* ``__init__``: Used to initialize your adapter. See the
  :class:`sublime.adapters.Adapter.__init__` documentation for the function
  signature of the ``__init__`` function.
* ``is_available``: This property which will tell the UI whether or not your
  adapter can currently service requests. (See the
  :class:`sublime.adapters.Adapter.is_available` documentation for examples of
  what you may want to check in this property.)
* ``get_config_parameters``: Specifies the settings which can be configured on
  for the adapter. See :ref:`adapter-api:Handling Configuration` for details.
* ``verify_configuration``: Verifies whether or not a given set of configuration
  values are valid. See :ref:`adapter-api:Handling Configuration` for details.

.. tip::

   While developing the adapter, setting ``is_available`` to ``True`` will
   indicate to the UI that your adapter is always ready to service requests.
   This can be a useful debugging tool.

.. note::

   The :class:`sublime.adapters.Adapter` class is an `Abstract Base Class
   <abc_>`_ and all required functions are annotated with the
   ``@abstractmethod`` decorator. This means that your adapter will fail to
   instantiate if the abstract methods are not implemented.

   .. _abc: https://docs.python.org/3/library/abc.html

Handling Configuration
----------------------

For each configuration parameter you want to allow your adapter to accept, you
must do the following:

1. Choose a name for your configuration parameter. The configuration parameter
   name must be unique within your adapter.

2. Add a new entry to the return value of your
   :class:`sublime.adapters.Adapter.get_config_parameters` function with the key
   being the name from (1), and the value being a
   :class:`sublime.adapters.ConfigParamDescriptor`. The order of the keys in the
   dictionary matters, since the UI uses that to determine the order in which
   the configuration parameters will be shown in the UI.

3. Add any verifications that are necessary for your configuration parameter in
   your :class:`sublime.adapters.Adapter.verify_configuration` function. If you
   parameter descriptor has ``required = True``, then that parameter is
   guaranteed to appear in the configuration.

4. The configuration parameter will be passed into your
   :class:`sublime.adapters.Adapter.init` function. It is guaranteed that the
   ``verify_configuration`` will have been called first, so there is no need to
   re-verify the config that is passed.

Implementing Data Retrieval Methods
-----------------------------------

After you've done the initial configuration of your adapter class, you will want
to implement the actual adapter data retrieval functions.

For each data retrieval function there is a corresponding ``can_``-prefixed
property (CPP) which will be used by the UI to determine if the data retrieval
function can be called at the given time. If the CPP is ``False``, the UI will
never call the corresponding function (and if it does, it's a UI bug). The CPP
can be dynamic, for example, if your adapter supports many API versions, some of
the CPPs may depend on the API version.

There is a special, global ``can_``-prefixed property which determines whether
the adapter can currently service *any* requests. This should be used for checks
such as making sure that the user is able to access the server.

.. code:: python

    @property
    def can_service_requests(self) -> bool:
        return self.check_can_access_server()

Here is an example of what a ``get_playlists`` interface for an external server
might look like:

.. code:: python

    can_get_playlists = True
    def get_playlists(self) -> List[Playlist]:
        return my_server.get_playlists()

    can_get_playlist_details = True
    def get_playlist_details(self, playlist_id: str) -> PlaylistDetails:
        return my_server.get_playlist(playlist_id)

.. tip::

   By default, all ``can_``-prefixed properties are ``False``, which means that
   you can implement them one-by-one, testing as you go. The UI should
   dynamically enable features as new ``can_``-prefixed properties become
   ``True``.

Usage Parameters
----------------

There are a few special properties dictate how the adapter can be used. You
probably do not need to use this except for very specific purposes. Read the
"Usage Parameters" section of the source code for details.
