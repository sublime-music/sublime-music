import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Pango, GLib, Gio

from sublime.state_manager import ApplicationState
from sublime.cache_manager import CacheManager
from sublime.ui import util
from sublime.ui.common import IconButton


class BrowsePanel(Gtk.ScrolledWindow):
    """Defines the arist panel."""

    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    def __init__(self):
        super().__init__()

        self.root_directory_listing = DirectoryListAndDrilldown(is_root=True)

        self.add(self.root_directory_listing)

    def update(self, state: ApplicationState, force=False):
        self.root_directory_listing.update(state=state, force=force)


class DirectoryListAndDrilldown(Gtk.Paned):
    __gsignals__ = {
        'song-clicked': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (int, object, object),
        ),
        'refresh-window': (
            GObject.SignalFlags.RUN_FIRST,
            GObject.TYPE_NONE,
            (object, bool),
        ),
    }

    def __init__(self, is_root=False):
        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)
        self.is_root = is_root

        self.directory_listing = DirectoryList()
        self.pack1(self.directory_listing, False, False)

        self.listing_drilldown_panel = Gtk.Box()
        self.pack2(self.listing_drilldown_panel, True, False)

    def update(self, state: ApplicationState, force=False):
        if self.is_root:
            self.directory_listing.update_root(state=state, force=force)
        else:
            self.directory_listing.update_not_root(state=state, force=force)


class DirectoryList(Gtk.Box):
    class SubelementModel(GObject.GObject):
        id = GObject.Property(type=str)
        name = GObject.Property(type=str)

        def __init__(self, id, name):
            GObject.GObject.__init__(self)
            self.id = id
            self.name = name

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        list_actions = Gtk.ActionBar()

        refresh = IconButton('view-refresh-symbolic')
        refresh.connect('clicked', lambda *a: self.update(force=True))
        list_actions.pack_end(refresh)

        self.add(list_actions)

        self.loading_indicator = Gtk.ListBox()
        spinner_row = Gtk.ListBoxRow()
        spinner = Gtk.Spinner(
            name='directory-list-spinner',
            active=True,
        )
        spinner_row.add(spinner)
        self.loading_indicator.add(spinner_row)
        self.pack_start(self.loading_indicator, False, False, 0)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=250)

        def create_row(model: DirectoryList.SubelementModel):
            return Gtk.Label(
                label=f'<b>{util.esc(model.name)}</b>',
                use_markup=True,
                margin=10,
                halign=Gtk.Align.START,
                ellipsize=Pango.EllipsizeMode.END,
                max_width_chars=30,
            )

        self.directory_list_store = Gio.ListStore()
        self.list = Gtk.ListBox(name='directory-list')
        self.list.bind_model(self.directory_list_store, create_row)
        list_scroll_window.add(self.list)

        self.pack_start(list_scroll_window, True, True, 0)

    def update_store(self, elements):
        new_store = []
        selected_idx = None
        for i, el in enumerate(elements):
            # if state and state.selected_artist_id == el.id:
            #     selected_idx = i

            new_store.append(
                DirectoryList.SubelementModel(el.id, el.name))

        util.diff_model_store(self.directory_list_store, new_store)

        # Preserve selection
        if selected_idx is not None:
            row = self.list.get_row_at_index(selected_idx)
            self.list.select_row(row)

        self.loading_indicator.hide()

    @util.async_callback(
        lambda *a, **k: CacheManager.get_indexes(*a, **k),
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_root(
        self,
        artists,
        state: ApplicationState = None,
        force=False,
    ):
        self.update_store(artists)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_music_directory(*a, **k),
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_not_root(
        self,
        directory,
        state: ApplicationState = None,
        force=False,
    ):
        self.update_store(directory.child)
