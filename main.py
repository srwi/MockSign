import io
import pathlib as pl

import PySimpleGUI as sg
from PIL import ImageGrab, Image

SIGNATURES_FOLDER = pl.Path("signatures")


def load_signatures_or_fail(path: pl.Path):
    signatures = {}
    for file in path.glob("*"):
        image = Image.open(file)
        with io.BytesIO() as output:
            image.save(output, format="PNG")
            signatures[file.name] = output.getvalue()
    if len(signatures) == 0:
        sg.popup_error(f"No signatures found. Place some signatures inside of the '{SIGNATURES_FOLDER}' folder and restart FalsiSignPy.",
                       title="No signatures found")
        exit(1)
    return signatures


def save_element_as_file(element, filename):
    """
    Saves any element as an image file.  Element needs to have an underlyiong Widget available (almost if not all of them do)
    :param element: The element to save
    :param filename: The filename to save to. The extension of the filename determines the format (jpg, png, gif, ?)
    """
    widget = element.Widget
    box = (widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_rootx() + widget.winfo_width(), widget.winfo_rooty() + widget.winfo_height())
    grab = ImageGrab.grab(bbox=box)
    grab.save(filename)


def main():
    sg.theme('Dark Grey 13')
    loaded_signatures = load_signatures_or_fail(pl.Path(SIGNATURES_FOLDER))

    col_left = [
        [sg.T("Select input pdf file:")],
        [sg.InputText(disabled=True), sg.FileBrowse()],
        [sg.HSeparator()],
        [sg.Text("Scanner effects:")],
        [sg.Checkbox("Random blur"), sg.Slider((0, 1), resolution=0.01, orientation="horizontal")],
        [sg.Checkbox("Random rotate"), sg.Slider((0, 1), resolution=0.01, orientation="horizontal")],
        [sg.Checkbox("Gamma"), sg.Slider((0, 1), resolution=0.01, orientation="horizontal")],
        [sg.Checkbox("Grayscale")],
        [sg.HSeparator()],
        [sg.Text("Place signature:")],
        [sg.DropDown(list(loaded_signatures.keys()), default_value=list(loaded_signatures.keys())[0], key="-DROPDOWN-", enable_events=True, readonly=True)],
        [sg.Radio("Place", key="-PLACE-", group_id=0, enable_events=True)],
        [sg.Radio("Remove", key="-REMOVE-", group_id=0)],
        [sg.HSeparator()],
        [sg.Radio("Preview", key="-PREVIEW-", group_id=0, default=True)],
    ]

    col_right = [
        [
            sg.Graph(
                canvas_size=(400, 400),
                graph_bottom_left=(0, 0),
                graph_top_right=(800, 800),
                key="-GRAPH-",
                enable_events=True,
                background_color='lightblue',
                drag_submits=True,
                motion_events=True,
            )
        ],
        [sg.Button("<", key="-PREVIOUS-"), sg.Text("Page 1 / 10", key="-CURRENT-PAGE-"), sg.Button(">", key="-NEXT-")],
        [sg.Button("Save pdf...", key="-SAVE-")]
    ]

    layout = [
        [sg.Col(col_left, key="-COL-LEFT-"), sg.Col(col_right, key="-COL-RIGHT-")],
        [sg.Text(key="-INFO-", size=(60, 1))]
    ]

    window = sg.Window("FalsiSignPy", layout, finalize=True)
    graph = window["-GRAPH-"]  # type: sg.Graph
    graph.bind("<Leave>", "+LEAVE")
    floating_signature = None
    selected_signature = None

    while True:
        event, values = window.read()
        print(event, values)

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
            print(values["-DROPDOWN-"])
            selected_signature = loaded_signatures[values["-DROPDOWN-"]]

        elif event == "-GRAPH-" and values["-REMOVE-"]:
            cursor_position = values["-GRAPH-"]
            signatures = graph.get_figures_at_location(cursor_position)
            for signature in signatures:
                graph.delete_figure(signature)

        elif event == "-SAVE-":
            filename = sg.popup_get_file("Save pdf...", save_as=True)
            if filename is not None:
                save_element_as_file(window["-GRAPH-"], filename)

    window.close()


if __name__ == "__main__":
    main()
