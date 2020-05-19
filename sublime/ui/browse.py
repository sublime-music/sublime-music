from functools import partial
from typing import Any, cast, List, Optional, Tuple

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

from sublime.adapters import AdapterManager, api_objects as API, Result
from sublime.config import AppConfiguration
from sublime.ui import util
from sublime.ui.common import IconButton, SongListColumn


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

        self.root_directory_listing = ListAndDrilldown()
        self.root_directory_listing.connect(
            "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
        )
        self.root_directory_listing.connect(
            "refresh-window", lambda _, *args: self.emit("refresh-window", *args),
        )
        scrolled_window.add(self.root_directory_listing)

        self.add(scrolled_window)

        self.spinner = Gtk.Spinner(
            name="browse-spinner",
            active=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

    def update(self, app_config: AppConfiguration, force: bool = False):
        if not AdapterManager.can_get_directory():
            return

        self.update_order_token += 1

        def do_update(update_order_token: int, id_stack: Tuple[str, ...]):
            if self.update_order_token != update_order_token:
                return

            self.root_directory_listing.update(id_stack, app_config, force)
            self.spinner.hide()

        def calculate_path() -> Tuple[str, ...]:
            if (current_dir_id := app_config.state.selected_browse_element_id) is None:
                return ("root",)

            id_stack = []
            while current_dir_id and (
                directory := AdapterManager.get_directory(
                    current_dir_id, before_download=self.spinner.show,
                ).result()
            ):
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
            "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
        )
        self.list.connect(
            "refresh-window", lambda _, *args: self.emit("refresh-window", *args),
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
                    "song-clicked", lambda _, *args: self.emit("song-clicked", *args),
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

        refresh = IconButton("view-refresh-symbolic", "Refresh folder")
        refresh.connect("clicked", lambda *a: self.update(force=True))
        list_actions.pack_end(refresh)

        self.add(list_actions)

        self.loading_indicator = Gtk.ListBox()
        spinner_row = Gtk.ListBoxRow(activatable=False, selectable=False)
        spinner = Gtk.Spinner(name="drilldown-list-spinner", active=True)
        spinner_row.add(spinner)
        self.loading_indicator.add(spinner_row)
        self.pack_start(self.loading_indicator, False, False, 0)

        self.scroll_window = Gtk.ScrolledWindow(min_content_width=250)
        scrollbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.drilldown_directories_store = Gio.ListStore()
        self.list = Gtk.ListBox()
        self.list.bind_model(self.drilldown_directories_store, self.create_row)
        scrollbox.add(self.list)

        self.directory_song_store = Gtk.ListStore(
            str, str, str, str,  # cache status, title, duration, song ID
        )

        self.directory_song_list = Gtk.TreeView(
            model=self.directory_song_store,
            name="directory-songs-list",
            headers_visible=False,
        )
        self.directory_song_list.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        # Song status column.
        renderer = Gtk.CellRendererPixbuf()
        renderer.set_fixed_size(30, 35)
        column = Gtk.TreeViewColumn("", renderer, icon_name=0)
        column.set_resizable(True)
        self.directory_song_list.append_column(column)

        self.directory_song_list.append_column(SongListColumn("TITLE", 1, bold=True))
        self.directory_song_list.append_column(
            SongListColumn("DURATION", 2, align=1, width=40)
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
            self.directory_id, force=force, order_token=self.update_order_token,
        )

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
    ):
        if order_token != self.update_order_token:
            return

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
        for i, c in enumerate(directory.children):
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
                    status_icon,
                    util.esc(song.title),
                    util.format_song_duration(song.duration),
                    song.id,
                ]
                for status_icon, song in zip(
                    util.get_cached_status_icons(song_ids), songs
                )
            ]
        else:
            new_songs_store = [
                [status_icon] + song_model[1:]
                for status_icon, song_model in zip(
                    util.get_cached_status_icons(song_ids), self.directory_song_store
                )
            ]

        util.diff_song_store(self.directory_song_store, new_songs_store)

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
            action_name="app.browse-to", action_target=GLib.Variant("s", model.id),
        )
        rowbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        rowbox.add(
            Gtk.Label(
                label=f"<b>{util.esc(model.name)}</b>",
                use_markup=True,
                margin=8,
                halign=Gtk.Align.START,
                ellipsize=Pango.EllipsizeMode.END,
            )
        )

        icon = Gio.ThemedIcon(name="go-next-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        rowbox.pack_end(image, False, False, 5)
        row.add(rowbox)
        row.show_all()
        return row

    # Event Handlers
    # ==================================================================================
    def on_song_activated(self, treeview: Any, idx: Gtk.TreePath, column: Any):
        # The song ID is in the last column of the model.
        self.emit(
            "song-clicked",
            idx.get_indices()[0],
            [m[-1] for m in self.directory_song_store],
            {},
        )

    def on_song_button_press(self, tree: Gtk.TreeView, event: Gdk.EventButton,) -> bool:
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
                on_download_state_change=self.on_download_state_change,
            )

            # If the click was on a selected row, don't deselect anything.
            if not allow_deselect:
                return True

        return False
