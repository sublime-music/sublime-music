from functools import lru_cache
from random import randint
from typing import List

from fuzzywuzzy import process

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, Pango, GObject, GLib

from sublime.server.api_objects import PlaylistWithSongs
from sublime.state_manager import ApplicationState
from sublime.cache_manager import CacheManager
from sublime.ui import util
from sublime.ui.common import EditFormDialog, IconButton, SpinnerImage


class EditPlaylistDialog(EditFormDialog):
    entity_name: str = 'Playlist'
    initial_size = (350, 120)
    text_fields = [('Name', 'name', False), ('Comment', 'comment', False)]
    boolean_fields = [('Public', 'public')]

    def __init__(self, *args, playlist_id=None, **kwargs):
        delete_playlist = Gtk.Button(label='Delete Playlist')
        self.extra_buttons = [(delete_playlist, Gtk.ResponseType.DELETE_EVENT)]
        super().__init__(*args, **kwargs)


class PlaylistsPanel(Gtk.Paned):
    """Defines the playlists panel."""
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object, object),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    def __init__(self, *args, **kwargs):
        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.playlist_list = PlaylistList()
        self.pack1(self.playlist_list, False, False)

        self.playlist_detail_panel = PlaylistDetailPanel()
        self.playlist_detail_panel.connect(
            'song-clicked',
            lambda _, *args: self.emit('song-clicked', *args),
        )
        self.playlist_detail_panel.connect(
            'refresh-window',
            lambda _, *args: self.emit('refresh-window', *args),
        )
        self.pack2(self.playlist_detail_panel, True, False)

    def update(self, state: ApplicationState = None, force=False):
        self.playlist_list.update(state=state)
        self.playlist_detail_panel.update(state=state)


class PlaylistList(Gtk.Box):
    __gsignals__ = {
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    class PlaylistModel(GObject.GObject):
        playlist_id = GObject.Property(type=str)
        name = GObject.Property(type=str)

        def __init__(self, playlist_id, name):
            GObject.GObject.__init__(self)
            self.playlist_id = playlist_id
            self.name = name

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        playlist_list_actions = Gtk.ActionBar()

        new_playlist_button = IconButton('list-add', label='New Playlist')
        new_playlist_button.connect('clicked', self.on_new_playlist_clicked)
        playlist_list_actions.pack_start(new_playlist_button)

        list_refresh_button = IconButton('view-refresh')
        list_refresh_button.connect('clicked', self.on_list_refresh_click)
        playlist_list_actions.pack_end(list_refresh_button)

        self.add(playlist_list_actions)

        loading_new_playlist = Gtk.ListBox()

        self.loading_indicator = Gtk.ListBoxRow(
            activatable=False,
            selectable=False,
        )
        loading_spinner = Gtk.Spinner(
            name='playlist-list-spinner', active=True)
        self.loading_indicator.add(loading_spinner)
        loading_new_playlist.add(self.loading_indicator)

        self.new_playlist_row = Gtk.ListBoxRow(
            activatable=False, selectable=False)
        new_playlist_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, visible=False)

        self.new_playlist_entry = Gtk.Entry(
            name='playlist-list-new-playlist-entry')
        self.new_playlist_entry.connect('activate', self.new_entry_activate)
        new_playlist_box.add(self.new_playlist_entry)

        new_playlist_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        confirm_button = IconButton(
            'object-select-symbolic',
            name='playlist-list-new-playlist-confirm',
            relief=True,
        )
        confirm_button.connect('clicked', self.confirm_button_clicked)
        new_playlist_actions.pack_end(confirm_button, False, True, 0)

        self.cancel_button = IconButton(
            'process-stop-symbolic',
            name='playlist-list-new-playlist-cancel',
            relief=True,
        )
        self.cancel_button.connect('clicked', self.cancel_button_clicked)
        new_playlist_actions.pack_end(self.cancel_button, False, True, 0)

        new_playlist_box.add(new_playlist_actions)
        self.new_playlist_row.add(new_playlist_box)

        loading_new_playlist.add(self.new_playlist_row)
        self.add(loading_new_playlist)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=220)

        def create_playlist_row(model: PlaylistList.PlaylistModel):
            row = Gtk.ListBoxRow(
                action_name='app.go-to-playlist',
                action_target=GLib.Variant('s', model.playlist_id),
            )
            row.add(
                Gtk.Label(
                    label=f'<b>{model.name}</b>',
                    use_markup=True,
                    margin=12,
                    halign=Gtk.Align.START,
                    ellipsize=Pango.EllipsizeMode.END,
                    max_width_chars=30,
                ))
            row.show_all()
            return row

        self.playlists_store = Gio.ListStore()
        self.list = Gtk.ListBox(name='playlist-list-listbox')
        self.list.bind_model(self.playlists_store, create_playlist_row)
        list_scroll_window.add(self.list)
        self.pack_start(list_scroll_window, True, True, 0)

    def update(self, **kwargs):
        self.new_playlist_row.hide()
        self.update_list(**kwargs)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlists(*a, **k),
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_list(
            self,
            playlists: List[PlaylistWithSongs],
            state: ApplicationState,
    ):
        new_store = []
        selected_idx = None
        for i, playlist in enumerate(playlists):
            if state and state.selected_playlist_id == playlist.id:
                selected_idx = i

            new_store.append(
                PlaylistList.PlaylistModel(playlist.id, playlist.name))

        util.diff_model_store(self.playlists_store, new_store)

        # Preserve selection
        if selected_idx is not None:
            row = self.list.get_row_at_index(selected_idx)
            self.list.select_row(row)

        self.loading_indicator.hide()

    # Event Handlers
    # =========================================================================
    def on_new_playlist_clicked(self, new_playlist_button):
        self.new_playlist_entry.set_text('Untitled Playlist')
        self.new_playlist_entry.grab_focus()
        self.new_playlist_row.show()

    def on_list_refresh_click(self, button):
        self.update(force=True)

    def new_entry_activate(self, entry):
        self.create_playlist(entry.get_text())

    def cancel_button_clicked(self, button):
        self.new_playlist_row.hide()

    def confirm_button_clicked(self, button):
        self.create_playlist(self.new_playlist_entry.get_text())

    def create_playlist(self, playlist_name):
        def on_playlist_created(f):
            print(f)
            CacheManager.invalidate_playlists_cache()
            self.update(force=True)

        self.loading_indicator.show()
        playlist_ceate_future = CacheManager.create_playlist(
            name=playlist_name)
        playlist_ceate_future.add_done_callback(
            lambda f: GLib.idle_add(on_playlist_created, f))


class PlaylistDetailPanel(Gtk.Overlay):
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (str, object, object),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    playlist_id = None

    editing_playlist_song_list: bool = False
    reordering_playlist_song_list: bool = False

    def __init__(self):
        Gtk.Overlay.__init__(self, name='playlist-view-overlay')
        playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Playlist info panel
        # TODO shrink when playlist is is scrolled down.
        self.big_info_panel = Gtk.Box(
            name='playlist-info-panel',
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        self.playlist_artwork = SpinnerImage(
            image_name='playlist-album-artwork',
            spinner_name='playlist-artwork-spinner',
        )
        self.big_info_panel.pack_start(self.playlist_artwork, False, False, 0)

        # Action buttons, name, comment, number of songs, etc.
        playlist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Action buttons (note we are packing end here, so we have to put them
        # in right-to-left).
        self.playlist_action_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL)

        view_refresh_button = IconButton('view-refresh-symbolic')
        view_refresh_button.connect('clicked', self.on_view_refresh_click)
        self.playlist_action_buttons.pack_end(
            view_refresh_button, False, False, 5)

        playlist_edit_button = IconButton('document-edit-symbolic')
        playlist_edit_button.connect(
            'clicked', self.on_playlist_edit_button_click)
        self.playlist_action_buttons.pack_end(
            playlist_edit_button, False, False, 5)

        download_all_button = IconButton('folder-download-symbolic')
        download_all_button.connect(
            'clicked', self.on_playlist_list_download_all_button_click)
        self.playlist_action_buttons.pack_end(
            download_all_button, False, False, 5)

        playlist_details_box.pack_start(
            self.playlist_action_buttons, False, False, 5)

        playlist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.playlist_indicator = self.make_label(name='playlist-indicator')
        playlist_details_box.add(self.playlist_indicator)

        self.playlist_name = self.make_label(name='playlist-name')
        playlist_details_box.add(self.playlist_name)

        self.playlist_comment = self.make_label(name='playlist-comment')
        playlist_details_box.add(self.playlist_comment)

        self.playlist_stats = self.make_label(name='playlist-stats')
        playlist_details_box.add(self.playlist_stats)

        self.play_shuffle_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            name='playlist-play-shuffle-buttons',
        )

        play_button = IconButton(
            'media-playback-start-symbolic',
            label='Play All',
            relief=True,
        )
        play_button.connect('clicked', self.on_play_all_clicked)
        self.play_shuffle_buttons.pack_start(play_button, False, False, 0)

        shuffle_button = IconButton(
            'media-playlist-shuffle-symbolic',
            label='Shuffle All',
            relief=True,
        )
        shuffle_button.connect('clicked', self.on_shuffle_all_button)
        self.play_shuffle_buttons.pack_start(shuffle_button, False, False, 5)

        playlist_details_box.add(self.play_shuffle_buttons)

        self.big_info_panel.pack_start(playlist_details_box, True, True, 10)

        playlist_box.pack_start(self.big_info_panel, False, True, 0)

        # Playlist songs list
        playlist_view_scroll_window = Gtk.ScrolledWindow()

        def create_column(header, text_idx, bold=False, align=0, width=None):
            renderer = Gtk.CellRendererText(
                xalign=align,
                weight=Pango.Weight.BOLD if bold else Pango.Weight.NORMAL,
                ellipsize=Pango.EllipsizeMode.END,
            )
            renderer.set_fixed_size(width or -1, 35)

            column = Gtk.TreeViewColumn(header, renderer, text=text_idx)
            column.set_resizable(True)
            column.set_expand(not width)
            return column

        self.playlist_song_store = Gtk.ListStore(
            str,  # cache status
            str,  # title
            str,  # album
            str,  # artist
            str,  # duration
            str,  # song ID
        )

        @lru_cache(maxsize=1024)
        def row_score(key, row_items):
            return max(map(lambda m: m[1], process.extract(key, row_items)))

        @lru_cache()
        def max_score_for_key(key, rows):
            return max(row_score(key, row) for row in rows)

        def playlist_song_list_search_fn(model, col, key, treeiter, data=None):
            # TODO: this is very inefficient, it's slow when the result is
            # close to the bottom of the list. Would be good to research what
            # the default one does (maybe it uses an index?).
            max_score = max_score_for_key(
                key, tuple(tuple(row[1:4]) for row in model))
            row_max_score = row_score(key, tuple(model[treeiter][1:4]))
            if row_max_score == max_score:
                return False  # indicates match
            return True

        self.playlist_songs = Gtk.TreeView(
            model=self.playlist_song_store,
            reorderable=True,
            margin_top=15,
            enable_search=True,
        )
        self.playlist_songs.set_search_equal_func(playlist_song_list_search_fn)
        self.playlist_songs.get_selection().set_mode(
            Gtk.SelectionMode.MULTIPLE)

        # TODO: add playing/menu column which shows whether a song is playing,
        # and when hovered shows a 3-dot menu (the same as right click menu).

        # Song status column.
        renderer = Gtk.CellRendererPixbuf()
        renderer.set_fixed_size(30, 35)
        column = Gtk.TreeViewColumn('', renderer, icon_name=0)
        column.set_resizable(True)
        self.playlist_songs.append_column(column)

        self.playlist_songs.append_column(create_column('TITLE', 1, bold=True))
        self.playlist_songs.append_column(create_column('ALBUM', 2))
        self.playlist_songs.append_column(create_column('ARTIST', 3))
        self.playlist_songs.append_column(
            create_column('DURATION', 4, align=1, width=40))

        self.playlist_songs.connect('row-activated', self.on_song_activated)
        self.playlist_songs.connect(
            'button-press-event', self.on_song_button_press)

        # Set up drag-and-drop on the song list for editing the order of the
        # playlist.
        self.playlist_song_store.connect(
            'row-inserted', self.playlist_model_row_move)
        self.playlist_song_store.connect(
            'row-deleted', self.playlist_model_row_move)

        playlist_view_scroll_window.add(self.playlist_songs)

        playlist_box.pack_end(playlist_view_scroll_window, True, True, 0)
        self.add(playlist_box)

        playlist_view_spinner = Gtk.Spinner(active=True)
        playlist_view_spinner.start()

        self.playlist_view_loading_box = Gtk.Alignment(
            name='playlist-view-overlay',
            xalign=0.5,
            yalign=0.5,
            xscale=0.1,
            yscale=0.1)
        self.playlist_view_loading_box.add(playlist_view_spinner)
        self.add_overlay(self.playlist_view_loading_box)

    def update(self, state: ApplicationState):
        if state.selected_playlist_id is None:
            self.playlist_artwork.set_from_file(None)
            self.playlist_indicator.set_markup('')
            self.playlist_name.set_markup('')
            self.playlist_comment.hide()
            self.playlist_stats.set_markup('')
            self.playlist_action_buttons.hide()
            self.play_shuffle_buttons.hide()
            self.playlist_view_loading_box.hide()
            self.playlist_artwork.set_loading(False)
        else:
            self.update_playlist_view(state.selected_playlist_id, state=state)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlist(*a, **k),
        before_download=lambda self: self.playlist_view_loading_box.show_all(),
        on_failure=lambda self, e: self.playlist_view_loading_box.hide(),
    )
    def update_playlist_view(
            self,
            playlist,
            state: ApplicationState = None,
            force=False,
    ):
        if self.playlist_id != playlist.id:
            self.playlist_songs.get_selection().unselect_all()

        self.playlist_id = playlist.id

        # Update the info display.
        self.playlist_indicator.set_markup('PLAYLIST')
        self.playlist_name.set_markup(f'<b>{playlist.name}</b>')
        if playlist.comment:
            self.playlist_comment.set_text(playlist.comment)
            self.playlist_comment.show()
        else:
            self.playlist_comment.hide()
        self.playlist_stats.set_markup(self.format_stats(playlist))

        # Update the artwork.
        self.update_playlist_artwork(playlist.coverArt)

        # Update the song list model. This requires some fancy diffing to
        # update the list.
        self.editing_playlist_song_list = True

        new_store = [
            [
                util.get_cached_status_icon(
                    CacheManager.get_cached_status(song)),
                song.title,
                song.album,
                song.artist,
                util.format_song_duration(song.duration),
                song.id,
            ] for song in (playlist.entry or [])
        ]

        util.diff_song_store(self.playlist_song_store, new_store)

        self.editing_playlist_song_list = False

        self.playlist_view_loading_box.hide()
        self.playlist_action_buttons.show_all()
        self.play_shuffle_buttons.show_all()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_cover_art_filename(*a, **k),
        before_download=lambda self: self.playlist_artwork.set_loading(True),
        on_failure=lambda self, e: self.playlist_artwork.set_loading(False),
    )
    def update_playlist_artwork(
            self,
            cover_art_filename,
            state: ApplicationState,
    ):
        self.playlist_artwork.set_from_file(cover_art_filename)
        self.playlist_artwork.set_loading(False)

    # Event Handlers
    # =========================================================================
    def on_view_refresh_click(self, button):
        self.update_playlist_view(self.playlist_id, force=True)

    def on_playlist_edit_button_click(self, button):
        dialog = EditPlaylistDialog(
            self.get_toplevel(),
            CacheManager.get_playlist(self.playlist_id).result(),
            playlist_id=self.playlist_id,
        )

        result = dialog.run()
        if result in (Gtk.ResponseType.OK, Gtk.ResponseType.DELETE_EVENT):
            if result == Gtk.ResponseType.OK:
                CacheManager.update_playlist(
                    self.playlist_id,
                    name=dialog.data['name'].get_text(),
                    comment=dialog.data['comment'].get_text(),
                    public=dialog.data['public'].get_active(),
                )
            elif result == Gtk.ResponseType.DELETE_EVENT:
                # Delete the playlist.
                CacheManager.delete_playlist(self.playlist_id)

            # Invalidate the caches and force a re-fresh of the view
            CacheManager.delete_cached_cover_art(self.playlist_id)
            CacheManager.invalidate_playlists_cache()
            self.emit(
                'refresh-window',
                {
                    'selected_playlist_id':
                    None if result == Gtk.ResponseType.DELETE_EVENT else
                    self.playlist_id
                },
                True,
            )

        dialog.destroy()

    def on_playlist_list_download_all_button_click(self, button):
        def download_state_change(*args):
            GLib.idle_add(self.update_playlist_view, self.playlist_id)

        song_ids = [s[-1] for s in self.playlist_song_store]
        CacheManager.batch_download_songs(
            song_ids,
            before_download=download_state_change,
            on_song_download_complete=download_state_change,
        )

    def on_play_all_clicked(self, btn):
        song_id = self.playlist_song_store[0][-1]
        self.emit(
            'song-clicked',
            song_id,
            [m[-1] for m in self.playlist_song_store],
            {
                'force_shuffle_state': False,
                'active_playlist_id': self.playlist_id,
            },
        )

    def on_shuffle_all_button(self, btn):
        rand_idx = randint(0, len(self.playlist_song_store) - 1)
        self.emit(
            'song-clicked',
            self.playlist_song_store[rand_idx][-1],
            [m[-1] for m in self.playlist_song_store],
            {
                'force_shuffle_state': True,
                'active_playlist_id': self.playlist_id,
            },
        )

    def on_song_activated(self, treeview, idx, column):
        # The song ID is in the last column of the model.
        self.emit(
            'song-clicked',
            self.playlist_song_store[idx][-1],
            [m[-1] for m in self.playlist_song_store],
            {
                'active_playlist_id': self.playlist_id,
            },
        )

    def on_song_button_press(self, tree, event):
        if event.button == 3:  # Right click
            clicked_path = tree.get_path_at_pos(event.x, event.y)
            if not clicked_path:
                return False

            store, paths = tree.get_selection().get_selected_rows()
            allow_deselect = False

            def on_download_state_change(song_id=None):
                GLib.idle_add(self.update_playlist_view, self.playlist_id)

            # Use the new selection instead of the old one for calculating what
            # to do the right click on.
            if clicked_path[0] not in paths:
                paths = [clicked_path[0]]
                allow_deselect = True

            song_ids = [self.playlist_song_store[p][-1] for p in paths]

            # Used to adjust for the header row.
            bin_coords = tree.convert_tree_to_bin_window_coords(
                event.x, event.y)
            widget_coords = tree.convert_tree_to_widget_coords(
                event.x, event.y)

            def on_remove_songs_click(button):
                CacheManager.update_playlist(
                    playlist_id=self.playlist_id,
                    song_index_to_remove=[p.get_indices()[0] for p in paths],
                )
                self.update_playlist_view(self.playlist_id, force=True)

            remove_text = (
                'Remove ' + util.pluralize('song', len(song_ids))
                + ' from playlist')
            util.show_song_popover(
                song_ids,
                event.x,
                event.y + abs(bin_coords.by - widget_coords.wy),
                tree,
                on_download_state_change=on_download_state_change,
                extra_menu_items=[
                    (Gtk.ModelButton(text=remove_text), on_remove_songs_click),
                ],
            )

            # If the click was on a selected row, don't deselect anything.
            if not allow_deselect:
                return True

    def make_label(self, text=None, name=None, **params):
        return Gtk.Label(
            label=text,
            name=name,
            halign=Gtk.Align.START,
            **params,
        )

    def playlist_model_row_move(self, *args):
        # If we are programatically editing the song list, don't do anything.
        if self.editing_playlist_song_list:
            return

        # We get both a delete and insert event, I think it's deterministic
        # which one comes first, but just in case, we have this
        # reordering_playlist_song_list flag..
        if self.reordering_playlist_song_list:
            self.update_playlist_order(self.playlist_id)
            self.reordering_playlist_song_list = False
        else:
            self.reordering_playlist_song_list = True

    @util.async_callback(lambda *a, **k: CacheManager.get_playlist(*a, **k))
    def update_playlist_order(self, playlist, state: ApplicationState):
        self.playlist_view_loading_box.show_all()
        update_playlist_future = CacheManager.update_playlist(
            playlist_id=playlist.id,
            song_index_to_remove=list(range(playlist.songCount)),
            song_id_to_add=[s[-1] for s in self.playlist_song_store],
        )

        update_playlist_future.add_done_callback(
            lambda f: GLib.idle_add(
                lambda: self.update_playlist_view(playlist.id, force=True)))

    def format_stats(self, playlist):
        created_date = playlist.created.strftime('%B %d, %Y')
        lines = [
            util.dot_join(
                f'Created by {playlist.owner} on {created_date}',
                f"{'Not v' if not playlist.public else 'V'}isible to others",
            ),
            util.dot_join(
                '{} {}'.format(
                    playlist.songCount,
                    util.pluralize("song", playlist.songCount)),
                util.format_sequence_duration(playlist.duration),
            ),
        ]
        return '\n'.join(lines)
