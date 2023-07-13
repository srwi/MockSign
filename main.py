import pathlib as pl
from typing import Dict, Callable, Any, Optional, Tuple

import PySimpleGUI as sg
from PIL import Image

import utils
from pdf import PDF
from scanner import Scanner, ScannerMode, Signature

SIGNATURES_FOLDER = pl.Path("signatures")


class FalsiSignPy:

    def __init__(self):
        self._running = False
        self._scanner: Optional[Scanner] = None
        self._current_page_figure = None
        self._floating_signature_figure = None
        self._selected_signature_image = None
        self._loaded_signatures = None
        self._signature_zoom_level = 1.
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
            [sg.Button("<", key="-PREVIOUS-"), sg.Text("Page 1 / 10", key="-CURRENT-PAGE-"), sg.Button(">", key="-NEXT-")],
            [
                sg.Graph(
                    canvas_size=(400, 400),
                    graph_bottom_left=(0, 0),
                    graph_top_right=(800, 800),
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

    def _place_scaled_signature(self, signature_image: Image.Image, cursor_position: Tuple[int, int], floating: bool) -> None:
        new_size = (int(signature_image.width * self._signature_zoom_level),
                    int(signature_image.height * self._signature_zoom_level))
        scaled_signature_image = signature_image.copy().resize(new_size)
        scaled_signature_bytes = utils.convert_pil_image_to_byte_data(scaled_signature_image)
        signature_position = (cursor_position[0] - scaled_signature_image.width // 2,
                              cursor_position[1] + scaled_signature_image.height // 2)

        placed_figure = self._graph.draw_image(data=scaled_signature_bytes, location=signature_position)
        if self._floating_signature_figure is not None:
            self._graph.delete_figure(self._floating_signature_figure)
            self._floating_signature_figure = None
        if floating:
            self._floating_signature_figure = placed_figure

    def update_page(self, page_image: Image.Image) -> None:
        new_page_image = self._scanner.apply(page_image, self._window["-GRAPH-"].get_size(), as_bytes=True)
        if self._current_page_figure is not None:
            self._graph.delete_figure(self._current_page_figure)
        self._current_page_figure = self._graph.draw_image(data=new_page_image, location=(0, 800))
        self._window["-CURRENT-PAGE-"].update(self._pdf.page_description)

    def on_graph_move(self, values: Dict[str, Any]) -> None:
        if not values["-PLACE-"]:
            return

        cursor_position = values["-GRAPH-"]
        self._place_scaled_signature(self._selected_signature_image, cursor_position, floating=True)

    def on_graph_leave(self, _: Dict[str, Any]):
        if self._floating_signature_figure is not None:
            self._graph.delete_figure(self._floating_signature_figure)

    def on_graph_mouse_wheel(self, values: Dict[str, Any]):
        if not values["-PLACE-"]:
            return

        mouse_wheel_up = self._graph.user_bind_event.delta > 0
        self._signature_zoom_level *= 1.1 if mouse_wheel_up else 0.9

        cursor_position = values["-GRAPH-"]
        self._place_scaled_signature(self._selected_signature_image, cursor_position, floating=True)

    def on_signature_selected(self, values: Dict[str, Any]):
        self._selected_signature_image = self._loaded_signatures[values["-DROPDOWN-"]]
        self._scanner.mode = ScannerMode.EDIT

    def on_remove_selected(self, _: Dict[str, Any]):
        self._scanner.mode = ScannerMode.EDIT

    def on_preview_selected(self, _: Dict[str, Any]):
        self._scanner.mode = ScannerMode.PREVIEW

    def on_graph_clicked(self, values: Dict[str, Any]):
        cursor_position = values["-GRAPH-"]
        if values["-REMOVE-"]:
            figures_at_location = self._graph.get_figures_at_location(cursor_position)
            for figure in figures_at_location:
                if figure == self._current_page_figure:
                    continue
                self._graph.delete_figure(figure)
        elif values["-PLACE-"]:
            placed_signature = Signature(self._selected_signature_image,
                                         self._pdf.current_page if self._pdf else 0,
                                         cursor_position,
                                         self._signature_zoom_level,
                                         self._floating_signature_figure)
            self._scanner.place_signature(placed_signature)
            # Anchor floating signature
            self._floating_signature_figure = None

    @staticmethod
    def on_save_clicked(_: Dict[str, Any]):
        filename = sg.popup_get_file("Save pdf...", save_as=True)
        if filename is not None:
            pass

    def on_previous_page_clicked(self, _: Dict[str, Any]):
        previous_page = self._pdf.select_and_get_previous_page()
        self.update_page(previous_page)

    def on_next_page_clicked(self, _: Dict[str, Any]):
        next_page = self._pdf.select_and_get_next_page()
        self.update_page(next_page)

    def on_input_file_selected(self, values: Dict[str, Any]):
        filename = values["-INPUT-"]
        self._pdf = PDF(pl.Path(filename))
        current_page = self._pdf.get_current_page()
        self.update_page(current_page)

    def on_window_resized(self, _: Dict[str, Any]):
        if self._pdf is not None and self._pdf.loaded:
            current_page = self._pdf.get_current_page()
            self.update_page(current_page)

    def on_win_closed(self, _: Dict[str, Any]) -> None:
        self._running = False

    def start(self):
        self._running = True
        self._scanner = Scanner()
        self._loaded_signatures = self.load_signatures_or_fail(pl.Path(SIGNATURES_FOLDER))

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
    app = FalsiSignPy()
    app.start()
