from typing import Optional, Tuple

from PIL import Image

import utils


class Signature:
    def __init__(self,
                 image: Image.Image,
                 page: int,
                 location: Tuple[int, int],
                 scale: float,
                 id: Optional[int] = None) -> None:
        self._image = image
        self._page = page
        self._location = location
        self._scale = scale
        self._id = id

        self._scaled_image_cache: Optional[Image.Image] = None
        self._scaled_bytes_cache: Optional[bytes] = None

    def get_scaled(self, as_bytes: bool = False) -> Image.Image:
        if self._scaled_image_cache is None:
            new_size = int(self._image.size[0] * self._scale), int(self._image.size[1] * self._scale)
            self._scaled_image_cache = self._image.copy().resize(size=new_size)
        if not as_bytes:
            return self._scaled_image_cache.copy()

        if self._scaled_bytes_cache is None:
            self._scaled_bytes_cache = utils.convert_pil_image_to_byte_data(self._scaled_image_cache)

        return self._scaled_bytes_cache

    def set_scale(self, value) -> None:
        if value != self._scale:
            self._scale = value
            self._scaled_image_cache = None
            self._scaled_bytes_cache = None
