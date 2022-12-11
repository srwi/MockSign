import pathlib as pl
from typing import List

import fitz
from PIL import Image


class Scanner:
    def __init__(self):
        self.pages: List[Image] = []

    def open_pdf(self, path: pl.Path) -> None:
        self.pages = []
        document = fitz.Document(path)
        for i in range(document.page_count):
            page = document.load_page(i)
            pixmap = page.get_pixmap()
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self.pages.append(image)

    def save_transformed_pdf(self, path: pl.Path) -> None:
        self.pages[0].save(path,
                           "PDF",
                           resolution=100.0,
                           save_all=True,
                           append_images=self.pages[1:])

    def get_transformed_page(self, page: int) -> Image:
        return self.pages[page]
