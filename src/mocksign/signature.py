from typing import Optional, Tuple

import cv2
import numpy as np
from cv2 import seamlessClone
from PIL import Image


def seamless_clone(image: Image.Image, signature: Image.Image, location: Tuple[int, int]) -> Image.Image:
    x, y = location
    signature_width, signature_height = signature.size
    signature_array = np.array(signature)
    target_image = np.array(image)

    cropped_signature = signature_array[
        : min(signature_height, target_image.shape[0] - y), : min(signature_width, target_image.shape[1] - x)
    ]
    location_center = (x + cropped_signature.shape[1] // 2, y + cropped_signature.shape[0] // 2)
    mask = np.ones_like(cropped_signature) * 255

    cloned_image = seamlessClone(
        src=cropped_signature,
        dst=target_image,
        mask=mask,
        p=location_center,
        flags=cv2.MIXED_CLONE,
    )

    return Image.fromarray(cloned_image)


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

    def get_scaled_signature(self) -> Image.Image:
        if self._scaled_image_cache is None:
            new_size = int(self._image.size[0] * self._scale), int(self._image.size[1] * self._scale)
            self._scaled_image_cache = self._image.copy().resize(size=new_size)

        return self._scaled_image_cache.copy()

    def get_location(self) -> Tuple[int, int]:
        return self._location

    def set_scale(self, value: float) -> None:
        if value != self._scale:
            self._scale = value
            self._scaled_image_cache = None
            self._scaled_bytes_cache = None

    def draw(self, image: Image.Image, remove_background: bool) -> Image.Image:
        image = image.copy()
        flipped_y_location = (self._location[0], image.size[1] - self._location[1])
        if remove_background:
            image = seamless_clone(image, self.get_scaled_signature(), flipped_y_location)
        else:
            image.paste(self.get_scaled_signature(), flipped_y_location)
        return image
