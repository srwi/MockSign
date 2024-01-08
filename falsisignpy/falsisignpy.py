import ctypes
import pathlib as pl
import platform
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

import PySimpleGUI as sg
import utils
from pdf import PDF
from PIL import Image
from scanner import Scanner
from signature import Signature

SIGNATURES_FOLDER = pl.Path(__file__).parent / "signatures"


class Mode(Enum):
    EDIT = 1
    PREVIEW = 2


class FalsiSignPy:
    def __init__(self) -> None:
        self._running = False
        self._scanner: Optional[Scanner] = None
        self._current_page_figure_id: Optional[int] = None
        self._current_page: int = 0
        self._floating_signature_figure_id: Optional[int] = None
        self._selected_signature_image = None
        self._loaded_signatures = None
        self._signature_zoom_level = 1.0
        self._scaling_factor = 1.0
        self._window: Optional[sg.Window] = None
        self._graph: Optional[sg.Graph] = None
        self._pdf: Optional[PDF] = None
        self._mode: Mode = Mode.PREVIEW
        self._event_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

    def _create_window(self) -> sg.Window:
        col_left = [
            [sg.T("Select input pdf file:")],
            [
                sg.Input(readonly=True, key="-INPUT-", enable_events=True),
                sg.FileBrowse(file_types=[("PDF", "*.pdf")]),
            ],
            [sg.HSeparator()],
            [sg.Text("Scanner effects:")],
            [
                sg.Checkbox("Random blur"),
                sg.Slider((0, 1), resolution=0.01, orientation="horizontal"),
            ],
            [
                sg.Checkbox("Random rotate"),
                sg.Slider((0, 1), resolution=0.01, orientation="horizontal"),
            ],
            [
                sg.Checkbox("Gamma"),
                sg.Slider((0, 1), resolution=0.01, orientation="horizontal"),
            ],
            [sg.Checkbox("Grayscale")],
            [sg.HSeparator()],
            [sg.Text("Place signature:")],
            [
                sg.Combo(
                    list(self._loaded_signatures.keys()),
                    default_value=list(self._loaded_signatures.keys())[0],
                    key="-DROPDOWN-",
                    enable_events=True,
                    readonly=True,
                )
            ],
            [sg.Radio("Place", key="-PLACE-", group_id=0, enable_events=True)],
            [sg.Radio("Remove", key="-REMOVE-", group_id=0, enable_events=True)],
            [sg.HSeparator()],
            [sg.Radio("Preview", key="-PREVIEW-", group_id=0, enable_events=True, default=True)],
        ]

        col_right = [
            [sg.Button("Save pdf...", key="-SAVE-")],
            [
                sg.Button("<", key="-PREVIOUS-"),
                sg.Text("No file loaded", key="-CURRENT-PAGE-"),
                sg.Button(">", key="-NEXT-"),
            ],
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
        ]

        layout = [
            [sg.Col(col_left), sg.Col(col_right, expand_y=True, expand_x=True)],
            [sg.Text(key="-INFO-", size=(60, 1))],
        ]

        return sg.Window("FalsiSignPy", layout, finalize=True, resizable=True)

    @staticmethod
    def _load_signatures_or_fail(path: pl.Path) -> Dict[str, Image.Image]:
        signatures = {}
        for file in path.glob("*"):
            signatures[file.name] = Image.open(file)
        if len(signatures) == 0:
            sg.popup_error(
                f"No signatures found. Place some signatures inside of "
                f"the '{SIGNATURES_FOLDER}' folder and restart FalsiSignPy.",
                title="No signatures found",
            )
            exit(1)
        return signatures

    def _place_floating_signature(self, signature_image: Image.Image, cursor_position: Tuple[int, int]) -> None:
        new_size = (
            int(signature_image.width * self._signature_zoom_level / self._scaling_factor),
            int(signature_image.height * self._signature_zoom_level / self._scaling_factor),
        )
        scaled_signature_image = signature_image.copy().resize(new_size)
        scaled_signature_bytes = utils.image_to_bytes(scaled_signature_image)

        placed_figure: int = self._graph.draw_image(data=scaled_signature_bytes, location=cursor_position)
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)
            self._floating_signature_figure_id = None
        self._floating_signature_figure_id = placed_figure

    def _describe_page(self, page_number: int) -> str:
        return f"Page {page_number + 1}/{self._pdf.num_pages}"

    def _update_page(self, page_image: Image.Image) -> None:
        new_page_image = page_image.copy()
        print("update page", self._mode)
        if self._mode == Mode.PREVIEW:
            new_page_image = self._scanner.apply(new_page_image)

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

        self._window["-CURRENT-PAGE-"].update(self._describe_page(self._current_page))

        if self._mode == Mode.EDIT:
            self._redraw_page_signatures()

    def _update_current_page(self) -> None:
        if self._pdf is None or not self._pdf.loaded:
            return

        current_page_image = self._pdf.get_page_image(self._current_page)
        self._update_page(current_page_image)

    def _on_graph_move(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return

        cursor_position = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_position)

    def _on_graph_leave(self, _: Dict[str, Any]) -> None:
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)

    def _on_graph_mouse_wheel(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return

        mouse_wheel_up = self._graph.user_bind_event.delta > 0
        self._signature_zoom_level *= 1.1 if mouse_wheel_up else 0.9

        cursor_position = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_position)

    def _set_mode(self, mode: Mode) -> None:
        self._mode = mode
        self._update_current_page()

    def _on_signature_selected(self, values: Dict[str, Any]) -> None:
        self._selected_signature_image = self._loaded_signatures[values["-DROPDOWN-"]]
        self._set_mode(Mode.EDIT)

    def _on_remove_selected(self, _: Dict[str, Any]) -> None:
        self._set_mode(Mode.EDIT)

    def _on_preview_selected(self, _: Dict[str, Any]) -> None:
        self._set_mode(Mode.PREVIEW)

    def _on_graph_clicked(self, values: Dict[str, Any]) -> None:
        cursor_position = values["-GRAPH-"]
        if values["-REMOVE-"]:
            figure_ids_at_location = self._graph.get_figures_at_location(cursor_position)
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
                location=cursor_position,
                scale=self._signature_zoom_level,
            )
            self._pdf.place_signature(
                signature=placed_signature,
                identifier=self._floating_signature_figure_id,
                page_number=self._current_page,
            )
            self._floating_signature_figure_id = None  # Anchor floating signature

    @staticmethod
    def _on_save_clicked(_: Dict[str, Any]) -> None:
        filename = sg.popup_get_file("Save pdf...", save_as=True)
        if filename is not None:
            pass

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
        new_page_image = self._pdf.get_page_image(self._current_page)
        self._update_page(new_page_image)

    def _on_previous_page_clicked(self, _: Dict[str, Any]) -> None:
        self._navigate_page(-1)

    def _on_next_page_clicked(self, _: Dict[str, Any]) -> None:
        self._navigate_page(1)

    def _on_input_file_selected(self, values: Dict[str, Any]) -> None:
        input_file = values["-INPUT-"]
        if not input_file:
            return
        filename = pl.Path(input_file)
        self._pdf = PDF(filename)
        current_page = self._pdf.get_page_image(self._current_page)
        self._update_page(current_page)

    def _on_window_resized(self, _: Dict[str, Any]) -> None:
        if self._pdf is not None and self._pdf.loaded:
            current_page = self._pdf.get_page_image(self._current_page)
            self._update_page(current_page)

    def _on_win_closed(self, _: Dict[str, Any]) -> None:
        self._running = False

    def start(self) -> None:
        self._running = True
        self._scanner = Scanner()
        self._loaded_signatures = self._load_signatures_or_fail(SIGNATURES_FOLDER)

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
        self._event_handlers["-PLACE-"] = self._on_signature_selected
        self._event_handlers["-REMOVE-"] = self._on_remove_selected
        self._event_handlers["-PREVIEW-"] = self._on_preview_selected
        self._event_handlers["-SAVE-"] = self._on_save_clicked
        self._event_handlers["-PREVIOUS-"] = self._on_previous_page_clicked
        self._event_handlers["-NEXT-"] = self._on_next_page_clicked
        self._event_handlers["-INPUT-"] = self._on_input_file_selected
        self._event_handlers["-CONFIGURE-"] = self._on_window_resized

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
