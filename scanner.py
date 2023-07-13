import abc
from enum import Enum
from typing import Tuple, Optional, Union, Dict, List
from collections.abc import Mapping
from PIL import Image, ImageOps

import utils
from signature import Signature


class Filter(abc.ABC):
    def __init__(self):
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

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

    def __getitem__(self, key) -> Filter:
        return self._filters[key]

    def __len__(self) -> int:
        return len(self._filters)

    def __iter__(self):
        return iter(self._filters)

    def add(self, name: str, filter_: Filter) -> None:
        self._filters[name] = filter_


class InvertFilter(Filter):
    def _apply(self, image: Image.Image) -> Image.Image:
        return ImageOps.invert(image)


class ScannerMode(Enum):
    EDIT = 1
    PREVIEW = 2


class Scanner:
    def __init__(self):
        self._mode: ScannerMode = ScannerMode.EDIT
        self._filters = FilterCollection()
        self._signatures: List[Signature] = []

        self._filters.add("invert", InvertFilter())

    @property
    def mode(self) -> ScannerMode:
        return self._mode

    @mode.setter
    def mode(self, mode: ScannerMode) -> None:
        self._mode = mode

    @property
    def filters(self) -> FilterCollection:
        return self._filters

    def apply(self, page: Image.Image, resize: Optional[Tuple[int, int]] = None, as_bytes: bool = False) -> Union[Image.Image, bytes]:
        if self._mode == ScannerMode.PREVIEW:
            for filter_ in self._filters:
                page = filter_.apply(page)

        if resize is not None:
            page = utils.resize_and_pad_image(page, resize)

        if as_bytes:
            page = utils.convert_pil_image_to_byte_data(page)

        return page

    def place_signature(self, signature: Signature) -> None:
        self._signatures.append(signature)
