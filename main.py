import pathlib as pl
from typing import Dict, Callable, Any, Optional

import PySimpleGUI as sg
from PIL import Image

import utils
from pdf import PDF
from scanner import Scanner, ScannerMode

SIGNATURES_FOLDER = pl.Path("signatures")


class FalsiSignPy:

    def __init__(self):
        self._scanner: Optional[Scanner] = None
        self._floating_signature = None
        self._selected_signature = None
        self._current_page_image = None
        self._loaded_signatures = None
        self._window = None
        self._graph = None
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
            image = Image.open(file)
            signatures[file.name] = utils.convert_pil_image_to_byte_data(image)
        if len(signatures) == 0:
            sg.popup_error(f"No signatures found. Place some signatures inside of the '{SIGNATURES_FOLDER}' folder and restart FalsiSignPy.",
                           title="No signatures found")
            exit(1)
        return signatures

    def update_page(self, page_image: Image.Image) -> None:
        new_page_image = self._scanner.apply(page_image, self._window["-GRAPH-"].get_size(), as_bytes=True)
        if self._current_page_image is not None:
            self._graph.delete_figure(self._current_page_image)
        self._current_page_image = self._graph.draw_image(data=new_page_image, location=(0, 800))
        self._window["-CURRENT-PAGE-"].update(self._pdf.page_description)

    def start(self):
        self._scanner = Scanner()
        self._loaded_signatures = self.load_signatures_or_fail(pl.Path(SIGNATURES_FOLDER))

        self._window: sg.Window = self.create_window()
        self._window.bind("<Configure>", "-CONFIGURE-")

        self._graph: sg.Graph = self._window["-GRAPH-"]
        self._graph.bind("<Leave>", "+LEAVE")

        while True:
            event, values = self._window.read()

            if event == sg.WIN_CLOSED:
                break

            if event == "-GRAPH-+MOVE" and values["-PLACE-"]:
                if self._floating_signature is not None:
                    self._graph.delete_figure(self._floating_signature)
                cursor_position = values["-GRAPH-"]
                self._floating_signature = self._graph.draw_image(data=self._selected_signature, location=cursor_position)

            elif event == "-GRAPH-+LEAVE":
                if self._floating_signature is not None:
                    self._graph.delete_figure(self._floating_signature)

            elif event == "-GRAPH-+UP":
                self._floating_signature = None  # Anchor floating signature

            elif event == "-DROPDOWN-":
                self._selected_signature = self._loaded_signatures[values["-DROPDOWN-"]]
                self._scanner.mode = ScannerMode.EDIT

            elif event == "-PLACE-":
                self._selected_signature = self._loaded_signatures[values["-DROPDOWN-"]]
                self._scanner.mode = ScannerMode.EDIT

            elif event == "-REMOVE-":
                self._scanner.mode = ScannerMode.EDIT

            elif event == "-PREVIEW-":
                self._scanner.mode = ScannerMode.PREVIEW

            elif event == "-GRAPH-" and values["-REMOVE-"]:
                cursor_position = values["-GRAPH-"]
                figures_at_location = self._graph.get_figures_at_location(cursor_position)
                for figure in figures_at_location:
                    if figure == self._current_page_image:
                        continue
                    self._graph.delete_figure(figure)

            elif event == "-SAVE-":
                filename = sg.popup_get_file("Save pdf...", save_as=True)
                if filename is not None:
                    pass

            elif event == "-PREVIOUS-":
                previous_page = self._pdf.select_and_get_previous_page()
                self.update_page(previous_page)

            elif event == "-NEXT-":
                next_page = self._pdf.select_and_get_next_page()
                self.update_page(next_page)

            elif event == "-INPUT-":
                filename = values["-INPUT-"]
                self._pdf = PDF(pl.Path(filename))
                current_page = self._pdf.get_current_page()
                self.update_page(current_page)

            elif event == "-CONFIGURE-":
                if self._pdf is not None and self._pdf.loaded:
                    current_page = self._pdf.get_current_page()
                    self.update_page(current_page)

    def close(self):
        self._window.close()


if __name__ == "__main__":
    app = FalsiSignPy()
    app.start()
    app.close()
