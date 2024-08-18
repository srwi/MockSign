from typing import Tuple

import pytest
from PIL import Image

from mocksign import utils


@pytest.mark.parametrize(
    "image_size,target_size,expected_padded_image_coords",
    [
        (
            (80, 160),
            (40, 40),
            utils.PaddedImageInfo(left_offset=10, top_offset=0, width=20, height=40, scale=4.0),
        ),
        (
            (160, 80),
            (40, 40),
            utils.PaddedImageInfo(left_offset=0, top_offset=10, width=40, height=20, scale=4.0),
        ),
        (
            (40, 40),
            (80, 160),
            utils.PaddedImageInfo(left_offset=0, top_offset=40, width=80, height=80, scale=0.5),
        ),
    ],
)
def test_calculate_padded_image_coordinates(
    image_size: Tuple[int, int],
    target_size: Tuple[int, int],
    expected_padded_image_coords: utils.PaddedImageInfo,
) -> None:
    padded_image_coords = utils.calculate_padded_image_coordinates(image_size, target_size)
    assert padded_image_coords == expected_padded_image_coords


def test_resize_and_pad_image() -> None:
    image = Image.new("RGB", (270, 440), "red")
    target_image = utils.resize_and_pad_image(image, (500, 600))
    expected_image = Image.new("RGB", (500, 600), "gray")
    expected_image.paste(Image.new("RGB", (368, 600), "red"), (66, 0))
    assert expected_image == target_image
