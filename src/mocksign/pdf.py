import pathlib as pl
from typing import Dict, List

import fitz
from PIL import Image

from . import filter
from .signature import Signature


class PDF:
    def __init__(self, path: pl.Path, remove_signature_background: bool) -> None:
        self._pages: List[Image.Image] = []
        self._remove_signature_background = remove_signature_background

        document = fitz.Document(path)
        for i in range(document.page_count):
            page = document.load_page(i)
            pixmap = page.get_pixmap(dpi=150)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self._pages.append(image)

        self._signatures: List[Dict[int, Signature]] = [{} for _ in self._pages]

    def place_signature(self, page_number: int, signature: Signature, identifier: int) -> None:
        if page_number >= len(self._pages):
            raise RuntimeError(f"Page {page_number} does not exist.")

        for i, page_signatures in enumerate(self._signatures):
            if identifier in page_signatures:
                raise RuntimeError(f"Signature with identifier {identifier} already exists on page {i}.")

        self._signatures[page_number][identifier] = signature
        print(self._signatures)

    def delete_signature(self, identifier: int) -> None:
        for i, page_signatures in enumerate(self._signatures):
            if identifier in page_signatures:
                del self._signatures[i][identifier]
                return

        raise RuntimeError(f"Signature with identifier {identifier} does not exist.")

    def get_page_signatures(self, page_number: int) -> List[Signature]:
        return list(self._signatures[page_number].values())

    def get_page_signature_ids(self, page_number: int) -> List[int]:
        return list(self._signatures[page_number].keys())

    def clear_page_signatures(self, page_number: int) -> None:
        if page_number >= len(self._pages):
            raise RuntimeError(f"Page {page_number} does not exist.")

        self._signatures[page_number] = {}

    def save(self, path: pl.Path, filters: List[filter.Filter]) -> None:
        if len(self._pages) == 0:
            raise RuntimeError("Can not save empty document.")

        signed_pages = [self.get_page_image(i, signed=True) for i in range(len(self._pages))]

        scanned_pages = []
        for i, page in enumerate(signed_pages):
            for filter_ in filters:
                page = filter_.apply(page)
            scanned_pages.append(page)

        scanned_pages[0].save(path, "PDF", resolution=100.0, save_all=True, append_images=scanned_pages[1:])

    def get_page_image(self, page_number: int, signed: bool) -> Image.Image:
        if page_number >= len(self._pages):
            raise RuntimeError(f"Page {page_number} does not exist.")

        image = self._pages[page_number].copy()
        if signed:
            for signature in self.get_page_signatures(page_number):
                image = signature.draw(image, remove_background=self._remove_signature_background)

        return image

    def set_remove_signature_background(self, value: bool) -> None:
        self._remove_signature_background = value

    @property
    def num_pages(self) -> int:
        return len(self._pages)

    @property
    def loaded(self) -> bool:
        return len(self._pages) > 0
