import abc
from collections.abc import Mapping
from typing import Dict, Iterable, Tuple

from PIL import Image, ImageOps


class Filter(abc.ABC):
    def __init__(self, enabled: bool, strength: float) -> None:
        self._enabled = enabled
        self._strength = strength

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def strength(self) -> float:
        return self._strength

    @strength.setter
    def strength(self, value: bool) -> None:
        self._strength = value

    @abc.abstractmethod
    def _apply(self, image: Image.Image) -> Image.Image:
        ...

    def apply(self, image: Image.Image) -> Image.Image:
        if not self._enabled:
            return image

        image = image.copy()
        return self._apply(image)


class FilterCollection(Mapping):
    def __init__(self) -> None:
        self._filters: Dict[str, Filter] = {}

    def __getitem__(self, key: str) -> Filter:
        return self._filters[key]

    def __len__(self) -> int:
        return len(self._filters)

    def __iter__(self) -> Iterable[Tuple[str, Filter]]:
        return iter(self._filters.items())

    def add(self, name: str, filter_: Filter) -> None:
        self._filters[name] = filter_


class InvertFilter(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageOps.invert(image)


class Scanner:
    def __init__(self) -> None:
        self._filters = FilterCollection()

        # TODO: Consider removing filter names
        self._filters.add("invert", InvertFilter(enabled=True, strength=1.0))

    def apply(self, page: Image.Image) -> Image.Image:
        for _, filter_ in self._filters:
            page = filter_.apply(page)

        return page
