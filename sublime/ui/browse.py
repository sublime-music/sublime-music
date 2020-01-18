from typing import Union

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject, Pango, GLib, Gio

from sublime.state_manager import ApplicationState
from sublime.cache_manager import CacheManager
from sublime.ui import util
from sublime.ui.common import IconButton

from sublime.server.api_objects import Child, Artist


class BrowsePanel(Gtk.Overlay):
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

    id_stack = None

    def __init__(self):
        super().__init__()
        scrolled_window = Gtk.ScrolledWindow()
        self.root_directory_listing = ListAndDrilldown(IndexList)
        scrolled_window.add(self.root_directory_listing)
        self.add(scrolled_window)

        self.spinner = Gtk.Spinner(
            active=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.add_overlay(self.spinner)

    def update(self, state: ApplicationState, force=False):
        id_stack = []
        # TODO make async
        if CacheManager.ready:
            directory = None
            current_dir_id = state.selected_browse_element_id
            while directory is None or directory.parent is not None:
                directory = CacheManager.get_music_directory(
                    current_dir_id).result()
                id_stack.append(directory.id)
                current_dir_id = directory.parent

        self.root_directory_listing.update(id_stack, state=state, force=force)
        self.spinner.hide()


class ListAndDrilldown(Gtk.Paned):
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

    id_stack = None

    def __init__(self, list_type):
        Gtk.Paned.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self.list = list_type()
        self.pack1(self.list, False, False)

        self.drilldown = Gtk.Box()
        self.pack2(self.drilldown, True, False)

    def update(
        self,
        id_stack,
        state: ApplicationState,
        force=False,
        directory_id=None,
    ):
        if self.id_stack == id_stack:
            return
        self.id_stack = id_stack

        if len(id_stack) > 0:
            self.remove(self.drilldown)
            self.drilldown = ListAndDrilldown(MusicDirectoryList)
            self.drilldown.update(
                id_stack[:-1],
                state,
                force=force,
                directory_id=id_stack[-1],
            )
            self.drilldown.show_all()
            self.pack2(self.drilldown, True, False)

        self.list.update(
            None if len(id_stack) == 0 else id_stack[-1],
            state=state,
            force=force,
            directory_id=directory_id,
        )


class DrilldownList(Gtk.Box):
    class DrilldownElement(GObject.GObject):
        id = GObject.Property(type=str)
        name = GObject.Property(type=str)
        is_dir = GObject.Property(type=bool, default=True)

        def __init__(self, element: Union[Child, Artist]):
            GObject.GObject.__init__(self)
            self.id = element.id
            self.name = (
                element.name if isinstance(element, Artist) else element.title)
            self.is_dir = isinstance(element, Artist) or element.isDir

    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        list_actions = Gtk.ActionBar()

        refresh = IconButton('view-refresh-symbolic')
        refresh.connect('clicked', self.on_refresh_clicked)
        list_actions.pack_end(refresh)

        self.add(list_actions)

        self.loading_indicator = Gtk.ListBox()
        spinner_row = Gtk.ListBoxRow(
            activatable=False,
            selectable=False,
        )
        spinner = Gtk.Spinner(
            name='drilldown-list-spinner',
            active=True,
        )
        spinner_row.add(spinner)
        self.loading_indicator.add(spinner_row)
        self.pack_start(self.loading_indicator, False, False, 0)

        list_scroll_window = Gtk.ScrolledWindow(min_content_width=250)

        self.drilldown_list_store = Gio.ListStore()
        self.list = Gtk.ListBox()
        self.list.bind_model(self.drilldown_list_store, self.create_row)
        list_scroll_window.add(self.list)

        self.pack_start(list_scroll_window, True, True, 0)

    def do_update_store(self, elements):
        new_store = []
        selected_idx = None
        for idx, el in enumerate(elements):
            if el.id == self.selected_id:
                selected_idx = idx
            new_store.append(DrilldownList.DrilldownElement(el))

        util.diff_model_store(self.drilldown_list_store, new_store)

        # Preserve selection
        if selected_idx is not None:
            row = self.list.get_row_at_index(selected_idx)
            self.list.select_row(row)

        self.loading_indicator.hide()


class IndexList(DrilldownList):
    def update(
        self,
        selected_id,
        state: ApplicationState = None,
        force=False,
        **kwargs,
    ):
        self.selected_id = selected_id
        self.update_store(force=force, state=state)

    def on_refresh_clicked(self, _):
        self.update(self.selected_id, force=True)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_indexes(*a, **k),
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_store(
        self,
        artists,
        state: ApplicationState = None,
        force=False,
    ):
        self.do_update_store(artists)

    def create_row(self, model: DrilldownList.DrilldownElement):
        row = Gtk.ListBoxRow(
            action_name='app.browse-to',
            action_target=GLib.Variant('s', model.id),
        )
        row.add(
            Gtk.Label(
                label=f'<b>{util.esc(model.name)}</b>',
                use_markup=True,
                margin=10,
                halign=Gtk.Align.START,
                ellipsize=Pango.EllipsizeMode.END,
                max_width_chars=30,
            ))
        row.show_all()
        return row


class MusicDirectoryList(DrilldownList):
    def update(
        self,
        selected_id,
        state: ApplicationState = None,
        force=False,
        directory_id=None,
    ):
        self.directory_id = directory_id
        self.selected_id = selected_id
        self.update_store(directory_id, force=force, state=state)

    def on_refresh_clicked(self, _):
        self.update(
            self.selected_id, force=True, directory_id=self.directory_id)

    @util.async_callback(
        lambda *a, **k: CacheManager.get_music_directory(*a, **k),
        before_download=lambda self: self.loading_indicator.show_all(),
        on_failure=lambda self, e: self.loading_indicator.hide(),
    )
    def update_store(
        self,
        directory,
        state: ApplicationState = None,
        force=False,
    ):
        self.do_update_store(directory.child)

    def create_row(self, model: DrilldownList.DrilldownElement):
        row = Gtk.ListBoxRow()
        if model.is_dir:
            row.set_action_name('app.browse-to')
            row.set_action_target_value(GLib.Variant('s', model.id))

        row.add(
            Gtk.Label(
                label=f'<b>{util.esc(model.name)}</b>',
                use_markup=True,
                margin=10,
                halign=Gtk.Align.START,
                ellipsize=Pango.EllipsizeMode.END,
                max_width_chars=30,
            ))
        row.show_all()
        return row
