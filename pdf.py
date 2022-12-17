import pathlib as pl

import fitz
from PIL import Image


class PDF:
    def __init__(self, path: pl.Path) -> None:
        self._current_page: int = 0
        self._pages = []

        document = fitz.Document(path)
        for i in range(document.page_count):
            page = document.load_page(i)
            pixmap = page.get_pixmap(dpi=150)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self._pages.append(image)

    def save(self, path: pl.Path) -> None:
        if len(self._pages) == 0:
            raise RuntimeError("Can not save empty document.")

        self._pages[0].save(path,
                            "PDF",
                            resolution=100.0,
                            save_all=True,
                            append_images=self._pages[1:])

    def get_current_page(self) -> Image.Image:
        return self.get_page(self._current_page)

    def get_page(self, page_number: int) -> Image.Image:
        if not self.loaded:
            raise RuntimeError("No pdf loaded.")

        return self._pages[page_number]

    def select_and_get_next_page(self) -> Image.Image:
        self._current_page = min(self._current_page + 1, self.num_pages - 1)
        return self.get_current_page()

    def select_and_get_previous_page(self) -> Image.Image:
        self._current_page = max(self._current_page + 1, 0)
        return self.get_current_page()

    @property
    def page_description(self) -> str:
        if not self.loaded:
            return ""

        return f"Page {self._current_page + 1} / {self.num_pages}"

    @property
    def num_pages(self) -> int:
        return len(self._pages)

    @property
    def loaded(self) -> bool:
        return len(self._pages) > 0
