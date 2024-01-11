import abc
from typing import Optional, Tuple

from PIL import Image, ImageFilter, ImageOps


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

    def set_enabled(self, value: bool) -> None:
        print(f"Setting {self._name} to {value}")
        self._enabled = value

    @property
    def strength_range(self) -> Optional[Tuple[float, float]]:
        return self._strength_range

    def set_strength(self, value: bool) -> None:
        print(f"Setting {self._name} strength to {value}")
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


class Gamma(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageOps.autocontrast(image, cutoff=0, ignore=None)


class Blur(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        return image.filter(ImageFilter.BLUR)


class Rotate(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        return image.rotate(self._strength)


class Scanner:
    def apply(self, page: Image.Image) -> Image.Image:
        # for _, filter_ in self._filters:
        #     page = filter_.apply(page)

        return page
