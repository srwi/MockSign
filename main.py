import ctypes
import pathlib as pl
import platform
from typing import Dict, Callable, Any, Optional, Tuple

import PySimpleGUI as sg
from PIL import Image

import utils
from pdf import PDF
from scanner import Scanner, ScannerMode
from signature import Signature

SIGNATURES_FOLDER = pl.Path("signatures")


class FalsiSignPy:

    def __init__(self):
        self._running = False
        self._scanner: Optional[Scanner] = None
        self._current_page_figure_id = None
        self._floating_signature_figure_id: Optional[int] = None
        self._selected_signature_image = None
        self._loaded_signatures = None
        self._signature_zoom_level = 1.
        self._scaling_factor = 1.
        self._window: Optional[sg.Window] = None
        self._graph: Optional[sg.Graph] = None
        self._pdf: Optional[PDF] = None
        self._event_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

    def create_window(self) -> sg.Window:
        sg.theme('Dark Grey 13')

        col_left = [
            [sg.T("Select input pdf file:")],
            [sg.Input(readonly=True, key="-INPUT-", enable_events=True), sg.FileBrowse(file_types=[("PDF", "*.pdf")])],
            [sg.HSeparator()],
            [sg.Text("Scanner effects:")],
            [sg.Checkbox("Random blur"), sg.Slider((0, 1), resolution=0.01, orientation="horizontal")],
            [sg.Checkbox("Random rotate"), sg.Slider((0, 1), resolution=0.01, orientation="horizontal")],
            [sg.Checkbox("Gamma"), sg.Slider((0, 1), resolution=0.01, orientation="horizontal")],
            [sg.Checkbox("Grayscale")],
            [sg.HSeparator()],
            [sg.Text("Place signature:")],
            [sg.Combo(list(self._loaded_signatures.keys()), default_value=list(self._loaded_signatures.keys())[0], key="-DROPDOWN-", enable_events=True, readonly=True)],
            [sg.Radio("Place", key="-PLACE-", group_id=0, enable_events=True)],
            [sg.Radio("Remove", key="-REMOVE-", group_id=0)],
            [sg.HSeparator()],
            [sg.Radio("Preview", key="-PREVIEW-", group_id=0, default=True)],
        ]

        col_right = [
            [sg.Button("Save pdf...", key="-SAVE-")],
            [sg.Button("<", key="-PREVIOUS-"), sg.Text("No file loaded", key="-CURRENT-PAGE-"), sg.Button(">", key="-NEXT-")],
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
            [sg.Text(key="-INFO-", size=(60, 1))]
        ]

        return sg.Window("FalsiSignPy", layout, finalize=True, resizable=True)

    @staticmethod
    def load_signatures_or_fail(path: pl.Path):
        signatures = {}
        for file in path.glob("*"):
            signatures[file.name] = Image.open(file)
        if len(signatures) == 0:
            sg.popup_error(f"No signatures found. Place some signatures inside of the '{SIGNATURES_FOLDER}' folder and restart FalsiSignPy.",
                           title="No signatures found")
            exit(1)
        return signatures

    def _place_floating_signature(self, signature_image: Image.Image, cursor_position: Tuple[int, int]) -> None:
        new_size = (int(signature_image.width * self._signature_zoom_level / self._scaling_factor),
                    int(signature_image.height * self._signature_zoom_level / self._scaling_factor))
        scaled_signature_image = signature_image.copy().resize(new_size)
        scaled_signature_bytes = utils.image_to_bytes(scaled_signature_image)

        placed_figure: int = self._graph.draw_image(data=scaled_signature_bytes, location=cursor_position)
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)
            self._floating_signature_figure_id = None
        self._floating_signature_figure_id = placed_figure

    def update_page(self, page_image: Image.Image) -> None:
        print("dsfsa")

        new_page_image = self._scanner.apply(page_image)

        # Match document coordinate system
        graph_size = self._graph.get_size()
        self._graph.CanvasSize = graph_size  # https://github.com/PySimpleGUI/PySimpleGUI/issues/6451
        _, _, _, _, self._scaling_factor = utils.calculate_padded_image_coordinates(new_page_image.size, graph_size)
        h_offset = ((graph_size[0] * self._scaling_factor) - new_page_image.width) / 2
        v_offset = ((graph_size[1] * self._scaling_factor) - new_page_image.height) / 2
        self._graph.change_coordinates(
            graph_bottom_left=(-h_offset, -v_offset),
            graph_top_right=(new_page_image.width + h_offset, new_page_image.height + v_offset)
        )

        # Update page figure
        new_page_image_resized = utils.resize_and_pad_image(new_page_image, target_size=graph_size)
        if self._current_page_figure_id is not None:
            self._graph.delete_figure(self._current_page_figure_id)
        self._current_page_figure_id = self._graph.draw_image(
            data=utils.image_to_bytes(new_page_image_resized),
            location=(-h_offset, v_offset + new_page_image.height)
        )

        self._window["-CURRENT-PAGE-"].update(self._pdf.page_description)

        self._redraw_page_signatures()

    def on_graph_move(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return

        cursor_position = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_position)

    def on_graph_leave(self, _: Dict[str, Any]):
        if self._floating_signature_figure_id is not None:
            self._graph.delete_figure(self._floating_signature_figure_id)

    def on_graph_mouse_wheel(self, values: Dict[str, Any]):
        if not values["-PLACE-"]:
            return

        mouse_wheel_up = self._graph.user_bind_event.delta > 0
        self._signature_zoom_level *= 1.1 if mouse_wheel_up else 0.9

        cursor_position = values["-GRAPH-"]
        self._place_floating_signature(self._selected_signature_image, cursor_position)

    def on_signature_selected(self, values: Dict[str, Any]):
        self._selected_signature_image = self._loaded_signatures[values["-DROPDOWN-"]]
        self._scanner.set_mode(ScannerMode.EDIT)

    def on_remove_selected(self, _: Dict[str, Any]):
        self._scanner.set_mode(ScannerMode.EDIT)

    def on_preview_selected(self, _: Dict[str, Any]):
        self._scanner.set_mode(ScannerMode.PREVIEW)

    def on_graph_clicked(self, values: Dict[str, Any]):
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
            placed_signature = Signature(image=self._selected_signature_image,
                                         location=cursor_position,
                                         scale=self._signature_zoom_level)
            self._pdf.place_signature(placed_signature, self._floating_signature_figure_id)
            # Anchor floating signature
            self._floating_signature_figure_id = None

    @staticmethod
    def on_save_clicked(_: Dict[str, Any]):
        filename = sg.popup_get_file("Save pdf...", save_as=True)
        if filename is not None:
            pass

    def _redraw_page_signatures(self):
        page_signatures = self._pdf.get_current_page_signatures()
        self._pdf.clear_current_page_signatures()
        for signature in page_signatures:
            scaled_signature = signature.get_scaled_signature()
            scaled_signature = scaled_signature.resize((int(scaled_signature.width / self._scaling_factor), int(scaled_signature.height / self._scaling_factor)))
            graph_location = signature.get_location()
            scaled_signature_bytes = utils.image_to_bytes(scaled_signature)
            signature_id = self._graph.draw_image(data=scaled_signature_bytes,
                                                  location=graph_location)
            self._pdf.place_signature(signature=signature, identifier=signature_id)

    def on_previous_page_clicked(self, _: Dict[str, Any]):
        previous_page = self._pdf.select_and_get_previous_page_image()
        self.update_page(previous_page)

    def on_next_page_clicked(self, _: Dict[str, Any]):
        next_page = self._pdf.select_and_get_next_page_image()
        self.update_page(next_page)

    def on_input_file_selected(self, values: Dict[str, Any]):
        filename = pl.Path(values["-INPUT-"])
        self._pdf = PDF(filename)
        current_page = self._pdf.get_current_page_image()
        self.update_page(current_page)

    def on_window_resized(self, _: Dict[str, Any]):
        if self._pdf is not None and self._pdf.loaded:
            current_page = self._pdf.get_current_page_image()
            self.update_page(current_page)

    def on_win_closed(self, _: Dict[str, Any]) -> None:
        self._running = False

    def start(self):
        self._running = True
        self._scanner = Scanner()
        self._loaded_signatures = self.load_signatures_or_fail(SIGNATURES_FOLDER)

        self._window: sg.Window = self.create_window()
        self._window.bind("<Configure>", "-CONFIGURE-")

        self._graph: sg.Graph = self._window["-GRAPH-"]
        self._graph.bind("<Leave>", "+LEAVE")
        self._graph.bind("<MouseWheel>", "+WHEEL")

        self._event_handlers[sg.WIN_CLOSED] = self.on_win_closed
        self._event_handlers["-GRAPH-+MOVE"] = self.on_graph_move
        self._event_handlers["-GRAPH-+LEAVE"] = self.on_graph_leave
        self._event_handlers["-GRAPH-+WHEEL"] = self.on_graph_mouse_wheel
        self._event_handlers["-GRAPH-"] = self.on_graph_clicked
        self._event_handlers["-DROPDOWN-"] = self.on_signature_selected
        self._event_handlers["-PLACE-"] = self.on_signature_selected
        self._event_handlers["-REMOVE-"] = self.on_remove_selected
        self._event_handlers["-PREVIEW-"] = self.on_preview_selected
        self._event_handlers["-SAVE-"] = self.on_save_clicked
        self._event_handlers["-PREVIOUS-"] = self.on_previous_page_clicked
        self._event_handlers["-NEXT-"] = self.on_next_page_clicked
        self._event_handlers["-INPUT-"] = self.on_input_file_selected
        self._event_handlers["-CONFIGURE-"] = self.on_window_resized

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
