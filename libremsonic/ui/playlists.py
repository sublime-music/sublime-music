import re
from functools import lru_cache
from typing import List, OrderedDict

from deepdiff import DeepDiff
from fuzzywuzzy import process

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk, Pango, GObject, GLib, Gdk

from libremsonic.server.api_objects import Child, PlaylistWithSongs
from libremsonic.state_manager import ApplicationState
from libremsonic.cache_manager import CacheManager, SongCacheStatus
from libremsonic.ui import util
from libremsonic.ui.common import EditFormDialog


class EditPlaylistDialog(EditFormDialog):
    __gsignals__ = {
        'delete-playlist': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                            ()),
    }

    entity_name: str = 'Playlist'
    initial_size = (350, 120)
    text_fields = [('Name', 'name', False), ('Comment', 'comment', False)]
    boolean_fields = [('Public', 'public')]

    def __init__(self, *args, **kwargs):
        delete_playlist = Gtk.Button(label='Delete Playlist')
        delete_playlist.connect('clicked', self.on_delete_playlist_click)
        self.extra_buttons = [delete_playlist]
        super().__init__(*args, **kwargs)

    def on_delete_playlist_click(self, event):
        self.emit('delete-playlist')


class PlaylistsPanel(Gtk.Paned):
    """Defines the playlists panel."""
    __gsignals__ = {
        'song-clicked': (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE,
                         (str, object)),
    }

    playlist_map: OrderedDict[int, PlaylistWithSongs] = {}
    song_ids: List[int] = []

    editing_playlist_song_list: bool = False
    reordering_playlist_song_list: bool = False

    def __init__(self):
        Gtk.Paned.__init__(
            self,
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        # The playlist list on the left side
        # =====================================================================
        playlist_list_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        playlist_list_actions = Gtk.ActionBar()

        self.new_playlist = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        add_icon = Gio.ThemedIcon(name='list-add')
        image = Gtk.Image.new_from_gicon(add_icon, Gtk.IconSize.LARGE_TOOLBAR)
        box.add(image)
        box.add(Gtk.Label(label='New Playlist', margin=5))
        self.new_playlist.add(box)
        self.new_playlist.connect('clicked', self.on_new_playlist_clicked)
        playlist_list_actions.pack_start(self.new_playlist)

        list_refresh_button = util.button_with_icon('view-refresh')
        list_refresh_button.connect('clicked', self.on_list_refresh_click)
        playlist_list_actions.pack_end(list_refresh_button)

        playlist_list_vbox.add(playlist_list_actions)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=220)
        self.playlist_list = Gtk.ListBox(name='playlist-list-listbox')

        self.playlist_list_loading = Gtk.ListBoxRow(activatable=False,
                                                    selectable=False)
        playlist_list_loading_spinner = Gtk.Spinner(
            name='playlist-list-spinner', active=True)
        self.playlist_list_loading.add(playlist_list_loading_spinner)
        self.playlist_list.add(self.playlist_list_loading)

        self.new_playlist_row = Gtk.ListBoxRow(activatable=False,
                                               selectable=False)
        new_playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                   visible=False)

        self.playlist_list_new_entry = Gtk.Entry(
            name='playlist-list-new-playlist-entry')
        self.playlist_list_new_entry.connect(
            'activate', self.on_playlist_list_new_entry_activate)
        new_playlist_box.add(self.playlist_list_new_entry)

        new_playlist_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.playlist_list_new_confirm_button = Gtk.Button.new_from_icon_name(
            'object-select-symbolic', Gtk.IconSize.BUTTON)
        self.playlist_list_new_confirm_button.set_name(
            'playlist-list-new-playlist-confirm')
        self.playlist_list_new_confirm_button.connect(
            'clicked', self.on_playlist_list_new_confirm_button_clicked)
        new_playlist_actions.pack_end(self.playlist_list_new_confirm_button,
                                      False, True, 0)

        self.playlist_list_new_cancel_button = Gtk.Button.new_from_icon_name(
            'process-stop-symbolic', Gtk.IconSize.BUTTON)
        self.playlist_list_new_cancel_button.set_name(
            'playlist-list-new-playlist-cancel')
        self.playlist_list_new_cancel_button.connect(
            'clicked', self.on_playlist_list_new_cancel_button_clicked)
        new_playlist_actions.pack_end(self.playlist_list_new_cancel_button,
                                      False, True, 0)

        new_playlist_box.add(new_playlist_actions)
        self.new_playlist_row.add(new_playlist_box)
        self.playlist_list.add(self.new_playlist_row)

        self.playlist_list.connect('row-activated', self.on_playlist_selected)
        list_scroll_window.add(self.playlist_list)
        playlist_list_vbox.pack_start(list_scroll_window, True, True, 0)

        # Add playlist button

        self.pack1(playlist_list_vbox, False, False)

        # The playlist view on the right side
        # =====================================================================
        loading_overlay = Gtk.Overlay(name='playlist-view-overlay')
        playlist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Playlist info panel
        # TODO shrink when playlist is is scrolled down.
        self.big_info_panel = Gtk.Box(
            name='playlist-info-panel',
            orientation=Gtk.Orientation.HORIZONTAL,
        )

        artwork_overlay = Gtk.Overlay()
        self.playlist_artwork = Gtk.Image(name='playlist-album-artwork')
        artwork_overlay.add(self.playlist_artwork)

        self.artwork_spinner = Gtk.Spinner(name='playlist-artwork-spinner',
                                           active=True,
                                           halign=Gtk.Align.CENTER,
                                           valign=Gtk.Align.CENTER)
        artwork_overlay.add_overlay(self.artwork_spinner)
        self.big_info_panel.pack_start(artwork_overlay, False, False, 0)

        # Action buttons, name, comment, number of songs, etc.
        playlist_details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Action buttons (note we are packing end here, so we have to put them
        # in right-to-left).
        self.playlist_action_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL)

        view_refresh_button = util.button_with_icon('view-refresh-symbolic')
        view_refresh_button.connect('clicked', self.on_view_refresh_click)
        self.playlist_action_buttons.pack_end(view_refresh_button, False,
                                              False, 5)

        playlist_edit_button = util.button_with_icon('document-edit-symbolic')
        playlist_edit_button.connect('clicked',
                                     self.on_playlist_edit_button_click)
        self.playlist_action_buttons.pack_end(playlist_edit_button, False,
                                              False, 5)

        download_all_button = util.button_with_icon('folder-download-symbolic')
        download_all_button.connect(
            'clicked', self.on_playlist_list_download_all_button_click)
        self.playlist_action_buttons.pack_end(download_all_button, False,
                                              False, 5)

        playlist_details_box.pack_start(self.playlist_action_buttons, False,
                                        False, 5)

        playlist_details_box.pack_start(Gtk.Box(), True, False, 0)

        self.playlist_indicator = self.make_label(name='playlist-indicator')
        playlist_details_box.add(self.playlist_indicator)

        self.playlist_name = self.make_label(name='playlist-name')
        playlist_details_box.add(self.playlist_name)

        self.playlist_comment = self.make_label(name='playlist-comment')
        playlist_details_box.add(self.playlist_comment)

        self.playlist_stats = self.make_label(name='playlist-stats')
        playlist_details_box.add(self.playlist_stats)

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

        self.playlist_song_model = Gtk.ListStore(
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
            model=self.playlist_song_model,
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
        self.playlist_songs.connect('button-press-event',
                                    self.on_song_button_press)

        # Set up drag-and-drop on the song list for editing the order of the
        # playlist.
        self.playlist_song_model.connect('row-inserted',
                                         self.playlist_model_row_move)
        self.playlist_song_model.connect('row-deleted',
                                         self.playlist_model_row_move)

        playlist_view_scroll_window.add(self.playlist_songs)

        playlist_box.pack_end(playlist_view_scroll_window, True, True, 0)
        loading_overlay.add(playlist_box)

        playlist_view_spinner = Gtk.Spinner(active=True)
        playlist_view_spinner.start()

        self.playlist_view_loading_box = Gtk.Alignment(
            name='playlist-view-overlay',
            xalign=0.5,
            yalign=0.5,
            xscale=0.1,
            yscale=0.1)
        self.playlist_view_loading_box.add(playlist_view_spinner)
        loading_overlay.add_overlay(self.playlist_view_loading_box)

        self.pack2(loading_overlay, True, False)

    # Event Handlers
    # =========================================================================
    def on_new_playlist_clicked(self, new_playlist_button):
        self.playlist_list_new_entry.set_text('Untitled Playlist')
        self.playlist_list_new_entry.grab_focus()
        self.new_playlist_row.show()

    def on_playlist_selected(self, playlist_list, row):
        self.update_playlist_view(self.playlist_map[row.get_index()].id)

    def on_list_refresh_click(self, button):
        self.update_playlist_list(force=True)

    def on_playlist_edit_button_click(self, button):
        selected = self.playlist_list.get_selected_row()
        playlist = self.playlist_map[selected.get_index()]
        dialog = EditPlaylistDialog(
            self.get_toplevel(),
            CacheManager.get_playlist(playlist.id).result())

        def on_delete_playlist(e):
            CacheManager.delete_playlist(playlist.id)
            dialog.destroy()
            self.update_playlist_list(force=True)

        dialog.connect('delete-playlist', on_delete_playlist)

        result = dialog.run()
        if result == Gtk.ResponseType.OK:
            CacheManager.update_playlist(
                playlist.id,
                name=dialog.data['Name'].get_text(),
                comment=dialog.data['Comment'].get_text(),
                public=dialog.data['Public'].get_active(),
            )

            cover_art_filename = f'cover_art/{playlist.coverArt}_*'
            CacheManager.delete_cache(cover_art_filename)

            self.update_playlist_list(force=True)
            self.update_playlist_view(playlist.id, force=True)
        dialog.destroy()

    def on_playlist_list_download_all_button_click(self, button):
        playlist = self.playlist_map[
            self.playlist_list.get_selected_row().get_index()]

        def download_state_change(*args):
            GLib.idle_add(self.update_playlist_view, playlist.id)

        song_ids = [s[-1] for s in self.playlist_song_model]
        CacheManager.batch_download_songs(
            song_ids,
            before_download=download_state_change,
            on_song_download_complete=download_state_change,
        )

    def on_view_refresh_click(self, button):
        playlist = self.playlist_map[
            self.playlist_list.get_selected_row().get_index()]
        self.update_playlist_view(playlist.id, force=True)

    def on_song_activated(self, treeview, idx, column):
        # The song ID is in the last column of the model.
        song_id = self.playlist_song_model[idx][-1]
        self.emit('song-clicked', song_id,
                  [m[-1] for m in self.playlist_song_model])

    def on_song_button_press(self, tree, event):
        if event.button == 3:  # Right click
            clicked_path = tree.get_path_at_pos(event.x, event.y)
            if not clicked_path:
                return False

            store, paths = tree.get_selection().get_selected_rows()
            allow_deselect = False

            playlist = self.playlist_map[
                self.playlist_list.get_selected_row().get_index()]

            def on_download_state_change(song_id=None):
                GLib.idle_add(self.update_playlist_song_list, playlist.id)

            # Use the new selection instead of the old one for calculating what
            # to do the right click on.
            if clicked_path[0] not in paths:
                paths = [clicked_path[0]]
                allow_deselect = True

            song_ids = [self.playlist_song_model[p][-1] for p in paths]

            # Used to adjust for the header row.
            bin_coords = tree.convert_tree_to_bin_window_coords(
                event.x, event.y)
            widget_coords = tree.convert_tree_to_widget_coords(
                event.x, event.y)

            def on_remove_songs_click(button):
                CacheManager.update_playlist(
                    playlist_id=playlist.id,
                    song_index_to_remove=[p.get_indices()[0] for p in paths],
                )
                self.update_playlist_song_list(playlist.id, force=True)

            remove_text = f"Remove {util.pluralize('song', len(song_ids))} from playlist"
            util.show_song_popover(
                song_ids,
                event.x,
                event.y + abs(bin_coords.by - widget_coords.wy),
                tree,
                on_download_state_change=on_download_state_change,
                extra_menu_items=[(
                    Gtk.ModelButton(text=remove_text),
                    on_remove_songs_click,
                )])

            # If the click was on a selected row, don't deselect anything.
            if not allow_deselect:
                return True

    def on_playlist_list_new_entry_activate(self, entry):
        self.create_playlist(entry.get_text())

    def on_playlist_list_new_cancel_button_clicked(self, button):
        self.new_playlist_row.hide()

    def on_playlist_list_new_confirm_button_clicked(self, button):
        self.create_playlist(self.playlist_list_new_entry.get_text())

    def playlist_model_row_move(self, *args):
        # If we are programatically editing the song list, don't do anything.
        if self.editing_playlist_song_list:
            return

        # We get both a delete and insert event, I think it's deterministic
        # which one comes first, but just in case, we have this
        # reordering_playlist_song_list flag..
        if self.reordering_playlist_song_list:
            selected = self.playlist_list.get_selected_row()
            playlist = self.playlist_map[selected.get_index()]
            self.update_playlist_order(playlist.id)
            self.reordering_playlist_song_list = False
        else:
            self.reordering_playlist_song_list = True

    # Helper Methods
    # =========================================================================
    def make_label(self, text=None, name=None, **params):
        return Gtk.Label(
            label=text,
            name=name,
            halign=Gtk.Align.START,
            **params,
        )

    def update(self, state: ApplicationState):
        self.new_playlist_row.hide()
        self.set_playlist_view_loading(False)
        self.set_playlist_art_loading(False)
        self.update_playlist_list()
        selected = self.playlist_list.get_selected_row()
        if selected:
            playlist_id = self.playlist_map[selected.get_index()].id
            self.update_playlist_view(playlist_id)
            self.playlist_action_buttons.show()
        else:
            self.playlist_action_buttons.hide()

    def set_playlist_list_loading(self, loading_status):
        if loading_status:
            self.playlist_list_loading.show()
        else:
            self.playlist_list_loading.hide()

    def set_playlist_view_loading(self, loading_status):
        if loading_status:
            self.playlist_view_loading_box.show()
            self.artwork_spinner.show()
        else:
            self.playlist_view_loading_box.hide()

    def set_playlist_art_loading(self, loading_status):
        if loading_status:
            self.artwork_spinner.show()
        else:
            self.artwork_spinner.hide()

    def create_playlist(self, playlist_name):
        try:
            # TODO make this async eventually
            CacheManager.create_playlist(name=playlist_name)
        except ConnectionError:
            # TODO show a message box
            return

        self.update_playlist_list(force=True)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlists(*a, **k),
        before_download=lambda self: self.set_playlist_list_loading(True),
        on_failure=lambda self, e: self.set_playlist_list_loading(False),
    )
    def update_playlist_list(self, playlists: List[PlaylistWithSongs]):
        selected_row = self.playlist_list.get_selected_row()
        selected_playlist = None
        if selected_row:
            selected_playlist = self.playlist_map.get(selected_row.get_index())

        for row in self.playlist_list.get_children()[1:-1]:
            self.playlist_list.remove(row)

        self.playlist_map = {}
        selected_idx = None
        for i, playlist in enumerate(playlists):
            # Use i+1 due to loading indicator
            if playlist == selected_playlist:
                selected_idx = i + 1
            self.playlist_map[i + 1] = playlist
            self.playlist_list.insert(self.create_playlist_label(playlist),
                                      i + 1)
        if selected_idx:
            row = self.playlist_list.get_row_at_index(selected_idx)
            self.playlist_list.select_row(row)

        self.playlist_list.show_all()
        self.set_playlist_list_loading(False)
        self.new_playlist_row.hide()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlist(*a, **k),
        before_download=lambda self: self.set_playlist_view_loading(True),
        on_failure=lambda self, e: (self.set_playlist_view_loading(False) or
                                    self.set_playlist_art_loading(False)),
    )
    def update_playlist_view(self, playlist):
        # Update the Playlist Info panel
        self.update_playlist_artwork(playlist.coverArt)
        self.playlist_indicator.set_markup('PLAYLIST')
        self.playlist_name.set_markup(f'<b>{playlist.name}</b>')
        if playlist.comment:
            self.playlist_comment.set_text(playlist.comment)
            self.playlist_comment.show()
        else:
            self.playlist_comment.hide()
        self.playlist_stats.set_markup(self.format_stats(playlist))

        self.update_playlist_song_list(playlist.id)
        self.playlist_action_buttons.show()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlist(*a, **k),
    )
    def update_playlist_song_list(self, playlist):
        # Update the song list model. This requires some fancy diffing to
        # update the list.
        self.editing_playlist_song_list = True
        old_model = [row[:] for row in self.playlist_song_model]

        cache_icon = {
            SongCacheStatus.NOT_CACHED: '',
            SongCacheStatus.CACHED: 'folder-download-symbolic',
            SongCacheStatus.PERMANENTLY_CACHED: 'view-pin-symbolic',
            SongCacheStatus.DOWNLOADING: 'emblem-synchronizing-symbolic',
        }
        new_model = [[
            cache_icon[CacheManager.get_cached_status(song)],
            song.title,
            song.album,
            song.artist,
            util.format_song_duration(song.duration),
            song.id,
        ] for song in (playlist.entry or [])]

        # Diff the lists to determine what needs to be changed.
        diff = DeepDiff(old_model, new_model)
        changed = diff.get('values_changed', {})
        added = diff.get('iterable_item_added', {})
        removed = diff.get('iterable_item_removed', {})

        def parse_location(location):
            match = re.match(r'root\[(\d*)\](?:\[(\d*)\])?', location)
            return tuple(map(int,
                             (g for g in match.groups() if g is not None)))

        for edit_location, diff in changed.items():
            idx, field = parse_location(edit_location)
            self.playlist_song_model[idx][field] = diff['new_value']

        for add_location, value in added.items():
            self.playlist_song_model.append(value)

        for remove_location, value in reversed(list(removed.items())):
            remove_at = parse_location(remove_location)[0]
            del self.playlist_song_model[remove_at]

        self.editing_playlist_song_list = False
        self.set_playlist_view_loading(False)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_cover_art_filename(*a, **k),
        before_download=lambda self: self.set_playlist_art_loading(True),
        on_failure=lambda self, e: self.set_playlist_art_loading(False),
    )
    def update_playlist_artwork(self, cover_art_filename):
        self.playlist_artwork.set_from_file(cover_art_filename)
        self.set_playlist_art_loading(False)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_playlist(*a, **k),
        # TODO make loading here
    )
    def update_playlist_order(self, playlist):
        CacheManager.update_playlist(
            playlist_id=playlist.id,
            song_index_to_remove=list(range(playlist.songCount)),
            song_id_to_add=[s[-1] for s in self.playlist_song_model],
        )
        self.update_playlist_song_list(playlist.id, force=True)

    def create_playlist_label(self, playlist: PlaylistWithSongs):
        return self.make_label(f'<b>{playlist.name}</b>',
                               use_markup=True,
                               margin=12)

    def format_stats(self, playlist):
        created_date = playlist.created.strftime('%B %d, %Y')
        lines = [
            util.dot_join(
                f'Created by {playlist.owner} on {created_date}',
                f"{'Not v' if not playlist.public else 'V'}isible to others",
            ),
            util.dot_join(
                '{} {}'.format(playlist.songCount,
                               util.pluralize("song", playlist.songCount)),
                util.format_sequence_duration(playlist.duration),
            ),
        ]
        return '\n'.join(lines)
