Settings
########

There are many settings available in Sublime Music. Some are application-wide
settings while others are are configurable at a per-server basis.

Application Settings
--------------------

The following settings can be changed for the entire application.

Port Number : (int)
    The port number to use for streaming to Chromecast devices on the same
    LAN.

    A server will be started on this port and when you play a song that is
    already cached locally, the Chromecast will connect to your computer and
    stream from it instead of from the internet.

    This will not take effect until the application is restarted.

Replay Gain : (Disabled | Track | Album)
    Configures the replay gain setting for the MPV player. You can disable this
    setting, or configure it to work on a track or album basis.

Always stream songs : (bool)
    If checked, this will disable using the local song cache.

When streaming, also download song : (bool)
    If checked, when a song is streamed, it will also be downloaded. Once the
    download is complete, Sublime Music will stop streaming and switch to the
    downloaded version.

Show notification when song begins to play : (bool)
    If checked, a notification containing the new song's title, artist, album,
    and album art will be shown through your notification daemon.

Serve locally cached files over the LAN to Chromecast devices : (bool)
    If checked, a local server will be started on your computer which will serve
    your locally cached music files to the Chromecast. If not checked, the
    Chromecast will always stream from the server.

How many songs in the play queue do you want to prefetch? : (int)
    If the next :math:`n` songs in the play queue are not already downloaded,
    they will be downloaded. (This has no effect if *Always stream songs* is
    checked.)

How many song downloads do you want to allow concurrently? : (int)
    Specifies how many songs can be downloaded at the same time.

Server Settings
---------------

Each server has the following configuration options:

Name : (string)
    The friendly name of this server which is used throughout the UI to
    differentiate servers.

Server address : (uri)
    The URI of the Subsonic-API-compliant server (specify the server root, do
    not include ``/api`` or any other suffix).

Local network address : (string)
    See *Local network SSID*

Local network SSID : (string)
    If this SSID is active (as reported by NetworkManager), then the *Local
    network address* will be used to connect to the Subsonic-API-compliant
    server instead of the *Server address*.

    This is useful if your internet provider does not allow you to connect to
    your internal network using the IP of your network.

Username : (string)
    The username to login as.

Password : (string)
    The password to login with. This is stored in the system keyring.

Play queue sync enabled : (bool)
    If checked, Sublime Music will synchronise the play queue and song progress
    to the server every 15 seconds, whenever the song is paused/played, whenever
    the play queue is edited, and whenever a new song is started.

Do not verify certificate : (bool)
    Disables certificate verification if the protocol is HTTPS.

    .. danger::

       Only check this if you are *absolutely certain* that your connection to
       your server is secure, despite having an invalid or self-signed
       certificate.
