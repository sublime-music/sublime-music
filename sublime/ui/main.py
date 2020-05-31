from functools import partial
from typing import Any, Callable, Dict, Optional, Set, Tuple

from gi.repository import Gdk, GLib, GObject, Gtk, Pango

from sublime.adapters import (
    AdapterManager,
    api_objects as API,
    DownloadProgress,
    Result,
)
from sublime.config import AppConfiguration, ReplayGainType
from sublime.ui import albums, artists, browse, player_controls, playlists, util
from sublime.ui.common import IconButton, IconMenuButton, SpinnerImage


class MainWindow(Gtk.ApplicationWindow):
    """Defines the main window for Sublime Music."""

    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "songs-removed": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (object,),),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
        "notification-closed": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (),),
        "go-to": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (str, str),),
    }

    _updating_settings: bool = False
    _pending_downloads: Set[str] = set()
    _failed_downloads: Set[str] = set()
    _current_download_boxes: Dict[str, Gtk.Box] = {}
    _failed_downloads_box: Optional[Gtk.Label] = None
    _pending_downloads_label: Optional[Gtk.Label] = None
    _current_downloads_placeholder: Optional[Gtk.Label] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(1150, 768)

        # Create the stack
        self.albums_panel = albums.AlbumsPanel()
        self.artists_panel = artists.ArtistsPanel()
        self.browse_panel = browse.BrowsePanel()
        self.playlists_panel = playlists.PlaylistsPanel()
        self.stack = self._create_stack(
            Albums=self.albums_panel,
            Artists=self.artists_panel,
            Browse=self.browse_panel,
            Playlists=self.playlists_panel,
        )
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.titlebar = self._create_headerbar(self.stack)
        self.set_titlebar(self.titlebar)

        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        notification_container = Gtk.Overlay()

        notification_container.add(self.stack)

        self.notification_revealer = Gtk.Revealer(
            valign=Gtk.Align.END, halign=Gtk.Align.CENTER
        )

        notification_box = Gtk.Box(can_focus=False, valign="start", spacing=10)
        notification_box.get_style_context().add_class("app-notification")

        self.notification_icon = Gtk.Image()
        notification_box.pack_start(self.notification_icon, True, False, 5)

        self.notification_text = Gtk.Label(use_markup=True)
        notification_box.pack_start(self.notification_text, True, False, 5)

        self.notification_actions = Gtk.Box()
        notification_box.pack_start(self.notification_actions, True, False, 0)

        notification_box.add(close_button := IconButton("window-close-symbolic"))
        close_button.connect("clicked", lambda _: self.emit("notification-closed"))

        self.notification_revealer.add(notification_box)

        notification_container.add_overlay(self.notification_revealer)
        flowbox.pack_start(notification_container, True, True, 0)

        # Player Controls
        self.player_controls = player_controls.PlayerControls()
        self.player_controls.connect(
            "song-clicked", lambda _, *a: self.emit("song-clicked", *a)
        )
        self.player_controls.connect(
            "songs-removed", lambda _, *a: self.emit("songs-removed", *a)
        )
        self.player_controls.connect(
            "refresh-window", lambda _, *args: self.emit("refresh-window", *args),
        )
        flowbox.pack_start(self.player_controls, False, True, 0)

        self.add(flowbox)

        self.connect("button-release-event", self._on_button_release)

    current_notification_hash = None

    def update(self, app_config: AppConfiguration, force: bool = False):
        notification = app_config.state.current_notification
        if notification and (h := hash(notification)) != self.current_notification_hash:
            self.current_notification_hash = h

            if notification.icon:
                self.notification_icon.set_from_icon_name(
                    notification.icon, Gtk.IconSize.DND
                )
            else:
                self.notification_icon.set_from_icon_name(None, Gtk.IconSize.DND)

            self.notification_text.set_markup(notification.markup)

            for c in self.notification_actions.get_children():
                self.notification_actions.remove(c)

            for label, fn in notification.actions:
                self.notification_actions.add(action_button := Gtk.Button(label=label))
                action_button.connect("clicked", lambda _: fn())

            self.notification_revealer.show_all()
            self.notification_revealer.set_reveal_child(True)

        if notification is None:
            self.notification_revealer.set_reveal_child(False)

        # Update the Connected to label on the popup menu.
        if app_config.server:
            self.connected_to_label.set_markup(f"<b>{app_config.server.name}</b>")
        else:
            self.connected_to_label.set_markup("<i>No Music Source Selected</i>")

        if AdapterManager.ground_truth_adapter_is_networked:
            status_label = ""
            if app_config.offline_mode:
                status_label = "Offline"
            elif AdapterManager.get_ping_status():
                status_label = "Connected"
            else:
                status_label = "Error Connecting to Server"

            self.server_connection_menu_button.set_icon(
                f"server-subsonic-{status_label.split()[0].lower()}-symbolic"
            )
            self.connection_status_icon.set_from_icon_name(
                f"server-{status_label.split()[0].lower()}-symbolic",
                Gtk.IconSize.BUTTON,
            )
            self.connection_status_label.set_text(status_label)
            self.connected_status_box.show_all()
        else:
            self.connected_status_box.hide()

        self._updating_settings = True

        # Main Settings
        offline_mode = app_config.offline_mode
        self.offline_mode_switch.set_active(offline_mode)
        self.notification_switch.set_active(app_config.song_play_notification)
        self.replay_gain_options.set_active_id(app_config.replay_gain.as_string())
        self.serve_over_lan_switch.set_active(app_config.serve_over_lan)
        self.port_number_entry.set_value(app_config.port_number)

        # Download Settings
        allow_song_downloads = app_config.allow_song_downloads
        self.allow_song_downloads_switch.set_active(allow_song_downloads)
        self.download_on_stream_switch.set_active(app_config.download_on_stream)
        self.prefetch_songs_entry.set_value(app_config.prefetch_amount)
        self.max_concurrent_downloads_entry.set_value(
            app_config.concurrent_download_limit
        )
        self.download_on_stream_switch.set_sensitive(allow_song_downloads)
        self.prefetch_songs_entry.set_sensitive(allow_song_downloads)
        self.max_concurrent_downloads_entry.set_sensitive(allow_song_downloads)

        self._updating_settings = False

        self.stack.set_visible_child_name(app_config.state.current_tab)

        active_panel = self.stack.get_visible_child()
        if hasattr(active_panel, "update"):
            active_panel.update(app_config, force=force)

        self.player_controls.update(app_config, force=force)

    def update_song_download_progress(self, song_id: str, progress: DownloadProgress):
        if progress.type == DownloadProgress.Type.QUEUED:
            if (
                song_id not in self._failed_downloads
                and song_id not in self._current_download_boxes.keys()
            ):
                self._pending_downloads.add(song_id)
        elif progress.type in (
            DownloadProgress.Type.DONE,
            DownloadProgress.Type.CANCELLED,
        ):
            # Remove and delete the box for the download if it exists.
            if song_id in self._current_download_boxes:
                self.current_downloads_box.remove(self._current_download_boxes[song_id])
                del self._current_download_boxes[song_id]

            # The download is no longer pending.
            if song_id in self._pending_downloads:
                self._pending_downloads.remove(song_id)
        elif progress.type == DownloadProgress.Type.ERROR:
            self._failed_downloads.add(song_id)
            self.current_downloads_box.remove(self._current_download_boxes[song_id])
            del self._current_download_boxes[song_id]
        elif progress.type == DownloadProgress.Type.PROGRESS:
            if song_id not in self._current_download_boxes:
                # Create and add the box to show the progress.
                self._current_download_boxes[song_id] = DownloadStatusBox(song_id)
                self._current_download_boxes[song_id].connect(
                    "cancel-clicked", self._on_download_box_cancel_click
                )
                self.current_downloads_box.add(self._current_download_boxes[song_id])

            if song_id in self._pending_downloads:
                self._pending_downloads.remove(song_id)
            if song_id in self._failed_downloads:
                self._failed_downloads.remove(song_id)

            self._current_download_boxes[song_id].update_progress(
                progress.progress_fraction
            )

        # Show or hide the "failed count" indicator.
        failed_download_count = len(self._failed_downloads)
        if failed_download_count > 0:
            if not self._failed_downloads_box:
                self._failed_downloads_box = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL
                )

                self._failed_downloads_label = Gtk.Label(
                    label="",
                    halign=Gtk.Align.START,
                    name="current-downloads-list-failed-count",
                )
                self._failed_downloads_box.add(self._failed_downloads_label)

                retry_all_button = IconButton(
                    "view-refresh-symbolic", tooltip_text="Retry all failed downloads."
                )
                retry_all_button.connect("clicked", self._on_retry_all_clicked)
                self._failed_downloads_box.pack_end(retry_all_button, False, False, 0)

                self.current_downloads_box.pack_start(
                    self._failed_downloads_box, False, False, 5
                )
            songs = util.pluralize("song", failed_download_count)
            self._failed_downloads_label.set_text(
                f"{failed_download_count} {songs} failed to download"
            )
        else:
            if self._failed_downloads_box:
                self.current_downloads_box.remove(self._failed_downloads_box)
                self._failed_downloads_box = None

        # Show or hide the "pending count" indicator.
        pending_download_count = len(self._pending_downloads)
        if pending_download_count > 0:
            if not self._pending_downloads_label:
                self._pending_downloads_label = Gtk.Label(
                    label="",
                    halign=Gtk.Align.START,
                    name="current-downloads-list-pending-count",
                )
                self.current_downloads_box.pack_end(
                    self._pending_downloads_label, False, False, 5
                )
            songs = util.pluralize("song", pending_download_count)
            self._pending_downloads_label.set_text(
                f"+{pending_download_count} pending {songs}"
            )
        else:
            if self._pending_downloads_label:
                self.current_downloads_box.remove(self._pending_downloads_label)
                self._pending_downloads_label = None

        # Show or hide the placeholder depending on whether or not there's anything to
        # show.
        current_downloads = (
            len(self._current_download_boxes)
            + pending_download_count
            + failed_download_count
        )
        if current_downloads == 0:
            if not self._current_downloads_placeholder:
                self._current_downloads_placeholder = Gtk.Label(
                    label="<i>No current downloads</i>",
                    use_markup=True,
                    name="current-downloads-list-placeholder",
                )
                self.current_downloads_box.add(self._current_downloads_placeholder)
        else:
            if self._current_downloads_placeholder:
                self.current_downloads_box.remove(self._current_downloads_placeholder)
                self._current_downloads_placeholder = None

        self.current_downloads_box.show_all()

        self.cancel_all_button.set_sensitive(current_downloads > 0)

    def _on_cancel_all_clicked(self, _):
        AdapterManager.cancel_download_songs(
            {*self._pending_downloads, *self._current_download_boxes.keys()}
        )

    def _on_download_box_cancel_click(self, _, song_id: str):
        AdapterManager.cancel_download_songs([song_id])

    def _on_retry_all_clicked(self, _):
        AdapterManager.batch_download_songs(
            self._failed_downloads, lambda _: None, lambda _: None,
        )

    def _create_stack(self, **kwargs: Gtk.Widget) -> Gtk.Stack:
        stack = Gtk.Stack()
        for name, child in kwargs.items():
            child.connect(
                "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
            )
            child.connect(
                "refresh-window", lambda _, *args: self.emit("refresh-window", *args),
            )
            stack.add_titled(child, name.lower(), name)
        return stack

    def _create_headerbar(self, stack: Gtk.Stack) -> Gtk.HeaderBar:
        """
        Configure the header bar for the window.
        """
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = "Sublime Music"

        # Search
        self.search_entry = Gtk.SearchEntry(placeholder_text="Search everything...")
        self.search_entry.connect("focus-in-event", self._on_search_entry_focus)
        self.search_entry.connect(
            "button-press-event", self._on_search_entry_button_press
        )
        self.search_entry.connect("focus-out-event", self._on_search_entry_loose_focus)
        self.search_entry.connect("changed", self._on_search_entry_changed)
        self.search_entry.connect("stop-search", self._on_search_entry_stop_search)
        header.pack_start(self.search_entry)

        # Search popup
        self._create_search_popup()

        # Stack switcher
        switcher = Gtk.StackSwitcher(stack=stack)
        header.set_custom_title(switcher)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        # Downloads
        self.downloads_popover = self._create_downloads_popover()
        self.downloads_menu_button = IconMenuButton(
            "folder-download-symbolic",
            tooltip_text="Show download status",
            popover=self.downloads_popover,
        )
        self.downloads_menu_button.connect("clicked", self._on_downloads_menu_clicked)
        self.downloads_popover.set_relative_to(self.downloads_menu_button)
        button_box.add(self.downloads_menu_button)

        # Menu button
        self.main_menu_popover = self._create_main_menu()
        main_menu_button = IconMenuButton(
            "emblem-system-symbolic",
            tooltip_text="Open Sublime Music settings",
            popover=self.main_menu_popover,
        )
        main_menu_button.connect("clicked", self._on_main_menu_clicked)
        self.main_menu_popover.set_relative_to(main_menu_button)
        button_box.add(main_menu_button)

        # Server icon and change server dropdown
        self.server_connection_popover = self._create_server_connection_popover()
        self.server_connection_menu_button = IconMenuButton(
            "server-subsonic-offline-symbolic",
            tooltip_text="Server connection settings",
            popover=self.server_connection_popover,
        )
        self.server_connection_menu_button.connect(
            "clicked", self._on_server_connection_menu_clicked
        )
        self.server_connection_popover.set_relative_to(
            self.server_connection_menu_button
        )
        button_box.add(self.server_connection_menu_button)

        header.pack_end(button_box)

        return header

    def _create_label(
        self, text: str, *args, halign: Gtk.Align = Gtk.Align.START, **kwargs
    ) -> Gtk.Label:
        label = Gtk.Label(
            use_markup=True,
            halign=halign,
            ellipsize=Pango.EllipsizeMode.END,
            *args,
            **kwargs,
        )
        label.set_markup(text)
        label.get_style_context().add_class("search-result-row")
        return label

    def _create_toggle_menu_button(
        self, label: str, settings_name: str
    ) -> Tuple[Gtk.Box, Gtk.Switch]:
        def on_active_change(toggle: Gtk.Switch, _):
            self._emit_settings_change({settings_name: toggle.get_active()})

        box = Gtk.Box()
        box.add(gtk_label := Gtk.Label(label=label))
        gtk_label.get_style_context().add_class("menu-label")
        switch = Gtk.Switch(active=True)
        switch.connect("notify::active", on_active_change)
        box.pack_end(switch, False, False, 0)
        box.get_style_context().add_class("menu-button")
        return box, switch

    def _create_model_button(
        self, text: str, clicked_fn: Callable = None, **kwargs
    ) -> Gtk.ModelButton:
        model_button = Gtk.ModelButton(text=text, **kwargs)
        model_button.get_style_context().add_class("menu-button")
        if clicked_fn:
            model_button.connect("clicked", clicked_fn)
        return model_button

    def _create_spin_button_menu_item(
        self, label: str, low: int, high: int, step: int, settings_name: str
    ) -> Tuple[Gtk.Box, Gtk.Entry]:
        def on_change(entry: Gtk.SpinButton) -> bool:
            self._emit_settings_change({settings_name: int(entry.get_value())})
            return False

        box = Gtk.Box()
        box.add(spin_button_label := Gtk.Label(label=label))
        spin_button_label.get_style_context().add_class("menu-label")

        entry = Gtk.SpinButton.new_with_range(low, high, step)
        entry.connect("value-changed", on_change)
        box.pack_end(entry, False, False, 0)
        box.get_style_context().add_class("menu-button")
        return box, entry

    def _create_downloads_popover(self) -> Gtk.PopoverMenu:
        menu = Gtk.PopoverMenu()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="downloads-menu")

        current_downloads_header = Gtk.Box()
        current_downloads_header.add(
            current_downloads_label := Gtk.Label(
                label="Current Downloads", name="menu-header",
            )
        )
        current_downloads_label.get_style_context().add_class("menu-label")
        self.cancel_all_button = IconButton(
            "process-stop-symbolic", "Cancel all downloads", sensitive=False
        )
        self.cancel_all_button.connect("clicked", self._on_cancel_all_clicked)
        current_downloads_header.pack_end(self.cancel_all_button, False, False, 0)
        vbox.add(current_downloads_header)

        self.current_downloads_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, name="current-downloads-list"
        )
        self._current_downloads_placeholder = Gtk.Label(
            label="<i>No current downloads</i>",
            use_markup=True,
            name="current-downloads-list-placeholder",
        )
        self.current_downloads_box.add(self._current_downloads_placeholder)
        vbox.add(self.current_downloads_box)

        vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        clear_cache = self._create_model_button("Clear Cache", menu_name="clear-cache")
        vbox.add(clear_cache)
        menu.add(vbox)

        # Create the "Add song(s) to playlist" sub-menu.
        clear_cache_options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Back button
        clear_cache_options.add(
            Gtk.ModelButton(inverted=True, centered=True, menu_name="main")
        )

        # Clear Song File Cache
        menu_items = [
            ("Delete Cached Song Files", self._clear_song_file_cache),
            ("Delete Cached Song Files and Metadata", self._clear_entire_cache),
        ]
        for text, clicked_fn in menu_items:
            clear_song_cache = self._create_model_button(text, clicked_fn)
            clear_cache_options.pack_start(clear_song_cache, False, True, 0)

        menu.add(clear_cache_options)
        menu.child_set_property(clear_cache_options, "submenu", "clear-cache")

        return menu

    def _create_server_connection_popover(self) -> Gtk.PopoverMenu:
        menu = Gtk.PopoverMenu()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Current Server

        self.connected_to_label = self._create_label(
            "<i>No Music Source Selected</i>",
            name="connected-to-label",
            halign=Gtk.Align.CENTER,
        )
        vbox.add(self.connected_to_label)

        self.connected_status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, name="connected-status-row"
        )
        self.connected_status_box.pack_start(Gtk.Box(), True, True, 0)

        self.connection_status_icon = Gtk.Image.new_from_icon_name(
            "server-online", Gtk.IconSize.BUTTON
        )
        self.connection_status_icon.set_name("online-status-icon")
        self.connected_status_box.add(self.connection_status_icon)

        self.connection_status_label = Gtk.Label(
            label="Connected", name="connection-status-label"
        )
        self.connected_status_box.add(self.connection_status_label)

        self.connected_status_box.pack_start(Gtk.Box(), True, True, 0)
        vbox.add(self.connected_status_box)

        # Offline Mode
        offline_box, self.offline_mode_switch = self._create_toggle_menu_button(
            "Offline Mode", "offline_mode"
        )
        vbox.add(offline_box)

        edit_button = self._create_model_button(
            "Edit Configuration...", self._on_edit_configuration_click
        )
        vbox.add(edit_button)

        vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        music_provider_button = self._create_model_button(
            "Switch Music Provider",
            self._on_switch_provider_click,
            menu_name="switch-provider",
        )
        # TODO (#197)
        music_provider_button.set_action_name("app.configure-servers")
        vbox.add(music_provider_button)

        add_new_music_provider_button = self._create_model_button(
            "Add New Music Provider...", self._on_add_new_provider_click
        )
        vbox.add(add_new_music_provider_button)

        menu.add(vbox)
        return menu

    def _create_main_menu(self) -> Gtk.PopoverMenu:
        main_menu = Gtk.PopoverMenu()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="main-menu-box")

        # Notifications
        notifications_box, self.notification_switch = self._create_toggle_menu_button(
            "Enable Song Notifications", "song_play_notification"
        )
        vbox.add(notifications_box)

        # PLAYER SETTINGS
        # ==============================================================================
        vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        vbox.add(
            self._create_label(
                "Local Playback Settings", name="menu-settings-separator"
            )
        )

        # Replay Gain
        replay_gain_box = Gtk.Box()
        replay_gain_box.add(replay_gain_label := Gtk.Label(label="Replay Gain"))
        replay_gain_label.get_style_context().add_class("menu-label")

        replay_gain_option_store = Gtk.ListStore(str, str)
        for id, option in (("no", "Disabled"), ("track", "Track"), ("album", "Album")):
            replay_gain_option_store.append([id, option])

        self.replay_gain_options = Gtk.ComboBox.new_with_model(replay_gain_option_store)
        self.replay_gain_options.set_id_column(0)
        renderer_text = Gtk.CellRendererText()
        self.replay_gain_options.pack_start(renderer_text, True)
        self.replay_gain_options.add_attribute(renderer_text, "text", 1)
        self.replay_gain_options.connect("changed", self._on_replay_gain_change)

        replay_gain_box.pack_end(self.replay_gain_options, False, False, 0)
        replay_gain_box.get_style_context().add_class("menu-button")
        vbox.add(replay_gain_box)

        vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        vbox.add(
            self._create_label("Chromecast Settings", name="menu-settings-separator")
        )

        # Serve Local Files to Chromecast
        serve_over_lan, self.serve_over_lan_switch = self._create_toggle_menu_button(
            "Serve Local Files to Chromecasts on the LAN", "serve_over_lan"
        )
        vbox.add(serve_over_lan)

        # Server Port
        server_port_box, self.port_number_entry = self._create_spin_button_menu_item(
            "LAN Server Port Number", 8000, 9000, 1, "port_number"
        )
        vbox.add(server_port_box)

        # DOWNLOAD SETTINGS
        # ==============================================================================
        vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        vbox.add(
            self._create_label("Download Settings", name="menu-settings-separator")
        )

        # Allow Song Downloads
        (
            allow_song_downloads,
            self.allow_song_downloads_switch,
        ) = self._create_toggle_menu_button(
            "Allow Song Downloads", "allow_song_downloads"
        )
        vbox.add(allow_song_downloads)

        # Download on Stream
        (
            download_on_stream,
            self.download_on_stream_switch,
        ) = self._create_toggle_menu_button(
            "When Streaming, Also Download Song", "download_on_stream"
        )
        vbox.add(download_on_stream)

        # Prefetch Songs
        (
            prefetch_songs_box,
            self.prefetch_songs_entry,
        ) = self._create_spin_button_menu_item(
            "Number of Songs to Prefetch", 0, 10, 1, "prefetch_amount"
        )
        vbox.add(prefetch_songs_box)

        # Max Concurrent Downloads
        (
            max_concurrent_downloads,
            self.max_concurrent_downloads_entry,
        ) = self._create_spin_button_menu_item(
            "Maximum Concurrent Downloads", 0, 10, 1, "concurrent_download_limit"
        )
        vbox.add(max_concurrent_downloads)

        main_menu.add(vbox)
        return main_menu

    def _create_search_popup(self) -> Gtk.PopoverMenu:
        self.search_popup = Gtk.PopoverMenu(modal=False)

        results_scrollbox = Gtk.ScrolledWindow(
            min_content_width=500, min_content_height=750,
        )

        def make_search_result_header(text: str) -> Gtk.Label:
            label = self._create_label(text)
            label.get_style_context().add_class("search-result-header")
            return label

        search_results_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, name="search-results",
        )
        self.search_results_loading = Gtk.Spinner(active=False, name="search-spinner")
        search_results_box.add(self.search_results_loading)

        search_results_box.add(make_search_result_header("Songs"))
        self.song_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.song_results)

        search_results_box.add(make_search_result_header("Albums"))
        self.album_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.album_results)

        search_results_box.add(make_search_result_header("Artists"))
        self.artist_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.artist_results)

        search_results_box.add(make_search_result_header("Playlists"))
        self.playlist_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.playlist_results)

        results_scrollbox.add(search_results_box)
        self.search_popup.add(results_scrollbox)

        self.search_popup.set_relative_to(self.search_entry)
        rect = Gdk.Rectangle()
        rect.x = 22
        rect.y = 28
        rect.width = 1
        rect.height = 1
        self.search_popup.set_pointing_to(rect)
        self.search_popup.set_position(Gtk.PositionType.BOTTOM)

    # Event Listeners
    # =========================================================================
    def _on_button_release(self, win: Any, event: Gdk.EventButton) -> bool:
        if not self._event_in_widgets(event, self.search_entry, self.search_popup):
            self._hide_search()

        if not self._event_in_widgets(
            event,
            self.player_controls.device_button,
            self.player_controls.device_popover,
        ):
            self.player_controls.device_popover.popdown()

        if not self._event_in_widgets(
            event,
            self.player_controls.play_queue_button,
            self.player_controls.play_queue_popover,
        ):
            self.player_controls.play_queue_popover.popdown()

        return False

    def _prompt_confirm_clear_cache(
        self, title: str, detail_text: str
    ) -> Gtk.ResponseType:
        confirm_dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
            text=title,
        )
        confirm_dialog.add_buttons(
            Gtk.STOCK_DELETE,
            Gtk.ResponseType.YES,
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
        )
        confirm_dialog.format_secondary_markup(detail_text)
        result = confirm_dialog.run()
        confirm_dialog.destroy()
        return result

    def _clear_song_file_cache(self, _):
        title = "Confirm Delete Song Files"
        detail_text = "Are you sure you want to delete all cached song files? Your song metadata will be preserved."  # noqa: 512
        if self._prompt_confirm_clear_cache(title, detail_text) == Gtk.ResponseType.YES:
            AdapterManager.clear_song_cache()
            self.emit("refresh-window", {}, True)

    def _clear_entire_cache(self, _):
        title = "Confirm Delete Song Files and Metadata"
        detail_text = "Are you sure you want to delete all cached song files and corresponding metadata?"  # noqa: 512
        if self._prompt_confirm_clear_cache(title, detail_text) == Gtk.ResponseType.YES:
            AdapterManager.clear_entire_cache()
            self.emit("refresh-window", {}, True)

    def _on_downloads_menu_clicked(self, *args):
        self.downloads_popover.popup()
        self.downloads_popover.show_all()

    def _on_server_connection_menu_clicked(self, *args):
        self.server_connection_popover.popup()
        self.server_connection_popover.show_all()

    def _on_main_menu_clicked(self, *args):
        self.main_menu_popover.popup()
        self.main_menu_popover.show_all()

    def _on_replay_gain_change(self, combo: Gtk.ComboBox):
        self._emit_settings_change(
            {"replay_gain": ReplayGainType.from_string(combo.get_active_id())}
        )

    def _on_edit_configuration_click(self, _):
        # TODO (#197): EDIT
        pass

    def _on_switch_provider_click(self, _):
        # TODO (#197): switch
        pass

    def _on_add_new_provider_click(self, _):
        # TODO (#197) add new
        pass

    def _on_search_entry_focus(self, *args):
        self._show_search()

    def _on_search_entry_button_press(self, *args):
        self._show_search()

    def _on_search_entry_loose_focus(self, *args):
        self._hide_search()

    search_idx = 0
    searches: Set[Result] = set()

    def _on_search_entry_changed(self, entry: Gtk.Entry):
        while len(self.searches) > 0:
            search = self.searches.pop()
            if search:
                search.cancel()

        if not self.search_popup.is_visible():
            self.search_popup.show_all()
            self.search_popup.popup()

        def search_result_calback(idx: int, result: API.SearchResult):
            # Ignore slow returned searches.
            if idx < self.search_idx:
                return

            GLib.idle_add(self._update_search_results, result)

        def search_result_done(r: Result):
            if r.result() is True:
                # The search was cancelled
                return

            # If all results are back, the stop the loading indicator.
            GLib.idle_add(self._set_search_loading, False)

        self.search_idx += 1
        search_result = AdapterManager.search(
            entry.get_text(),
            search_callback=partial(search_result_calback, self.search_idx),
            before_download=lambda: self._set_search_loading(True),
        )
        search_result.add_done_callback(search_result_done)
        self.searches.add(search_result)

    def _on_search_entry_stop_search(self, entry: Any):
        self.search_popup.popdown()

    # Helper Functions
    # =========================================================================
    def _emit_settings_change(self, changed_settings: Dict[str, Any]):
        if self._updating_settings:
            return
        self.emit("refresh-window", {"__settings__": changed_settings}, False)

    def _show_search(self):
        self.search_entry.set_size_request(300, -1)
        self.search_popup.show_all()
        self.search_results_loading.hide()
        self.search_popup.popup()

    def _hide_search(self):
        self.search_popup.popdown()
        self.search_entry.set_size_request(-1, -1)

    def _set_search_loading(self, loading_state: bool):
        if loading_state:
            self.search_results_loading.start()
            self.search_results_loading.show_all()
        else:
            self.search_results_loading.stop()
            self.search_results_loading.hide()

    def _remove_all_from_widget(self, widget: Gtk.Widget):
        for c in widget.get_children():
            widget.remove(c)

    def _create_search_result_row(
        self, text: str, action_name: str, id: str, cover_art_id: Optional[str]
    ) -> Gtk.Button:
        def on_search_row_button_press(*args):
            self.emit("go-to", action_name, id)
            self._hide_search()

        row = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        row.connect("button-press-event", on_search_row_button_press)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        image = SpinnerImage(image_name="search-artwork", image_size=30)
        box.add(image)
        box.add(self._create_label(text))
        row.add(box)

        def image_callback(f: Result):
            image.set_loading(False)
            image.set_from_file(f.result())

        artwork_future = AdapterManager.get_cover_art_filename(cover_art_id)
        artwork_future.add_done_callback(lambda f: GLib.idle_add(image_callback, f))

        return row

    def _update_search_results(self, search_results: API.SearchResult):
        # Songs
        if search_results.songs is not None:
            self._remove_all_from_widget(self.song_results)
            for song in search_results.songs:
                label_text = util.dot_join(
                    f"<b>{util.esc(song.title)}</b>",
                    util.esc(song.artist.name if song.artist else None),
                )
                assert song.album and song.album.id
                self.song_results.add(
                    self._create_search_result_row(
                        label_text, "album", song.album.id, song.cover_art
                    )
                )

            self.song_results.show_all()

        # Albums
        if search_results.albums is not None:
            self._remove_all_from_widget(self.album_results)
            for album in search_results.albums:
                label_text = util.dot_join(
                    f"<b>{util.esc(album.name)}</b>",
                    util.esc(album.artist.name if album.artist else None),
                )
                assert album.id
                self.album_results.add(
                    self._create_search_result_row(
                        label_text, "album", album.id, album.cover_art
                    )
                )

            self.album_results.show_all()

        # Artists
        if search_results.artists is not None:
            self._remove_all_from_widget(self.artist_results)
            for artist in search_results.artists:
                label_text = util.esc(artist.name)
                assert artist.id
                self.artist_results.add(
                    self._create_search_result_row(
                        label_text, "artist", artist.id, artist.artist_image_url
                    )
                )

            self.artist_results.show_all()

        # Playlists
        if search_results.playlists:
            self._remove_all_from_widget(self.playlist_results)
            for playlist in search_results.playlists:
                label_text = util.esc(playlist.name)
                self.playlist_results.add(
                    self._create_search_result_row(
                        label_text, "playlist", playlist.id, playlist.cover_art
                    )
                )

            self.playlist_results.show_all()

    def _event_in_widgets(self, event: Gdk.EventButton, *widgets) -> bool:
        for widget in widgets:
            if not widget.is_visible():
                continue

            _, win_x, win_y = Gdk.Window.get_origin(self.get_window())
            widget_x, widget_y = widget.translate_coordinates(self, 0, 0)
            allocation = widget.get_allocation()

            bound_x = (win_x + widget_x, win_x + widget_x + allocation.width)
            bound_y = (win_y + widget_y, win_y + widget_y + allocation.height)

            # If the event is in this widget, return True immediately.
            if (bound_x[0] <= event.x_root <= bound_x[1]) and (
                bound_y[0] <= event.y_root <= bound_y[1]
            ):
                return True

        return False


class DownloadStatusBox(Gtk.Box):
    __gsignals__ = {
        "cancel-clicked": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (str,),),
        "retry-clicked": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (str,),),
    }

    def __init__(self, song_id: str):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.song = AdapterManager.get_song_details(song_id).result()

        image = SpinnerImage(
            image_size=30, image_name="current-downloads-cover-art-image"
        )
        self.add(image)

        artist = util.esc(self.song.artist.name if self.song.artist else None)
        label_text = util.dot_join(f"<b>{util.esc(self.song.title)}</b>", artist)
        self.song_label = Gtk.Label(
            label=label_text,
            ellipsize=Pango.EllipsizeMode.END,
            max_width_chars=30,
            name="currently-downloading-song-title",
            use_markup=True,
            halign=Gtk.Align.START,
        )
        self.pack_start(self.song_label, True, True, 5)

        self.download_progress = Gtk.ProgressBar(show_text=True)
        self.add(self.download_progress)

        self.cancel_button = IconButton(
            "process-stop-symbolic", tooltip_text="Cancel download"
        )
        self.cancel_button.connect(
            "clicked", lambda *a: self.emit("cancel-clicked", self.song.id)
        )
        self.add(self.cancel_button)

        def image_callback(f: Result):
            image.set_loading(False)
            image.set_from_file(f.result())

        artwork_future = AdapterManager.get_cover_art_filename(self.song.cover_art)
        artwork_future.add_done_callback(lambda f: GLib.idle_add(image_callback, f))

    def update_progress(self, progress_fraction: float):
        self.download_progress.set_fraction(progress_fraction)
