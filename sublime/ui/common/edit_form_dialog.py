from typing import Any, List, Optional, Tuple

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

TextFieldDescription = Tuple[str, str, bool]
BooleanFieldDescription = Tuple[str, str]
NumericFieldDescription = Tuple[str, str, Tuple[int, int, int], int]
OptionFieldDescription = Tuple[str, str, Tuple[str, ...]]


class EditFormDialog(Gtk.Dialog):
    entity_name: str
    title: str
    initial_size: Tuple[int, int]
    text_fields: List[TextFieldDescription] = []
    boolean_fields: List[BooleanFieldDescription] = []
    numeric_fields: List[NumericFieldDescription] = []
    option_fields: List[OptionFieldDescription] = []
    extra_label: Optional[str] = None
    extra_buttons: List[Gtk.Button] = []

    def get_object_name(self, obj: Any) -> str:
        """
        Gets the friendly object name. Can be overridden.
        """
        return obj.name if obj else ''

    def get_default_object(self):
        return None

    def __init__(self, parent: Any, existing_object: Any = None):
        editing = existing_object is not None
        title = getattr(self, 'title', None)
        if not title:
            if editing:
                title = f'Edit {self.get_object_name(existing_object)}'
            else:
                title = f'Create New {self.entity_name}'

        Gtk.Dialog.__init__(
            self,
            title=title,
            transient_for=parent,
            flags=0,
        )
        if not existing_object:
            existing_object = self.get_default_object()

        self.set_default_size(*self.initial_size)

        # Store a map of field label to GTK component.
        self.data = {}

        content_area = self.get_content_area()
        content_grid = Gtk.Grid(
            column_spacing=10,
            row_spacing=5,
            margin_left=10,
            margin_right=10,
        )

        # Add the text entries to the content area.
        i = 0
        for label, value_field_name, is_password in self.text_fields:
            entry_label = Gtk.Label(label=label + ':')
            entry_label.set_halign(Gtk.Align.START)
            content_grid.attach(entry_label, 0, i, 1, 1)

            entry = Gtk.Entry(
                text=getattr(existing_object, value_field_name, ''),
                hexpand=True,
            )
            if is_password:
                entry.set_visibility(False)
            content_grid.attach(entry, 1, i, 1, 1)
            self.data[value_field_name] = entry

            i += 1

        for label, value_field_name, options in self.option_fields:
            entry_label = Gtk.Label(label=label + ':')
            entry_label.set_halign(Gtk.Align.START)
            content_grid.attach(entry_label, 0, i, 1, 1)

            options_store = Gtk.ListStore(str)
            for option in options:
                options_store.append([option])

            combo = Gtk.ComboBox.new_with_model(options_store)
            combo.set_id_column(0)
            renderer_text = Gtk.CellRendererText()
            combo.pack_start(renderer_text, True)
            combo.add_attribute(renderer_text, "text", 0)

            field_value = getattr(existing_object, value_field_name)
            if field_value:
                combo.set_active(field_value.value)

            content_grid.attach(combo, 1, i, 1, 1)
            self.data[value_field_name] = combo

            i += 1

        # Add the boolean entries to the content area.
        for label, value_field_name in self.boolean_fields:
            entry_label = Gtk.Label(label=label + ':')
            entry_label.set_halign(Gtk.Align.START)
            content_grid.attach(entry_label, 0, i, 1, 1)

            # Put the checkbox in the right box. Note we have to pad here
            # since the checkboxes are smaller than the text fields.
            checkbox = Gtk.CheckButton(
                active=getattr(existing_object, value_field_name, False))
            self.data[value_field_name] = checkbox
            content_grid.attach(checkbox, 1, i, 1, 1)
            i += 1

        # Add the spin button entries to the content area.
        for (label, value_field_name, range_config,
             default_value) in self.numeric_fields:
            entry_label = Gtk.Label(label=label + ':')
            entry_label.set_halign(Gtk.Align.START)
            content_grid.attach(entry_label, 0, i, 1, 1)

            # Put the checkbox in the right box. Note we have to pad here
            # since the checkboxes are smaller than the text fields.
            spin_button = Gtk.SpinButton.new_with_range(*range_config)
            spin_button.set_value(
                getattr(existing_object, value_field_name, default_value))
            self.data[value_field_name] = spin_button
            content_grid.attach(spin_button, 1, i, 1, 1)
            i += 1

        if self.extra_label:
            label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            label_box.add(self.extra_label)
            content_grid.attach(label_box, 0, i, 2, 1)
            i += 1

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        for button, response_id in self.extra_buttons:
            if response_id is None:
                button_box.add(button)
                button.set_margin_right(10)
            else:
                self.add_action_widget(button, response_id)

        content_grid.attach(button_box, 0, i, 2, 1)

        content_area.pack_start(content_grid, True, True, 10)

        self.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_EDIT if editing else Gtk.STOCK_ADD,
            Gtk.ResponseType.OK,
        )

        self.show_all()
