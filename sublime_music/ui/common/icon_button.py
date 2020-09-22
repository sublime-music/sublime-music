from typing import Any, Optional

from gi.repository import Gtk


class IconButton(Gtk.Button):
    def __init__(
        self,
        icon_name: Optional[str],
        tooltip_text: str = "",
        relief: bool = False,
        icon_size: Gtk.IconSize = Gtk.IconSize.BUTTON,
        label: str = None,
        **kwargs,
    ):
        Gtk.Button.__init__(self, **kwargs)

        self.icon_size = icon_size
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="icon-button-box")

        self.image = Gtk.Image.new_from_icon_name(icon_name, self.icon_size)
        box.pack_start(self.image, False, False, 0)

        if label is not None:
            box.add(Gtk.Label(label=label))

        if not relief:
            self.props.relief = Gtk.ReliefStyle.NONE

        self.add(box)
        self.set_tooltip_text(tooltip_text)

    def set_icon(self, icon_name: Optional[str]):
        self.image.set_from_icon_name(icon_name, self.icon_size)


class IconToggleButton(Gtk.ToggleButton):
    def __init__(
        self,
        icon_name: Optional[str],
        tooltip_text: str = "",
        relief: bool = False,
        icon_size: Gtk.IconSize = Gtk.IconSize.BUTTON,
        label: str = None,
        **kwargs,
    ):
        Gtk.ToggleButton.__init__(self, **kwargs)
        self.icon_size = icon_size
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="icon-button-box")

        self.image = Gtk.Image.new_from_icon_name(icon_name, self.icon_size)
        box.add(self.image)

        if label is not None:
            box.add(Gtk.Label(label=label))

        if not relief:
            self.props.relief = Gtk.ReliefStyle.NONE

        self.add(box)
        self.set_tooltip_text(tooltip_text)

    def set_icon(self, icon_name: Optional[str]):
        self.image.set_from_icon_name(icon_name, self.icon_size)

    def get_active(self) -> bool:
        return super().get_active()

    def set_active(self, active: bool):
        super().set_active(active)


class IconMenuButton(Gtk.MenuButton):
    def __init__(
        self,
        icon_name: Optional[str] = None,
        tooltip_text: str = "",
        relief: bool = True,
        icon_size: Gtk.IconSize = Gtk.IconSize.BUTTON,
        label: str = None,
        popover: Any = None,
        **kwargs,
    ):
        Gtk.MenuButton.__init__(self, **kwargs)

        if popover:
            self.set_use_popover(True)
            self.set_popover(popover)

        self.icon_size = icon_size
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="icon-button-box")

        self.image = Gtk.Image.new_from_icon_name(icon_name, self.icon_size)
        box.add(self.image)

        if label is not None:
            box.add(Gtk.Label(label=label))

        self.props.relief = Gtk.ReliefStyle.NORMAL

        self.add(box)
        self.set_tooltip_text(tooltip_text)

    def set_icon(self, icon_name: Optional[str]):
        self.image.set_from_icon_name(icon_name, self.icon_size)

    def set_from_file(self, icon_file: Optional[str]):
        self.image.set_from_file(icon_file)
