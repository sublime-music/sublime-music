from functools import partial
from typing import Any, cast, List, Optional, Tuple

import bleach

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from ..adapters import AdapterManager, api_objects as API, CacheMissError, Result
from ..config import AppConfiguration
from ..ui import util
from ..ui.common import IconButton, LoadError, SongListColumn


class BrowsePanel(Gtk.Overlay):
    """Defines the arist panel."""

    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    update_order_token = 0

    def __init__(self):
        super().__init__()
        scrolled_window = Gtk.ScrolledWindow()
        window_box = Gtk.Box()

        self.error_container = Gtk.Box()
        window_box.pack_start(self.error_container, True, True, 0)

        self.root_directory_listing = ListAndDrilldown()
        self.root_directory_listing.connect(
            "song-clicked",
            lambda _, *args: self.emit("song-clicked", *args),
        )
        self.root_directory_listing.connect(
            "refresh-window",
            lambda _, *args: self.emit("refresh-window", *args),
        )
        window_box.add(self.root_directory_listing)

        scrolled_window.add(window_box)
        self.add(scrolled_window)

        self.spinner = Gtk.Spinner(
            name="browse-spinner",
            active=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

    def update(self, app_config: AppConfiguration, force: bool = False):
        self.update_order_token += 1

        def do_update(update_order_token: int, id_stack: Tuple[str, ...]):
            if self.update_order_token != update_order_token:
                return

            if len(id_stack) == 0:
                self.root_directory_listing.hide()
                if len(self.error_container.get_children()) == 0:
                    load_error = LoadError(
                        "Directory list",
                        "browse to song",
                        has_data=False,
                        offline_mode=app_config.offline_mode,
                    )
                    self.error_container.pack_start(load_error, True, True, 0)
                self.error_container.show_all()
            else:
                for c in self.error_container.get_children():
                    self.error_container.remove(c)
                self.error_container.hide()
                self.root_directory_listing.update(id_stack, app_config, force)
            self.spinner.hide()

        def calculate_path() -> Tuple[str, ...]:
            if (current_dir_id := app_config.state.selected_browse_element_id) is None:
                return ("root",)

            id_stack = []
            while current_dir_id:
                try:
                    directory = AdapterManager.get_directory(
                        current_dir_id,
                        before_download=self.spinner.show,
                    ).result()
                except CacheMissError as e:
                    directory = cast(API.Directory, e.partial_data)

                if not directory:
                    break
                else:
                    id_stack.append(directory.id)
                    current_dir_id = directory.parent_id

            return tuple(id_stack)

        path_result: Result[Tuple[str, ...]] = Result(calculate_path)
        path_result.add_done_callback(
            lambda f: GLib.idle_add(
                partial(do_update, self.update_order_token), f.result()
            )
        )


class ListAndDrilldown(Gtk.Paned):
    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    def __init__(self):
        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.list = MusicDirectoryList()
        self.list.connect(
            "song-clicked",
            lambda _, *args: self.emit("song-clicked", *args),
        )
        self.list.connect(
            "refresh-window",
            lambda _, *args: self.emit("refresh-window", *args),
        )
        self.pack1(self.list, False, False)

        self.box = Gtk.Box()
        self.pack2(self.box, True, False)

    def update(
        self,
        id_stack: Tuple[str, ...],
        app_config: AppConfiguration,
        force: bool = False,
    ):
        *child_id_stack, dir_id = id_stack
        selected_id = child_id_stack[-1] if len(child_id_stack) > 0 else None
        self.show()

        self.list.update(
            directory_id=dir_id,
            selected_id=selected_id,
            app_config=app_config,
            force=force,
        )

        children = self.box.get_children()
        if len(child_id_stack) == 0:
            if len(children) > 0:
                self.box.remove(children[0])
        else:
            if len(children) == 0:
                drilldown = ListAndDrilldown()
                drilldown.connect(
                    "song-clicked",
                    lambda _, *args: self.emit("song-clicked", *args),
                )
                drilldown.connect(
                    "refresh-window",
                    lambda _, *args: self.emit("refresh-window", *args),
                )
                self.box.add(drilldown)
                self.box.show_all()

            self.box.get_children()[0].update(
                tuple(child_id_stack), app_config, force=force
            )


class MusicDirectoryList(Gtk.Box):
    __gsignals__ = {
        "song-clicked": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        "refresh-window": (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    update_order_token = 0
    directory_id: Optional[str] = None
    selected_id: Optional[str] = None
    offline_mode = False

    class DrilldownElement(GObject.GObject):
        id = GObject.Property(type=str)
        name = GObject.Property(type=str)

        def __init__(self, element: API.Directory):
            GObject.GObject.__init__(self)
            self.id = element.id
            self.name = element.name

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        list_actions = Gtk.ActionBar()

        self.refresh_button = IconButton("view-refresh-symbolic", "Refresh folder")
        self.refresh_button.connect("clicked", lambda *a: self.update(force=True))
        list_actions.pack_end(self.refresh_button)

        self.add(list_actions)

        self.loading_indicator = Gtk.ListBox()
        spinner_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        spinner = Gtk.Spinner(name="drilldown-list-spinner", active=True)
        spinner_row.add(spinner)
        self.loading_indicator.add(spinner_row)
        self.pack_start(self.loading_indicator, False, False, 0)

        self.error_container = Gtk.Box()
        self.add(self.error_container)

        self.scroll_window = Gtk.ScrolledWindow(min_content_width=250)
        scrollbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.drilldown_directories_store = Gio.ListStore()
        self.list = Gtk.ListBox()
        self.list.bind_model(self.drilldown_directories_store, self.create_row)
        scrollbox.add(self.list)

        # clickable, cache status, title, duration, song ID
        self.directory_song_store = Gtk.ListStore(bool, str, str, str, str)

        self.directory_song_list = Gtk.TreeView(
            model=self.directory_song_store,
            name="directory-songs-list",
            headers_visible=False,
        )
        selection = self.directory_song_list.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.set_select_function(lambda _, model, path, current: model[path[0]][0])

        # Song status column.
        renderer = Gtk.CellRendererPixbuf()
        renderer.set_fixed_size(30, 35)
        column = Gtk.TreeViewColumn("", renderer, icon_name=1)
        column.set_resizable(True)
        self.directory_song_list.append_column(column)

        self.directory_song_list.append_column(SongListColumn("TITLE", 2, bold=True))
        self.directory_song_list.append_column(
            SongListColumn("DURATION", 3, align=1, width=40)
        )

        self.directory_song_list.connect("row-activated", self.on_song_activated)
        self.directory_song_list.connect(
            "button-press-event", self.on_song_button_press
        )
        scrollbox.add(self.directory_song_list)

        self.scroll_window.add(scrollbox)
        self.pack_start(self.scroll_window, True, True, 0)

    def update(
        self,
        app_config: AppConfiguration = None,
        force: bool = False,
        directory_id: str = None,
        selected_id: str = None,
    ):
        self.directory_id = directory_id or self.directory_id
        self.selected_id = selected_id or self.selected_id
        self.update_store(
            self.directory_id,
            force=force,
            order_token=self.update_order_token,
        )

        if app_config:
            # Deselect everything if switching online to offline.
            if self.offline_mode != app_config.offline_mode:
                self.directory_song_list.get_selection().unselect_all()
                for c in self.error_container.get_children():
                    self.error_container.remove(c)

            self.offline_mode = app_config.offline_mode

        self.refresh_button.set_sensitive(not self.offline_mode)

    _current_child_ids: List[str] = []

    @util.async_callback(
        AdapterManager.get_directory,
        before_download=lambda self: self.loading_indicator.show(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_store(
        self,
        directory: API.Directory,
        app_config: AppConfiguration = None,
        force: bool = False,
        order_token: int = None,
        is_partial: bool = False,
    ):
        if order_token != self.update_order_token:
            return

        dir_children = directory.children or []
        for c in self.error_container.get_children():
            self.error_container.remove(c)
        if is_partial:
            load_error = LoadError(
                "Directory listing",
                "load directory",
                has_data=len(dir_children) > 0,
                offline_mode=self.offline_mode,
            )
            self.error_container.pack_start(load_error, True, True, 0)
            self.error_container.show_all()
        else:
            self.error_container.hide()

        # This doesn't look efficient, since it's doing a ton of passses over the data,
        # but there is some annoying memory overhead for generating the stores to diff,
        # so we are short-circuiting by checking to see if any of the the IDs have
        # changed.
        #
        # The entire algorithm ends up being O(2n), but the first loop is very tight,
        # and the expensive parts of the second loop are avoided if the IDs haven't
        # changed.
        children_ids, children, song_ids = [], [], []
        selected_dir_idx = None
        if len(self._current_child_ids) != len(dir_children):
            force = True

        for i, c in enumerate(dir_children):
            if i >= len(self._current_child_ids) or c.id != self._current_child_ids[i]:
                force = True

            if c.id == self.selected_id:
                selected_dir_idx = i

            children_ids.append(c.id)
            children.append(c)

            if not hasattr(c, "children"):
                song_ids.append(c.id)

        if force:
            new_directories_store = []
            self._current_child_ids = children_ids

            songs = []
            for el in children:
                if hasattr(el, "children"):
                    new_directories_store.append(
                        MusicDirectoryList.DrilldownElement(cast(API.Directory, el))
                    )
                else:
                    songs.append(cast(API.Song, el))

            util.diff_model_store(
                self.drilldown_directories_store, new_directories_store
            )

            new_songs_store = [
                [
                    (
                        not self.offline_mode
                        or status_icon
                        in ("folder-download-symbolic", "view-pin-symbolic")
                    ),
                    status_icon,
                    bleach.clean(song.title),
                    util.format_song_duration(song.duration),
                    song.id,
                ]
                for status_icon, song in zip(
                    util.get_cached_status_icons(song_ids), songs
                )
            ]
        else:
            new_songs_store = [
                [
                    (
                        not self.offline_mode
                        or status_icon
                        in ("folder-download-symbolic", "view-pin-symbolic")
                    ),
                    status_icon,
                    *song_model[2:],
                ]
                for status_icon, song_model in zip(
                    util.get_cached_status_icons(song_ids), self.directory_song_store
                )
            ]

        util.diff_song_store(self.directory_song_store, new_songs_store)
        self.directory_song_list.show()

        if len(self.drilldown_directories_store) == 0:
            self.list.hide()
        else:
            self.list.show()

        if len(self.directory_song_store) == 0:
            self.directory_song_list.hide()
            self.scroll_window.set_min_content_width(275)
        else:
            self.directory_song_list.show()
            self.scroll_window.set_min_content_width(350)

        # Preserve selection
        if selected_dir_idx is not None:
            row = self.list.get_row_at_index(selected_dir_idx)
            self.list.select_row(row)

        self.loading_indicator.hide()

    def on_download_state_change(self, _):
        self.update()

    # Create Element Helper Functions
    # ==================================================================================
    def create_row(self, model: DrilldownElement) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow(
            action_name="app.browse-to",
            action_target=GLib.Variant("s", model.id),
        )
        rowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rowbox.add(
            Gtk.Label(
                label=bleach.clean(f"<b>{model.name}</b>"),
                use_markup=True,
                margin=8,
                halign=Gtk.Align.START,
                ellipsize=Pango.EllipsizeMode.END,
            )
        )

        image = Gtk.Image.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        rowbox.pack_end(image, False, False, 5)

        row.add(rowbox)
        row.show_all()
        return row

    # Event Handlers
    # ==================================================================================
    def on_song_activated(self, treeview: Any, idx: Gtk.TreePath, column: Any):
        if not self.directory_song_store[idx[0]][0]:
            return
        # The song ID is in the last column of the model.
        self.emit(
            "song-clicked",
            idx.get_indices()[0],
            [m[-1] for m in self.directory_song_store],
            {},
        )

    def on_song_button_press(self, tree: Gtk.TreeView, event: Gdk.EventButton) -> bool:
        if event.button == 3:  # Right click
            clicked_path = tree.get_path_at_pos(event.x, event.y)
            if not clicked_path:
                return False

            store, paths = tree.get_selection().get_selected_rows()
            allow_deselect = False

            # Use the new selection instead of the old one for calculating what
            # to do the right click on.
            if clicked_path[0] not in paths:
                paths = [clicked_path[0]]
                allow_deselect = True

            song_ids = [self.directory_song_store[p][-1] for p in paths]

            # Used to adjust for the header row.
            bin_coords = tree.convert_tree_to_bin_window_coords(event.x, event.y)
            widget_coords = tree.convert_tree_to_widget_coords(event.x, event.y)

            util.show_song_popover(
                song_ids,
                event.x,
                event.y + abs(bin_coords.by - widget_coords.wy),
                tree,
                self.offline_mode,
                on_download_state_change=self.on_download_state_change,
            )

            # If the click was on a selected row, don't deselect anything.
            if not allow_deselect:
                return True

        return False
