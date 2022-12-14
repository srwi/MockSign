import io
import pathlib as pl

import PySimpleGUI as sg
from PIL import Image

from scanner import Scanner

SIGNATURES_FOLDER = pl.Path("signatures")


def convert_pil_image_to_byte_data(image: Image):
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def load_signatures_or_fail(path: pl.Path):
    signatures = {}
    for file in path.glob("*"):
        image = Image.open(file)
        signatures[file.name] = convert_pil_image_to_byte_data(image)
    if len(signatures) == 0:
        sg.popup_error(f"No signatures found. Place some signatures inside of the '{SIGNATURES_FOLDER}' folder and restart FalsiSignPy.",
                       title="No signatures found")
        exit(1)
    return signatures


def main():
    sg.theme('Dark Grey 13')
    loaded_signatures = load_signatures_or_fail(pl.Path(SIGNATURES_FOLDER))
    scanner = Scanner()

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
        [sg.Combo(list(loaded_signatures.keys()), default_value=list(loaded_signatures.keys())[0], key="-DROPDOWN-", enable_events=True, readonly=True)],
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

    window = sg.Window("FalsiSignPy", layout, finalize=True, resizable=True)
    window.bind("<Configure>", "-CONFIGURE-")
    graph: sg.Graph = window["-GRAPH-"]
    graph.bind("<Leave>", "+LEAVE")
    floating_signature = None
    selected_signature = None
    current_page_image = None
    current_page = 0

    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED:
            break

        if event == "-GRAPH-+MOVE" and values["-PLACE-"]:
            cursor_position = values["-GRAPH-"]

            if floating_signature is not None:
                graph.delete_figure(floating_signature)
            floating_signature = graph.draw_image(data=selected_signature, location=cursor_position)

        elif event == "-GRAPH-+LEAVE":
            if floating_signature is not None:
                graph.delete_figure(floating_signature)

        elif event == "-GRAPH-+UP":
            floating_signature = None  # Anchor floating signature

        elif event in ["-PLACE-", "-DROPDOWN-"]:
            selected_signature = loaded_signatures[values["-DROPDOWN-"]]

        elif event == "-GRAPH-" and values["-REMOVE-"]:
            cursor_position = values["-GRAPH-"]
            figures_at_location = graph.get_figures_at_location(cursor_position)
            for figure in figures_at_location:
                if figure == current_page_image:
                    continue
                graph.delete_figure(figure)

        elif event == "-SAVE-":
            filename = sg.popup_get_file("Save pdf...", save_as=True)
            if filename is not None:
                pass

        elif event == "-PREVIOUS-":
            current_page = max(0, current_page - 1)
            if current_page_image is not None:
                graph.delete_figure(current_page_image)
            current_page_image = graph.draw_image(data=convert_pil_image_to_byte_data(scanner.get_transformed_page(current_page, resize=window["-GRAPH-"].get_size())), location=(0, 800))
            window["-CURRENT-PAGE-"].update(f"Page {current_page + 1} / {len(scanner.pages)}")

        elif event == "-NEXT-":
            current_page = min(current_page + 1, len(scanner.pages) - 1)
            if current_page_image is not None:
                graph.delete_figure(current_page_image)
            current_page_image = graph.draw_image(data=convert_pil_image_to_byte_data(scanner.get_transformed_page(current_page, resize=window["-GRAPH-"].get_size())), location=(0, 800))
            window["-CURRENT-PAGE-"].update(f"Page {current_page + 1} / {len(scanner.pages)}")

        elif event == "-INPUT-":
            filename = values["-INPUT-"]
            scanner.open_pdf(pl.Path(filename))
            if current_page_image is not None:
                graph.delete_figure(current_page_image)
            current_page_image = graph.draw_image(data=convert_pil_image_to_byte_data(scanner.get_transformed_page(current_page, resize=window["-GRAPH-"].get_size())), location=(0, 800))
            window["-CURRENT-PAGE-"].update(f"Page {current_page + 1} / {len(scanner.pages)}")

        elif event == "-CONFIGURE-":
            if len(scanner.pages) > 0:
                if current_page_image is not None:
                    graph.delete_figure(current_page_image)
                current_page_image = graph.draw_image(data=convert_pil_image_to_byte_data(scanner.get_transformed_page(current_page, resize=window["-GRAPH-"].get_size())), location=(0, 800))

    window.close()


if __name__ == "__main__":
    main()
