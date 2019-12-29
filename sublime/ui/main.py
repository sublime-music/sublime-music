import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, GObject, Gdk, GLib

from . import albums, artists, playlists, player_controls
from sublime.state_manager import ApplicationState
from sublime.cache_manager import CacheManager
from sublime.server.api_objects import Child, AlbumWithSongsID3


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

    browse_by_tags: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_default_size(1150, 768)

        # Create the stack
        self.stack = self.create_stack(
            Albums=albums.AlbumsPanel(),
            Artists=artists.ArtistsPanel(),
            Playlists=playlists.PlaylistsPanel(),
        )
        self.stack.set_transition_type(
            Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        self.titlebar = self.create_headerbar(self.stack)
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

        self.connect('button-release-event', self.on_button_release)

    def update(self, state: ApplicationState, force=False):
        self.browse_by_tags = state.config.server.browse_by_tags

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

    def create_stack(self, **kwargs):
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

    def create_headerbar(self, stack):
        """
        Configure the header bar for the window.
        """
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.props.title = 'Sublime Music'

        # Search
        self.search_entry = Gtk.SearchEntry(
            placeholder_text='Search everything...')
        self.search_entry.connect('focus-in-event', self.on_search_entry_focus)
        self.search_entry.connect(
            'focus-out-event', self.on_search_entry_loose_focus)
        self.search_entry.connect('changed', self.on_search_entry_changed)
        self.search_entry.connect(
            'stop-search', self.on_search_entry_stop_search)
        header.pack_start(self.search_entry)

        # Search popup
        self.create_search_popup()

        # Stack switcher
        switcher = Gtk.StackSwitcher(stack=stack)
        header.set_custom_title(switcher)

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_use_popover(True)
        menu_button.set_popover(self.create_menu())
        menu_button.connect('clicked', self.on_menu_clicked)
        self.menu.set_relative_to(menu_button)

        icon = Gio.ThemedIcon(name='open-menu-symbolic')
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        menu_button.add(image)

        header.pack_end(menu_button)

        return header

    def create_label(self, text, *args, **kwargs):
        label = Gtk.Label(
            label=text,
            halign=Gtk.Align.START,
            *args,
            **kwargs,
        )
        label.get_style_context().add_class('search-result-row')
        return label

    def create_menu(self):
        self.menu = Gtk.PopoverMenu()

        self.connected_to_label = self.create_label(
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

    def create_search_popup(self):
        self.search_popup = Gtk.PopoverMenu(modal=False)

        def make_search_result_header(text):
            label = self.create_label(text)
            label.get_style_context().add_class('search-result-header')
            return label

        search_results_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            name='search-results',
        )

        search_results_box.add(make_search_result_header('Songs'))
        self.song_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.song_results)

        search_results_box.add(make_search_result_header('Album'))
        self.album_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.album_results)

        search_results_box.add(make_search_result_header('Artists'))
        self.artist_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.artist_results)

        search_results_box.add(make_search_result_header('Playlists'))
        self.playlists_results = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_results_box.add(self.playlists_results)

        self.search_popup.add(search_results_box)

        self.search_popup.set_relative_to(self.search_entry)
        rect = Gdk.Rectangle()
        rect.x = 18
        rect.y = 30
        rect.width = 1
        rect.height = 1
        self.search_popup.set_pointing_to(rect)
        self.search_popup.set_position(Gtk.PositionType.BOTTOM)

    # Event Listeners
    # =========================================================================
    def on_button_release(self, win, event):
        if not self.event_in_widgets(
                event,
                self.search_entry,
                self.search_popup,
        ):
            self.search_popup.popdown()

        if not self.event_in_widgets(
                event,
                self.player_controls.device_button,
                self.player_controls.device_popover,
        ):
            self.player_controls.device_popover.popdown()

        if not self.event_in_widgets(
                event,
                self.player_controls.play_queue_button,
                self.player_controls.play_queue_popover,
        ):
            self.player_controls.play_queue_popover.popdown()

        return False

    def on_menu_clicked(self, button):
        self.menu.popup()
        self.menu.show_all()

    def on_search_entry_focus(self, entry, event):
        self.search_popup.show_all()
        self.search_popup.popup()

    def on_search_entry_loose_focus(self, entry, event):
        self.search_popup.popdown()

    search_idx = 0
    latest_returned_search_idx = 0

    def on_search_entry_changed(self, entry):
        if not self.search_popup.is_visible():
            self.search_popup.show_all()
            self.search_popup.popup()

        def create_search_callback(idx):
            def search_done(f):
                # Ignore slow returned searches.
                if idx < self.latest_returned_search_idx:
                    return
                self.latest_returned_search_idx = idx

                self.update_search_results(f.result())

            return lambda f: GLib.idle_add(search_done, f)

        search_fn = (
            CacheManager.search3
            if self.browse_by_tags else CacheManager.search2)
        search_future = search_fn(entry.get_text())
        search_future.add_done_callback(
            create_search_callback(self.search_idx))

        self.search_idx += 1

    def on_search_entry_stop_search(self, entry):
        self.search_popup.popdown()

    # Helper Functions
    # =========================================================================
    def remove_all_from_widget(self, widget):
        for c in widget.get_children():
            widget.remove(c)

    def create_search_result_row(self, text, action_name, value):
        row = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        row.add(self.create_label(text))
        row.connect(
            'button-press-event',
            lambda *a: self.emit('go-to', action_name, value),
        )
        return row

    def update_search_results(self, search_results):
        # Albums
        self.remove_all_from_widget(self.album_results)
        for album in search_results.album or []:
            name = album.title if type(album) == Child else album.name
            self.album_results.add(
                self.create_search_result_row(name, 'album', album.id))

        # Artists
        self.remove_all_from_widget(self.artist_results)
        for artist in search_results.artist or []:
            self.artist_results.add(
                self.create_search_result_row(
                    artist.name, 'artist', artist.id))

        # Songs
        self.remove_all_from_widget(self.song_results)
        for song in search_results.song or []:
            self.song_results.add(
                self.create_search_result_row(
                    song.title, 'album', song.albumId))

        self.search_popup.show_all()

    def event_in_widgets(self, event, *widgets):
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
