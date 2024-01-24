import ctypes
import pathlib as pl
import platform
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import PySimpleGUI as sg
import scanner
import utils
from pdf import PDF
from PIL import Image
from signature import Signature

DEFAULT_SIGNATURE_FOLDER = pl.Path(__file__).parent / "signatures"


class Mode(Enum):
    EDIT = 1
    PREVIEW = 2


class FalsiSignPy:
    def __init__(self) -> None:
        self._running = False
        self._current_page_figure_id: Optional[int] = None
        self._current_page: int = 0
        self._floating_signature_figure_id: Optional[int] = None
        self._selected_signature_image = None
        self._loaded_signatures: Dict[str, Image] = {}
        self._signature_zoom_level = 1.0
        self._scaling_factor = 1.0
        self._window: Optional[sg.Window] = None
        self._graph: Optional[sg.Graph] = None
        self._pdf: Optional[PDF] = None
        self._mode: Mode = Mode.EDIT
        self._event_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

        self._filters = [
            scanner.Grayscale("Grayscale", enabled=True),
            scanner.Blur("Blur", enabled=False, initial_strength=1, strength_range=(0, 20)),
            scanner.Rotate("Random rotate", enabled=True, initial_strength=1, strength_range=(0, 10)),
            scanner.AutoContrast("Autocontrast cutoff", enabled=True, initial_strength=2, strength_range=(0, 45)),
        ]

    def _create_window(self) -> sg.Window:
        self._mode_options = [
            [
                sg.Radio("Place signature", key="-PLACE-", group_id=0, enable_events=True, default=True),
                sg.Radio("Remove signature", key="-REMOVE-", group_id=0, enable_events=True),
                sg.Radio("Preview", key="-PREVIEW-", group_id=0, enable_events=True),
            ],
        ]

        self._scanner_options = [
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

        self._signature_options = [
            [
                sg.Text("Selected signature:"),
                sg.Combo([], key="-DROPDOWN-", enable_events=True, readonly=True, expand_x=True),
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
                    self._mode_options,
                    expand_x=True,
                    pad=10,
                )
            ],
            [
                sg.Frame(
                    "Signatures",
                    self._signature_options,
                    element_justification="center",
                    expand_x=True,
                    pad=10,
                )
            ],
            [
                sg.Frame(
                    "Scanner options",
                    self._scanner_options,
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
                sg.Button("<", key="-PREVIOUS-", disabled=True),
                sg.Text("No file loaded", key="-CURRENT-PAGE-"),
                sg.Button(">", key="-NEXT-", disabled=True),
            ],
        ]

        layout = [
            [
                sg.Col(col_left, element_justification="center"),
                sg.Col(col_right, element_justification="center", expand_y=True, expand_x=True),
            ],
        ]

        return sg.Window("FalsiSignPy", layout, finalize=True, resizable=True)

    def _set_disabled(self, element: Union[sg.Element, List], disabled: bool) -> None:
        return  # TODO: Decide if this is needed

        if isinstance(element, list):
            for element in element:
                self._set_disabled(element, disabled)

        if isinstance(element, sg.Slider):
            element.Widget.config(troughcolor="#6D7F93" if disabled else sg.theme_slider_color())
        elif isinstance(element, sg.Text):
            element.update(text_color="grey43" if disabled else sg.theme_text_color())

        if isinstance(element, sg.Element) and getattr(element, "Disabled", None) is not None:
            element.update(disabled=disabled)

    def _load_signatures(self, values: Dict[str, Any]) -> None:
        path = values["-SIGNATURE-BROWSE-"]
        if not path:
            return
        path = pl.Path(path)

        signatures = {}
        for file in path.glob("*"):
            try:
                signatures[file.name] = Image.open(file)
            except OSError:
                pass

        if len(signatures) == 0:
            sg.popup_notify(
                "No signatures found. Please select a folder containing signature images.",
                title="No signatures found",
            )
            return

        self._window["-DROPDOWN-"].update(values=list(signatures.keys()))
        self._loaded_signatures = signatures

    def _place_floating_signature(self, signature_image: Image.Image, cursor_xy: Tuple[int, int]) -> None:
        new_size = (
            int(signature_image.width * self._signature_zoom_level / self._scaling_factor),
            int(signature_image.height * self._signature_zoom_level / self._scaling_factor),
        )
        scaled_signature_image = signature_image.copy().resize(new_size)
        scaled_signature_bytes = utils.image_to_bytes(scaled_signature_image)

        placed_figure: int = self._graph.draw_image(data=scaled_signature_bytes, location=cursor_xy)
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)
            self._floating_signature_figure_id = None
        self._floating_signature_figure_id = placed_figure

    def _update_page_navigation(self) -> None:
        description = f"Page {self._current_page + 1}/{self._pdf.num_pages}"
        self._window["-CURRENT-PAGE-"].update(description)
        self._window["-PREVIOUS-"].update(disabled=self._current_page == 0)
        self._window["-NEXT-"].update(disabled=self._current_page == self._pdf.num_pages - 1)

    def _update_page(self, page_image: Image.Image) -> None:
        new_page_image = page_image.copy()
        if self._mode == Mode.PREVIEW:
            for filter_ in self._filters:
                new_page_image = filter_.apply(new_page_image)

        # Match document coordinate system
        graph_size = self._graph.get_size()
        self._graph.CanvasSize = graph_size  # https://github.com/PySimpleGUI/PySimpleGUI/issues/6451
        _, _, _, _, self._scaling_factor = utils.calculate_padded_image_coordinates(new_page_image.size, graph_size)
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

    def _update_current_page(self) -> None:
        if self._pdf is None or not self._pdf.loaded:
            return

        current_page_image = self._pdf.get_page_image(self._current_page, signed=self._mode == Mode.PREVIEW)
        self._update_page(current_page_image)

    def _on_graph_move(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return
        if self._pdf is None or not self._pdf.loaded:
            return

        cursor_xy = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_xy)

    def _on_graph_leave(self, _: Dict[str, Any]) -> None:
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)

    def _on_graph_mouse_wheel(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return

        mouse_wheel_up = self._graph.user_bind_event.delta > 0
        self._signature_zoom_level *= 1.1 if mouse_wheel_up else 0.9

        cursor_xy = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_xy)

    def _set_mode(self, mode: Mode) -> None:
        self._mode = mode
        self._set_disabled(self._scanner_options, mode == Mode.EDIT)
        self._set_disabled(self._signature_options, mode == Mode.PREVIEW)
        self._update_current_page()

    def _on_signature_selected(self, values: Dict[str, Any]) -> None:
        self._selected_signature_image = self._loaded_signatures[values["-DROPDOWN-"]]
        signature_frame_size = self._window["-SIGNATURE-IMAGE-"].get_size()
        self._window["-SIGNATURE-IMAGE-"].update(
            data=utils.image_to_bytes(
                utils.resize_and_pad_image(self._selected_signature_image, target_size=signature_frame_size)
            )
        )
        self._set_mode(Mode.EDIT)

    def _on_remove_selected(self, _: Dict[str, Any]) -> None:
        self._set_mode(Mode.EDIT)

    def _on_preview_selected(self, _: Dict[str, Any]) -> None:
        self._set_mode(Mode.PREVIEW)

    def _on_graph_clicked(self, values: Dict[str, Any]) -> None:
        cursor_xy = values["-GRAPH-"]
        if values["-REMOVE-"]:
            figure_ids_at_location = self._graph.get_figures_at_location(cursor_xy)
            for id_ in reversed(figure_ids_at_location):
                if id_ == self._current_page_figure_id:
                    continue
                self._graph.delete_figure(id_)
                self._pdf.delete_signature(id_)
                break  # Delete only a single signature at a time
        elif values["-PLACE-"]:
            if not self._pdf:
                print("Please load a PDF file before placing signatures.")
                return
            if self._floating_signature_figure_id is None:
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

    def _on_save_clicked(self, _: Dict[str, Any]) -> None:
        if self._pdf is None or not self._pdf.loaded:
            print("Please load a PDF file before saving.")
            return

        filename = sg.popup_get_file("Save pdf...", save_as=True)
        if filename:
            self._pdf.save(path=pl.Path(filename), filters=self._filters)

    def _redraw_page_signatures(self) -> None:
        page_signatures = self._pdf.get_page_signatures(self._current_page)
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

    def _navigate_page(self, delta: int) -> None:
        new_page_number = self._current_page + delta
        if new_page_number < 0 or new_page_number >= self._pdf.num_pages:
            return

        for id_ in self._pdf.get_page_signature_ids(self._current_page):
            self._graph.delete_figure(id_)
        self._current_page = new_page_number
        new_page_image = self._pdf.get_page_image(self._current_page, signed=self._mode == Mode.PREVIEW)
        self._update_page(new_page_image)

    def _on_previous_page_clicked(self, _: Dict[str, Any]) -> None:
        self._navigate_page(-1)

    def _on_next_page_clicked(self, _: Dict[str, Any]) -> None:
        self._navigate_page(1)

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
        self._set_disabled(self._window["-SAVE-"], False)
        self._set_disabled(self._mode_options, False)
        self._set_disabled(self._scanner_options, True)

    def _on_window_resized(self, _: Dict[str, Any]) -> None:
        if self._pdf is not None and self._pdf.loaded:
            current_page = self._pdf.get_page_image(self._current_page, signed=self._mode == Mode.PREVIEW)
            self._update_page(current_page)

    def _on_win_closed(self, _: Dict[str, Any]) -> None:
        self._running = False

    def _set_filter_enabled(self, event: Dict[str, Any], filter_: scanner.Filter, key: str) -> None:
        filter_.set_enabled(event[key])
        self._update_current_page()

    def _set_filter_strength(self, event: Dict[str, Any], filter_: scanner.Filter, key: str) -> None:
        filter_.set_strength(event[key])
        self._update_current_page()

    def _set_remove_background(self, event: Dict[str, Any]) -> None:
        self._pdf.set_remove_signature_background(event["-REMOVE-BG-"])
        self._update_current_page()

    def start(self) -> None:
        self._running = True

        self._window: sg.Window = self._create_window()
        self._window.bind("<Configure>", "-CONFIGURE-")

        self._graph: sg.Graph = self._window["-GRAPH-"]
        self._graph.bind("<Leave>", "+LEAVE")
        self._graph.bind("<MouseWheel>", "+WHEEL")

        self._event_handlers[sg.WIN_CLOSED] = self._on_win_closed
        self._event_handlers["-GRAPH-+MOVE"] = self._on_graph_move
        self._event_handlers["-GRAPH-+LEAVE"] = self._on_graph_leave
        self._event_handlers["-GRAPH-+WHEEL"] = self._on_graph_mouse_wheel
        self._event_handlers["-GRAPH-"] = self._on_graph_clicked
        self._event_handlers["-DROPDOWN-"] = self._on_signature_selected
        self._event_handlers["-REMOVE-BG-"] = self._set_remove_background
        self._event_handlers["-PLACE-"] = self._on_signature_selected
        self._event_handlers["-REMOVE-"] = self._on_remove_selected
        self._event_handlers["-PREVIEW-"] = self._on_preview_selected
        self._event_handlers["-SAVE-"] = self._on_save_clicked
        self._event_handlers["-PREVIOUS-"] = self._on_previous_page_clicked
        self._event_handlers["-NEXT-"] = self._on_next_page_clicked
        self._event_handlers["-PDF-FILE-"] = self._on_input_file_selected
        self._event_handlers["-SIGNATURE-BROWSE-"] = self._load_signatures
        self._event_handlers["-CONFIGURE-"] = self._on_window_resized

        self._set_disabled(self._mode_options, True)
        self._set_disabled(self._signature_options, True)
        self._set_disabled(self._scanner_options, True)

        for filter_ in self._filters:
            key = filter_.__class__.__name__.upper()
            self._event_handlers[f"-{key}-"] = lambda e, f=filter_, k=key: self._set_filter_enabled(e, f, f"-{k}-")
            if filter_.strength_range is not None:
                self._event_handlers[f"-{key}-STRENGTH-"] = lambda e, f=filter_, k=key: self._set_filter_strength(
                    e, f, f"-{k}-STRENGTH-"
                )

        while self._running:
            event, values = self._window.read()
            if event in self._event_handlers.keys():
                self._event_handlers[event](values)

        self._window.close()


if __name__ == "__main__":
    if int(platform.release()) >= 8:
        ctypes.windll.shcore.SetProcessDpiAwareness(True)

    app = FalsiSignPy()
    app.start()
