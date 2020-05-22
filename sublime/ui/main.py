from functools import partial
from typing import Any, Callable, Optional, Set

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from sublime.adapters import AdapterManager, api_objects as API, Result
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(1150, 768)

        # Create the stack
        self.stack = self._create_stack(
            Albums=albums.AlbumsPanel(),
            Artists=artists.ArtistsPanel(),
            Browse=browse.BrowsePanel(),
            Playlists=playlists.PlaylistsPanel(),
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

        self.notification_text = Gtk.Label(use_markup=True)
        notification_box.pack_start(self.notification_text, True, False, 0)

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
        # if app_config.server:
        #     self.connected_to_label.set_markup(
        #         f"<b>Connected to {app_config.server.name}</b>"
        #     )
        # else:
        #     self.connected_to_label.set_markup(
        #         '<span style="italic">Not Connected to a Server</span>'
        #     )

        self._updating_settings = True

        self.offline_mode_switch.set_active(app_config.offline_mode)
        self.notification_switch.set_active(app_config.song_play_notification)
        self.replay_gain_options.set_active_id(app_config.replay_gain.as_string())
        self.serve_over_lan_switch.set_active(app_config.serve_over_lan)
        self.port_number_entry.set_value(app_config.port_number)

        self._updating_settings = False

        self.stack.set_visible_child_name(app_config.state.current_tab)

        active_panel = self.stack.get_visible_child()
        if hasattr(active_panel, "update"):
            active_panel.update(app_config, force=force)

        self.player_controls.update(app_config)

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
            name="server-connection-icon",
            icon_image_filename="/home/sumner/tmp/server-subsonic-symbolic.svg",
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

    def _create_label(self, text: str, *args, **kwargs) -> Gtk.Label:
        label = Gtk.Label(
            use_markup=True,
            halign=Gtk.Align.START,
            ellipsize=Pango.EllipsizeMode.END,
            *args,
            **kwargs,
        )
        label.set_markup(text)
        label.get_style_context().add_class("search-result-row")
        return label

    def _create_downloads_popover(self) -> Gtk.PopoverMenu:
        menu = Gtk.PopoverMenu()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="main-menu-box")

        download_settings = Gtk.ModelButton(
            text="Clear Cache", menu_name="clear-cache", name="menu-item-clear-cache",
        )
        download_settings.get_style_context().add_class("menu-button")
        vbox.add(download_settings)

        menu.add(vbox)
        return menu

    def _create_server_connection_popover(self) -> Gtk.PopoverMenu:
        menu = Gtk.PopoverMenu()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        menu.add(vbox)
        return menu

    def _create_main_menu(self) -> Gtk.PopoverMenu:
        main_menu = Gtk.PopoverMenu()
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="main-menu-box")

        # TODO
        # Current Server
        # current_server_box = Gtk.Box(name="connected-to-box")

        # self.connected_to_label = self._create_label("")
        # self.connected_to_label.set_markup(
        #     '<span style="italic">Not connected to any music source</span>'
        # )
        # current_server_box.add(self.connected_to_label)

        # edit_button = IconButton("document-edit-symbolic", "Edit the current server")
        # edit_button.connect("clicked", lambda _: print("edit"))  # TODO
        # current_server_box.pack_end(edit_button, False, False, 5)

        # vbox.add(current_server_box)

        # # Music Source
        # switch_source_button = Gtk.ModelButton(
        #     text="Switch Music Source",
        #     menu_name="switch-source",
        #     name="menu-item-switch-source",
        # )
        # switch_source_button.get_style_context().add_class("menu-button")
        # vbox.add(switch_source_button)

        # vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Offline Mode
        offline_box, self.offline_mode_switch = self._create_toggle_menu_button(
            "Offline Mode", "offline_mode"
        )
        vbox.add(offline_box)

        download_settings = Gtk.ModelButton(
            text="Download Settings",
            menu_name="download-settings",
            name="menu-item-download-settings",
        )
        download_settings.get_style_context().add_class("menu-button")
        vbox.add(download_settings)

        vbox.add(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Notifications
        notifications_box, self.notification_switch = self._create_toggle_menu_button(
            "Notifications", "song_play_notification"
        )
        vbox.add(notifications_box)

        # Replay Gain
        replay_gain_box = Gtk.Box()
        replay_gain_box.add(Gtk.Label(label="Replay Gain"))

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

        # Serve Local Files to Chromecast
        serve_over_lan, self.serve_over_lan_switch = self._create_toggle_menu_button(
            "Serve Local Files to Devices on the LAN", "serve_over_lan"
        )
        vbox.add(serve_over_lan)

        # Server Port
        server_port_box = Gtk.Box()
        server_port_box.add(Gtk.Label(label="LAN Server Port Number"))

        self.port_number_entry = Gtk.SpinButton.new_with_range(8000, 9000, 1)
        server_port_box.pack_end(self.port_number_entry, False, False, 0)
        server_port_box.get_style_context().add_class("menu-button")

        vbox.add(server_port_box)

        menu_items = [
            ("app.configure-servers", Gtk.ModelButton(text="Configure Servers")),
            ("app.settings", Gtk.ModelButton(text="Settings")),
        ]

        for name, item in menu_items:
            if name:
                item.set_action_name(name)
            item.get_style_context().add_class("menu-button")
            vbox.pack_start(item, False, True, 0)

        main_menu.add(vbox)
        return main_menu

    def _create_toggle_menu_button(self, label: str, settings_name: str) -> Gtk.Box:
        def on_active_change(toggle: Gtk.Switch, _):
            self._emit_settings_change(**{settings_name: toggle.get_active()})

        box = Gtk.Box()
        box.add(Gtk.Label(label=label))
        switch = Gtk.Switch(active=True)
        switch.connect("notify::active", on_active_change)
        box.pack_end(switch, False, False, 0)
        box.get_style_context().add_class("menu-button")
        return box, switch

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
            replay_gain=ReplayGainType.from_string(combo.get_active_id())
        )

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
            if not r.result():
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
    def _emit_settings_change(self, **kwargs):
        if self._updating_settings:
            return
        self.emit("refresh-window", {"__settings__": kwargs}, False)

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
