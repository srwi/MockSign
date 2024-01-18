from typing import Optional, Tuple, Union

import utils
from PIL import Image


class Signature:
    def __init__(
        self,
        image: Image.Image,
        location: Tuple[int, int],
        scale: float,
    ) -> None:
        self._image = image
        self._location = location
        self._scale = scale

        self._scaled_image_cache: Optional[Image.Image] = None
        self._scaled_bytes_cache: Optional[bytes] = None

    def get_scaled_signature(self, as_bytes: bool = False) -> Union[bytes, Image.Image]:
        if self._scaled_image_cache is None:
            new_size = int(self._image.size[0] * self._scale), int(self._image.size[1] * self._scale)
            self._scaled_image_cache = self._image.copy().resize(size=new_size)
        if not as_bytes:
            return self._scaled_image_cache.copy()

        if self._scaled_bytes_cache is None:
            self._scaled_bytes_cache = utils.image_to_bytes(self._scaled_image_cache)

        return self._scaled_bytes_cache

    def get_location(self) -> Tuple[int, int]:
        return self._location

    def set_scale(self, value: float) -> None:
        if value != self._scale:
            self._scale = value
            self._scaled_image_cache = None
            self._scaled_bytes_cache = None

    def draw(self, image: Image.Image, remove_background: bool) -> Image.Image:
        image = image.copy()
        image.paste(self.get_scaled_signature(), self._location)
        return image
