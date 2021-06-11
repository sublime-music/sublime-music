"""
sublime-music
Copyright (C) 2021 LoveIsGrief

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from gi.repository import GObject, Gtk

from sublime_music.adapters import AdapterManager
from sublime_music.ui.common import IconButton


class RatingButton(IconButton):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "ratingbutton"
        kwargs["relief"] = False
        super().__init__(*args, **kwargs)


class RatingButtonBox(Gtk.Box):
    """
    A simple GtkBox containing buttons that allow rating something.
    It doesn't know what it's rating just what the rating is when it changed
    """

    __gsignals__ = {
        # The rating has been set and is reflected in the UI
        "rating-changed": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ()),
        # It has just been clicked, but no rating has been set
        "rating-clicked": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, (int,)),
        "rating-remove": (GObject.SignalFlags.RUN_FIRST, GObject.TYPE_NONE, ()),
    }
    MAX_VALUE = 5

    def __init__(
        self,
        icon_rated: str = "star-full",
        icon_unrated: str = "star-empty",
        **kwargs,
    ):
        kwargs["orientation"] = kwargs.get("orientation", Gtk.Orientation.HORIZONTAL)
        super().__init__(**kwargs)
        self.set_css_name("ratingbuttonbox")
        self.set_property("valign", Gtk.Align.CENTER)
        self.set_property("halign", Gtk.Align.CENTER)
        self._rating: int | None = None

        # Icons to use for the rating indicators/buttons
        self.icon_rated = icon_rated
        self.icon_unrated = icon_unrated

        self._buttons = []
        for i in range(1, self.MAX_VALUE + 1):
            rating_button = RatingButton(self.icon_unrated)
            rating_button.connect("clicked", self._on_rating_clicked, i)
            self._buttons.append(rating_button)
            self.pack_start(rating_button, False, False, 1)

    @property
    def rating(self) -> int | None:
        return self._rating

    @rating.setter
    def rating(self, rating: int | None):
        """
        Update the UI to reflect a new rating
        """
        self.validate_rating(rating)

        for i, _button in enumerate(self._buttons, start=1):
            _button.set_icon(
                self.icon_rated if rating is not None and i <= rating else self.icon_unrated
            )
        self._rating = rating
        self.emit("rating-changed")

    def validate_rating(self, rating: int | None):
        if rating is not None and 1 >= rating > self.MAX_VALUE:
            raise ValueError("Must pass a value between 1 and " + str(self.MAX_VALUE))

    def _on_rating_clicked(self, button: IconButton, rating: int):
        if AdapterManager.can_set_song_rating():
            if self.rating == rating:
                self.rating = None
                self.emit("rating-remove")
            else:
                self.rating = rating
                self.emit("rating-clicked", rating)
