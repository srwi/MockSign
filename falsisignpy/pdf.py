import pathlib as pl
from typing import Dict, List

import fitz
from PIL import Image

from signature import Signature


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

        self._signatures: List[Dict[int, Signature]] = [{} for _ in self._pages]

    def place_signature(self, signature: Signature, identifier: int) -> None:
        self._signatures[self._current_page][identifier] = signature

    def delete_signature(self, identifier: int) -> None:
        del self._signatures[self._current_page][identifier]

    def save(self, path: pl.Path) -> None:
        if len(self._pages) == 0:
            raise RuntimeError("Can not save empty document.")

        self._pages[0].save(path, "PDF", resolution=100.0, save_all=True, append_images=self._pages[1:])

    def get_current_page_image(self) -> Image.Image:
        return self.get_page_image(self._current_page)

    def get_page_image(self, page_number: int) -> Image.Image:
        if not self.loaded:
            raise RuntimeError("No pdf loaded.")

        return self._pages[page_number]

    def get_page_signatures(self, page_number: int) -> List[Signature]:
        return list(self._signatures[page_number].values())

    def get_current_page_signatures(self) -> List[Signature]:
        return self.get_page_signatures(self._current_page)

    def clear_current_page_signatures(self) -> None:
        self._signatures[self._current_page] = {}

    def select_and_get_next_page_image(self) -> Image.Image:
        self._current_page = min(self._current_page + 1, self.num_pages - 1)
        return self.get_current_page_image()

    def select_and_get_previous_page_image(self) -> Image.Image:
        self._current_page = max(self._current_page - 1, 0)
        return self.get_current_page_image()

    @property
    def page_description(self) -> str:
        if not self.loaded:
            return ""

        return f"Page {self._current_page + 1} / {self.num_pages}"

    @property
    def num_pages(self) -> int:
        return len(self._pages)

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def loaded(self) -> bool:
        return len(self._pages) > 0
