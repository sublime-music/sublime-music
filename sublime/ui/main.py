from datetime import datetime
from typing import Any, Callable, Set

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from sublime.cache_manager import CacheManager, SearchResult
from sublime.state_manager import ApplicationState
from sublime.ui import (
    albums, artists, browse, player_controls, playlists, util)
from sublime.ui.common import SpinnerImage


class MainWindow(Gtk.ApplicationWindow):
    """Defines the main window for Sublime Music."""
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        'songs-removed': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, ),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
        'go-to': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, str),
        ),
    }

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
        self.stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.titlebar = self._create_headerbar(self.stack)
        self.set_titlebar(self.titlebar)

        self.player_controls = player_controls.PlayerControls()
        self.player_controls.connect(
            'song-clicked', lambda _, *a: self.emit('song-clicked', *a))
        self.player_controls.connect(
            'songs-removed', lambda _, *a: self.emit('songs-removed', *a))
        self.player_controls.connect(
            'refresh-window',
            lambda _, *args: self.emit('refresh-window', *args),
        )

        flowbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        flowbox.pack_start(self.stack, True, True, 0)
        flowbox.pack_start(self.player_controls, False, True, 0)
        self.add(flowbox)

        self.connect('button-release-event', self._on_button_release)

    def update(self, state: ApplicationState, force: bool = False):
        # Update the Connected to label on the popup menu.
        if state.config.current_server >= 0:
            server_name = state.config.servers[
                state.config.current_server].name
            self.connected_to_label.set_markup(
                f'<b>Connected to {server_name}</b>')
        else:
            self.connected_to_label.set_markup(
                f'<span style="italic">Not Connected to a Server</span>')

        self.stack.set_visible_child_name(state.current_tab)

        active_panel = self.stack.get_visible_child()
        if hasattr(active_panel, 'update'):
            active_panel.update(state, force=force)

        self.player_controls.update(state)

    def _create_stack(self, **kwargs: Gtk.Widget) -> Gtk.Stack:
        stack = Gtk.Stack()
        for name, child in kwargs.items():
            child.connect(
                'song-clicked',
                lambda _, *args: self.emit('song-clicked', *args),
            )
            child.connect(
                'refresh-window',
                lambda _, *args: self.emit('refresh-window', *args),
            )
            stack.add_titled(child, name.lower(), name)
        return stack

    def _create_headerbar(self, stack: Gtk.Stack) -> Gtk.HeaderBar:
        """
        Configure the header bar for the window.
        """
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = 'Sublime Music'

        # Search
        self.search_entry = Gtk.SearchEntry(
            placeholder_text='Search everything...')
        self.search_entry.connect(
            'focus-in-event', self._on_search_entry_focus)
        self.search_entry.connect(
            'button-press-event', self._on_search_entry_button_press)
        self.search_entry.connect(
            'focus-out-event', self._on_search_entry_loose_focus)
        self.search_entry.connect('changed', self._on_search_entry_changed)
        self.search_entry.connect(
            'stop-search', self._on_search_entry_stop_search)
        header.pack_start(self.search_entry)

        # Search popup
        self._create_search_popup()

        # Stack switcher
        switcher = Gtk.StackSwitcher(stack=stack)
        header.set_custom_title(switcher)

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_tooltip_text('Open application menu')
        menu_button.set_use_popover(True)
        menu_button.set_popover(self._create_menu())
        menu_button.connect('clicked', self._on_menu_clicked)
        self.menu.set_relative_to(menu_button)

        icon = Gio.ThemedIcon(name='open-menu-symbolic')
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        menu_button.add(image)

        header.pack_end(menu_button)

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
        label.get_style_context().add_class('search-result-row')
        return label

    def _create_menu(self) -> Gtk.PopoverMenu:
        self.menu = Gtk.PopoverMenu()

        self.connected_to_label = self._create_label(
            '', name='connected-to-label')
        self.connected_to_label.set_markup(
            f'<span style="italic">Not Connected to a Server</span>')

        menu_items = [
            (None, self.connected_to_label),
            (
                'app.configure-servers',
                Gtk.ModelButton(text='Configure Servers'),
            ),
            ('app.settings', Gtk.ModelButton(text='Settings')),
        ]

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for name, item in menu_items:
            if name:
                item.set_action_name(name)
            item.get_style_context().add_class('menu-button')
            vbox.pack_start(item, False, True, 0)
        self.menu.add(vbox)

        return self.menu

    def _create_search_popup(self) -> Gtk.PopoverMenu:
        self.search_popup = Gtk.PopoverMenu(modal=False)

        results_scrollbox = Gtk.ScrolledWindow(
            min_content_width=500,
            min_content_height=750,
        )

        def make_search_result_header(text: str) -> Gtk.Label:
            label = self._create_label(text)
            label.get_style_context().add_class('search-result-header')
            return label

        search_results_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name='search-results',
        )
        self.search_results_loading = Gtk.Spinner(
            active=False, name='search-spinner')
        search_results_box.add(self.search_results_loading)

        search_results_box.add(make_search_result_header('Songs'))
        self.song_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.song_results)

        search_results_box.add(make_search_result_header('Albums'))
        self.album_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.album_results)

        search_results_box.add(make_search_result_header('Artists'))
        self.artist_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.artist_results)

        search_results_box.add(make_search_result_header('Playlists'))
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
        if not self._event_in_widgets(
                event,
                self.search_entry,
                self.search_popup,
        ):
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

    def _on_menu_clicked(self, *args):
        self.menu.popup()
        self.menu.show_all()

    def _on_search_entry_focus(self, *args):
        self._show_search()

    def _on_search_entry_button_press(self, *args):
        self._show_search()

    def _on_search_entry_loose_focus(self, *args):
        self._hide_search()

    search_idx = 0
    latest_returned_search_idx = 0
    last_search_change_time = datetime.now()
    searches: Set[CacheManager.Result] = set()

    def _on_search_entry_changed(self, entry: Gtk.Entry):
        now = datetime.now()
        if (now - self.last_search_change_time).seconds < 0.5:
            while len(self.searches) > 0:
                search = self.searches.pop()
                if search:
                    search.cancel()
        self.last_search_change_time = now

        if not self.search_popup.is_visible():
            self.search_popup.show_all()
            self.search_popup.popup()

        def create_search_callback(idx: int) -> Callable[..., Any]:
            def search_result_calback(
                result: SearchResult,
                is_last_in_batch: bool,
            ):
                # Ignore slow returned searches.
                if idx < self.latest_returned_search_idx:
                    return

                # If all results are back, the stop the loading indicator.
                if is_last_in_batch:
                    if idx == self.search_idx - 1:
                        self._set_search_loading(False)
                    self.latest_returned_search_idx = idx

                self._update_search_results(result)

            return lambda *a: GLib.idle_add(search_result_calback, *a)

        self.searches.add(
            CacheManager.search(
                entry.get_text(),
                search_callback=create_search_callback(self.search_idx),
                before_download=lambda: self._set_search_loading(True),
            ))

        self.search_idx += 1

    def _on_search_entry_stop_search(self, entry: Any):
        self.search_popup.popdown()

    # Helper Functions
    # =========================================================================
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
            self,
            text: str,
            action_name: str,
            value: Any,
            artwork_future: CacheManager.Result,
    ) -> Gtk.Button:
        def on_search_row_button_press(*args):
            if action_name == 'song':
                goto_action_name, goto_id = 'album', value.albumId
            else:
                goto_action_name, goto_id = action_name, value.id
            self.emit('go-to', goto_action_name, goto_id)
            self._hide_search()

        row = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        row.connect('button-press-event', on_search_row_button_press)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        image = SpinnerImage(image_name='search-artwork', image_size=30)
        box.add(image)
        box.add(self._create_label(text))
        row.add(box)

        def image_callback(f: CacheManager.Result):
            image.set_loading(False)
            image.set_from_file(f.result())

        artwork_future.add_done_callback(
            lambda f: GLib.idle_add(image_callback, f))

        return row

    def _update_search_results(self, search_results: SearchResult):
        # Songs
        if search_results.song is not None:
            self._remove_all_from_widget(self.song_results)
            for song in search_results.song or []:
                label_text = util.dot_join(
                    f'<b>{util.esc(song.title)}</b>',
                    util.esc(song.artist),
                )
                cover_art_future = CacheManager.get_cover_art_filename(
                    song.coverArt)
                self.song_results.add(
                    self._create_search_result_row(
                        label_text, 'song', song, cover_art_future))

            self.song_results.show_all()

        # Albums
        if search_results.album is not None:
            self._remove_all_from_widget(self.album_results)
            for album in search_results.album or []:
                label_text = util.dot_join(
                    f'<b>{util.esc(album.name)}</b>',
                    util.esc(album.artist),
                )
                cover_art_future = CacheManager.get_cover_art_filename(
                    album.coverArt)
                self.album_results.add(
                    self._create_search_result_row(
                        label_text, 'album', album, cover_art_future))

            self.album_results.show_all()

        # Artists
        if search_results.artist is not None:
            self._remove_all_from_widget(self.artist_results)
            for artist in search_results.artist or []:
                label_text = util.esc(artist.name)
                cover_art_future = CacheManager.get_artist_artwork(artist)
                self.artist_results.add(
                    self._create_search_result_row(
                        label_text, 'artist', artist, cover_art_future))

            self.artist_results.show_all()

        # Playlists
        if search_results.playlist is not None:
            self._remove_all_from_widget(self.playlist_results)
            for playlist in search_results.playlist or []:
                label_text = util.esc(playlist.name)
                cover_art_future = CacheManager.get_cover_art_filename(
                    playlist.coverArt)
                self.playlist_results.add(
                    self._create_search_result_row(
                        label_text, 'playlist', playlist, cover_art_future))

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
            if ((bound_x[0] <= event.x_root <= bound_x[1])
                    and (bound_y[0] <= event.y_root <= bound_y[1])):
                return True

        return False
