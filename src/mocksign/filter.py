import abc
import random
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter, ImageOps
from PIL.Image import Resampling


class Filter(abc.ABC):
    def __init__(
        self,
        name: str,
        enabled: bool,
        initial_strength: Optional[float] = None,
        strength_range: Optional[Tuple[float, float]] = None,
    ) -> None:
        self._name = name
        self._enabled = enabled
        self._strength = initial_strength
        self._strength_range = strength_range

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def strength_range(self) -> Optional[Tuple[float, float]]:
        return self._strength_range

    @property
    def strength(self) -> Optional[float]:
        return self._strength

    def set_strength(self, value: float) -> None:
        self._strength = value

    @abc.abstractmethod
    def _apply(self, image: Image.Image) -> Image.Image:
        ...

    def apply(self, image: Image.Image) -> Image.Image:
        if not self._enabled:
            return image

        image = image.copy()
        return self._apply(image)


class Grayscale(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        return image.convert("L")


class AutoContrast(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        if self.strength is None:
            return image

        return ImageOps.autocontrast(image, cutoff=int(self.strength))


class Blur(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        if self.strength is None:
            return image

        return image.filter(ImageFilter.GaussianBlur(self.strength))


class Rotate(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        if self.strength is None:
            return image

        random_strength = random.uniform(-float(self.strength), float(self.strength))
        return image.rotate(angle=random_strength, fillcolor="white", resample=Resampling.BILINEAR)


class Noise(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        if self.strength is None:
            return image

        image_array = np.array(image)
        salt_mask = np.random.random(image_array.shape[:2]) < (self.strength / 1000)
        image_array[salt_mask] = np.random.randint(0, 255)
        return Image.fromarray(image_array)
