import ctypes
import os
import pathlib as pl
import platform
from enum import Enum
from functools import partial
from typing import Any, Callable, Dict, Optional, Tuple

import PySimpleGUI as sg
from PIL import Image

from . import filter, utils
from .pdf import PDF
from .signature import Signature


class Mode(Enum):
    EDIT = 1
    PREVIEW = 2


class MockSign:
    def __init__(self) -> None:
        self._running: bool = False
        self._window: sg.Window = None  # type: ignore
        self._graph: sg.Graph = None  # type: ignore
        self._event_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

        self._current_page_figure_id: Optional[int] = None
        self._current_page: int = 0
        self._floating_signature_figure_id: Optional[int] = None
        self._selected_signature_image: Optional[Image.Image] = None
        self._loaded_signatures: Dict[str, Image.Image] = {}
        self._signature_zoom_level: float = 1.0
        self._scaling_factor: float = 1.0
        self._pdf: PDF = None  # type: ignore
        self._mode: Mode = Mode.EDIT

        self._filters = [
            filter.Grayscale("Grayscale", enabled=True),
            filter.Noise("Noise", enabled=False, initial_strength=0.1, strength_range=(0, 1)),
            filter.Blur("Blur", enabled=False, initial_strength=1, strength_range=(0, 5)),
            filter.Rotate("Random rotate", enabled=True, initial_strength=1, strength_range=(0, 10)),
            filter.AutoContrast("Autocontrast cutoff", enabled=True, initial_strength=2, strength_range=(0, 45)),
        ]

    def _create_window(self) -> sg.Window:
        mode_options = [
            [
                sg.Radio("Place signature", key="-PLACE-", group_id=0, enable_events=True, default=True),
                sg.Radio("Remove signature", key="-REMOVE-", group_id=0, enable_events=True),
                sg.Radio("Preview", key="-PREVIEW-", group_id=0, enable_events=True),
            ],
        ]

        signature_options = [
            [
                sg.Text("Selected signature:"),
                sg.Combo([], key="-DROPDOWN-", enable_events=True, readonly=True, expand_x=True, disabled=True),
                sg.FolderBrowse("Browse", key="-SIGNATURE-BROWSE-", target="-SIGNATURE-BROWSE-", enable_events=True),
            ],
            [
                sg.Frame(
                    "",
                    [
                        [
                            sg.Image(
                                key="-SIGNATURE-IMAGE-",
                                size=(300, 70),
                                pad=(0, 0),
                                expand_x=True,
                                expand_y=True,
                            )
                        ]
                    ],
                    relief=sg.RELIEF_SUNKEN,
                    pad=(0, 20),
                )
            ],
        ]

        scanner_options = [
            [sg.Checkbox("Remove signature background", key="-REMOVE-BG-", enable_events=True, default=True)],
        ] + [
            [
                sg.Checkbox(
                    filter_.name,
                    key=f"-{filter_.__class__.__name__.upper()}-",
                    default=filter_.enabled,
                    enable_events=True,
                ),
                sg.Stretch(),
                sg.Text(f"{filter_.strength:.2f}", key=f"-{filter_.__class__.__name__.upper()}-STRENGTH-TEXT-")
                if filter_.strength_range
                else sg.Text(),
                sg.Slider(
                    range=filter_.strength_range,
                    resolution=(filter_.strength_range[1] - filter_.strength_range[0]) / 100,
                    orientation="horizontal",
                    key=f"-{filter_.__class__.__name__.upper()}-STRENGTH-",
                    default_value=filter_.strength,
                    enable_events=True,
                    disable_number_display=True,
                )
                if filter_.strength_range is not None
                else sg.Text(),
            ]
            for filter_ in self._filters
        ]

        col_left = [
            [
                sg.Frame(
                    "Input",
                    [
                        [
                            sg.Text("File:"),
                            sg.Text("No file loaded", auto_size_text=False, expand_x=True, key="-PDF-FILE-TEXT-"),
                            sg.FileBrowse(
                                key="-PDF-FILE-", file_types=[("PDF", "*.pdf")], target="-PDF-FILE-", enable_events=True
                            ),
                        ],
                    ],
                    expand_x=True,
                    pad=10,
                )
            ],
            [
                sg.Frame(
                    "Mode",
                    mode_options,
                    expand_x=True,
                    pad=10,
                )
            ],
            [
                sg.Frame(
                    "Signatures",
                    signature_options,
                    element_justification="center",
                    expand_x=True,
                    pad=10,
                )
            ],
            [
                sg.Frame(
                    "Scanner options",
                    scanner_options,
                    expand_x=True,
                    pad=10,
                ),
            ],
            [sg.Button("Save pdf...", key="-SAVE-", disabled=True)],
        ]

        col_right = [
            [
                sg.Graph(
                    canvas_size=(400, 400),
                    graph_bottom_left=(0, 0),
                    graph_top_right=(400, 400),
                    expand_x=True,
                    expand_y=True,
                    key="-GRAPH-",
                    enable_events=True,
                    drag_submits=True,
                    motion_events=True,
                )
            ],
            [
                sg.Button("<", key="-PREVIOUS-"),
                sg.Text("", key="-CURRENT-PAGE-"),
                sg.Button(">", key="-NEXT-"),
            ],
        ]

        layout = [
            [
                sg.Col(col_left, element_justification="center"),
                sg.Col(col_right, element_justification="center", expand_y=True, expand_x=True),
            ],
        ]

        return sg.Window("MockSign", layout, finalize=True, resizable=True)

    def _load_signatures(self, values: Dict[str, Any]) -> None:
        path = values["-SIGNATURE-BROWSE-"]
        if not path:
            return

        signatures = {}
        for file in pl.Path(path).glob("*"):
            try:
                signatures[file.name] = Image.open(file)
            except OSError:
                print(f"Could not open signature file {file.name}.")

        if not signatures:
            sg.popup_notify(
                "No signatures found. Please select a folder containing signature images.",
                title="No signatures found",
            )
            return

        signature_filenames = list(signatures.keys())
        self._window["-DROPDOWN-"].update(values=signature_filenames, set_to_index=0, disabled=False)
        self._select_signature(signatures[signature_filenames[0]])
        self._loaded_signatures = signatures

    def _select_signature(self, signature: Image.Image) -> None:
        self._selected_signature_image = signature
        preview_size = self._window["-SIGNATURE-IMAGE-"].get_size()
        padded_preview = utils.resize_and_pad_image(image=signature, target_size=preview_size)
        self._window["-SIGNATURE-IMAGE-"].update(data=utils.image_to_bytes(padded_preview))

    def _on_signature_selected(self, values: Dict[str, Any]) -> None:
        selected_signature_image = self._loaded_signatures[values["-DROPDOWN-"]]
        self._select_signature(selected_signature_image)

    def _place_floating_signature(self, signature_image: Image.Image, cursor_xy: Tuple[int, int]) -> None:
        size = (
            int(signature_image.width * self._signature_zoom_level / self._scaling_factor),
            int(signature_image.height * self._signature_zoom_level / self._scaling_factor),
        )
        scaled_signature_image = signature_image.copy().resize(size)
        scaled_signature_bytes = utils.image_to_bytes(scaled_signature_image)

        placed_figure: int = self._graph.draw_image(data=scaled_signature_bytes, location=cursor_xy)
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)
            self._floating_signature_figure_id = None
        self._floating_signature_figure_id = placed_figure

    def _update_page_navigation(self) -> None:
        if self._pdf and self._pdf.loaded:
            description = f"Page {self._current_page + 1}/{self._pdf.num_pages}"
            self._window["-CURRENT-PAGE-"].update(description)
            self._window["-PREVIOUS-"].update(disabled=self._current_page == 0)
            self._window["-NEXT-"].update(disabled=self._current_page == self._pdf.num_pages - 1)
        else:
            self._window["-CURRENT-PAGE-"].update("No file loaded")
            self._window["-PREVIOUS-"].update(disabled=True)
            self._window["-NEXT-"].update(disabled=True)

    def _update_page(self, page_image: Image.Image) -> None:
        new_page_image = page_image.copy()

        if self._mode == Mode.PREVIEW:
            for filter_ in self._filters:
                new_page_image = filter_.apply(new_page_image)

        # Match document coordinate system
        graph_size = self._graph.get_size()
        self._graph.CanvasSize = graph_size  # https://github.com/PySimpleGUI/PySimpleGUI/issues/6451
        self._scaling_factor = utils.calculate_padded_image_coordinates(new_page_image.size, graph_size).scale
        h_offset = ((graph_size[0] * self._scaling_factor) - new_page_image.width) / 2
        v_offset = ((graph_size[1] * self._scaling_factor) - new_page_image.height) / 2
        self._graph.change_coordinates(
            graph_bottom_left=(-h_offset, -v_offset),
            graph_top_right=(new_page_image.width + h_offset, new_page_image.height + v_offset),
        )

        # Update page figure
        new_page_image_resized = utils.resize_and_pad_image(new_page_image, target_size=graph_size)
        if self._current_page_figure_id is not None:
            self._graph.delete_figure(self._current_page_figure_id)
        self._current_page_figure_id = self._graph.draw_image(
            data=utils.image_to_bytes(new_page_image_resized), location=(-h_offset, v_offset + new_page_image.height)
        )

        self._update_page_navigation()

        if self._mode == Mode.EDIT:
            self._redraw_page_signatures()

    def _redraw_page_signatures(self) -> None:
        if self._pdf is None or not self._pdf.loaded:
            return

        page_signatures = self._pdf.get_page_signatures(self._current_page)
        for id_ in self._pdf.get_page_signature_ids(self._current_page):
            self._graph.delete_figure(id_)
        self._pdf.clear_page_signatures(self._current_page)
        for signature in page_signatures:
            scaled_signature = signature.get_scaled_signature()
            scaled_signature = scaled_signature.resize(
                (
                    int(scaled_signature.width / self._scaling_factor),
                    int(scaled_signature.height / self._scaling_factor),
                )
            )
            graph_location = signature.get_location()
            scaled_signature_bytes = utils.image_to_bytes(scaled_signature)
            signature_id = self._graph.draw_image(data=scaled_signature_bytes, location=graph_location)
            self._pdf.place_signature(
                signature=signature,
                identifier=signature_id,
                page_number=self._current_page,
            )

    def _update_current_page(self) -> None:
        if self._pdf is None or not self._pdf.loaded:
            return

        current_page_image = self._pdf.get_page_image(
            page_number=self._current_page,
            signed=self._mode == Mode.PREVIEW,
        )
        self._update_page(current_page_image)

    def _on_graph_mouse_move(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return

        if self._selected_signature_image:
            cursor_xy = values["-GRAPH-"]
            self._place_floating_signature(self._selected_signature_image, cursor_xy)

    def _on_graph_leave(self, _: Dict[str, Any]) -> None:
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)

    def _on_graph_mouse_wheel(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"] or not self._selected_signature_image:
            return

        is_mouse_wheel_up = self._graph.user_bind_event.delta > 0
        self._signature_zoom_level *= 1.1 if is_mouse_wheel_up else 0.9

        cursor_xy = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_xy)

    def _on_graph_clicked(self, values: Dict[str, Any]) -> None:
        cursor_xy = values["-GRAPH-"]
        if values["-REMOVE-"]:
            figure_ids_at_location = self._graph.get_figures_at_location(cursor_xy)
            for figure_id in reversed(figure_ids_at_location):
                if figure_id == self._current_page_figure_id:
                    continue
                self._graph.delete_figure(figure_id)
                self._pdf.delete_signature(figure_id)
                break  # Delete only a single signature at a time
        elif values["-PLACE-"]:
            if not self._pdf:
                sg.popup_notify(
                    "Please load a PDF file before placing signatures.",
                    title="No PDF file loaded",
                )
                return
            if self._floating_signature_figure_id is None or not self._selected_signature_image:
                return
            placed_signature = Signature(
                image=self._selected_signature_image,
                location=cursor_xy,
                scale=self._signature_zoom_level,
            )
            self._pdf.place_signature(
                signature=placed_signature,
                identifier=self._floating_signature_figure_id,
                page_number=self._current_page,
            )
            self._floating_signature_figure_id = None  # Anchor floating signature

    def _set_mode(self, mode: Mode) -> None:
        self._mode = mode
        self._update_current_page()

    def _on_save_clicked(self, _: Dict[str, Any]) -> None:
        if self._pdf is None or not self._pdf.loaded:
            sg.popup_notify(
                "Please load a PDF file before saving.",
                title="No PDF file loaded",
            )
            return

        filename = sg.popup_get_file("Save pdf...", save_as=True)
        if filename:
            self._pdf.save(path=pl.Path(filename), filters=self._filters)

    def _navigate_page(self, delta: int) -> None:
        if self._pdf is None or not self._pdf.loaded:
            return

        new_page_number = self._current_page + delta
        if new_page_number < 0 or new_page_number >= self._pdf.num_pages:
            return

        for id_ in self._pdf.get_page_signature_ids(self._current_page):
            self._graph.delete_figure(id_)
        self._current_page = new_page_number
        new_page_image = self._pdf.get_page_image(self._current_page, signed=self._mode == Mode.PREVIEW)
        self._update_page(new_page_image)

    def _on_input_file_selected(self, values: Dict[str, Any]) -> None:
        input_file = values["-PDF-FILE-"]
        if not input_file:
            return
        filename = pl.Path(input_file)
        self._pdf = PDF(filename, remove_signature_background=values["-REMOVE-BG-"])
        self._current_page = 0
        current_page_image = self._pdf.get_page_image(self._current_page, signed=self._mode == Mode.PREVIEW)
        self._update_page(current_page_image)
        self._window["-PDF-FILE-TEXT-"].update(filename.name)
        self._window["-PDF-FILE-TEXT-"].set_tooltip(str(filename))
        self._window["-SAVE-"].update(disabled=False)

    def _on_window_resized(self, _: Dict[str, Any]) -> None:
        if self._pdf is not None and self._pdf.loaded:
            current_page = self._pdf.get_page_image(self._current_page, signed=self._mode == Mode.PREVIEW)
            self._update_page(current_page)

    def _set_filter_enabled(self, filter_: filter.Filter, value: bool) -> None:
        filter_.set_enabled(value)
        self._update_current_page()

    def _set_filter_strength(self, filter_: filter.Filter, value: float) -> None:
        filter_.set_strength(value)
        self._update_current_page()

    def _set_remove_background(self, event: Dict[str, Any]) -> None:
        if self._pdf:
            self._pdf.set_remove_signature_background(event["-REMOVE-BG-"])
        self._update_current_page()

    def _on_windown_closed(self, _: Dict[str, Any]) -> None:
        self._running = False

    def _on_filter_strength_changed(self, values: Dict[str, Any], filter_: filter.Filter, key: str) -> None:
        new_strength = values[f"-{key}-STRENGTH-"]
        self._set_filter_strength(filter_, new_strength)
        self._window[f"-{key}-STRENGTH-TEXT-"].update(f"{new_strength:.2f}")

    def _on_filter_enabled_changed(self, values: Dict[str, Any], filter_: filter.Filter, key: str) -> None:
        self._set_filter_enabled(filter_, values[f"-{key}-"])

    def start(self) -> None:
        self._running = True

        self._window = self._create_window()
        self._window.bind("<Configure>", "-CONFIGURE-")

        self._graph = self._window["-GRAPH-"]
        self._graph.bind("<Leave>", "+LEAVE")
        self._graph.bind("<MouseWheel>", "+WHEEL")

        self._event_handlers[sg.WIN_CLOSED] = self._on_windown_closed
        self._event_handlers["-CONFIGURE-"] = self._on_window_resized
        self._event_handlers["-GRAPH-+MOVE"] = self._on_graph_mouse_move
        self._event_handlers["-GRAPH-+LEAVE"] = self._on_graph_leave
        self._event_handlers["-GRAPH-+WHEEL"] = self._on_graph_mouse_wheel
        self._event_handlers["-GRAPH-"] = self._on_graph_clicked
        self._event_handlers["-PDF-FILE-"] = self._on_input_file_selected
        self._event_handlers["-SIGNATURE-BROWSE-"] = self._load_signatures
        self._event_handlers["-DROPDOWN-"] = self._on_signature_selected
        self._event_handlers["-REMOVE-BG-"] = self._set_remove_background
        self._event_handlers["-PLACE-"] = lambda _: self._set_mode(Mode.EDIT)
        self._event_handlers["-REMOVE-"] = lambda _: self._set_mode(Mode.EDIT)
        self._event_handlers["-PREVIEW-"] = lambda _: self._set_mode(Mode.PREVIEW)
        self._event_handlers["-PREVIOUS-"] = lambda _: self._navigate_page(-1)
        self._event_handlers["-NEXT-"] = lambda _: self._navigate_page(1)
        self._event_handlers["-SAVE-"] = self._on_save_clicked

        for filter_ in self._filters:
            filter_name_key = filter_.__class__.__name__.upper()
            self._event_handlers[f"-{filter_name_key}-"] = partial(
                self._on_filter_enabled_changed,
                filter_=filter_,
                key=filter_name_key,
            )
            if filter_.strength_range is not None:
                self._event_handlers[f"-{filter_name_key}-STRENGTH-"] = partial(
                    self._on_filter_strength_changed,
                    filter_=filter_,
                    key=filter_name_key,
                )

        self._update_page_navigation()

        while self._running:
            event, values = self._window.read()
            if event in self._event_handlers.keys():
                self._event_handlers[event](values)

        self._window.close()


def main() -> None:
    # Enable DPI awareness on Windows 8 and above
    if os.name == "nt" and int(platform.release()) >= 8:
        ctypes.windll.shcore.SetProcessDpiAwareness(True)  # type: ignore

    app = MockSign()
    app.start()


if __name__ == "__main__":
    main()
