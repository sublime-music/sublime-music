from gi.repository import Gtk, Pango


class SongListColumn(Gtk.TreeViewColumn):
    def __init__(
        self,
        header: str,
        text_idx: int,
        bold: bool = False,
        align: float = 0,
        width: int = None,
    ):
        """Represents a column in a song list."""
        renderer = Gtk.CellRendererText(
            xalign=align,
            weight=Pango.Weight.BOLD if bold else Pango.Weight.NORMAL,
            ellipsize=Pango.EllipsizeMode.END,
        )
        renderer.set_fixed_size(width or -1, 35)

        super().__init__(header, renderer, text=text_idx, sensitive=0)
        self.set_resizable(True)
        self.set_expand(not width)
