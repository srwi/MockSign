import pathlib as pl
from typing import List, Tuple, Optional
import numpy as np
import cv2
import fitz
from PIL import Image


class Scanner:
    def __init__(self):
        self._pages: List[Image] = []
        self._current_page: int = 0
        self._preview_mode: bool = False

    def open_pdf(self, path: pl.Path) -> None:
        self._pages = []
        document = fitz.Document(path)
        for i in range(document.page_count):
            page = document.load_page(i)
            pixmap = page.get_pixmap(dpi=150)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self._pages.append(image)

    def get_page_description(self) -> str:
        if len(self._pages) == 0:
            return ""

        return f"Page {self._current_page} of {len(self._pages)}"

    def save_transformed_pdf(self, path: pl.Path) -> None:
        if len(self._pages) == 0:
            raise RuntimeError("Can not save empty document.")

        self._pages[0].save(path,
                            "PDF",
                            resolution=100.0,
                            save_all=True,
                            append_images=self._pages[1:])

    @staticmethod
    def _resize_and_pad_image(image: Image, target_size) -> Image:
        image = image.copy()

        image_aspect_ratio = image.size[0] / image.size[1]
        target_aspect_ratio = target_size[0] / target_size[1]

        target_image = Image.new("RGB", target_size, "gray")

        if image_aspect_ratio < target_aspect_ratio:
            scaled_width = int(image.size[0] * target_size[1] / image.size[1])
            image = image.resize((scaled_width, target_size[1]))
            left_offset = (target_size[0] - scaled_width) // 2
            target_image.paste(image, (left_offset, 0))
        else:
            scaled_height = int(image.size[1] * target_size[0] / image.size[0])
            image = image.resize((target_size[0], scaled_height))
            top_offset = (target_size[1] - scaled_height) // 2
            target_image.paste(image, (0, top_offset))

        return target_image

    def get_page_image(self, page: int, resize: Optional[Tuple[int, int]] = None) -> Image:
        image = self._pages[page]
        if resize is not None:
            image = self._resize_and_pad_image(image, resize)
        return image
