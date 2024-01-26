import dataclasses
import io
from typing import Tuple

from PIL import Image


@dataclasses.dataclass
class PaddedImageInfo:
    left_offset: int
    top_offset: int
    width: int
    height: int
    scale: float


def calculate_padded_image_coordinates(
    image_size: Tuple[int, int],
    target_size: Tuple[int, int],
) -> PaddedImageInfo:
    image_aspect_ratio = image_size[0] / image_size[1]
    target_aspect_ratio = target_size[0] / target_size[1]

    if image_aspect_ratio < target_aspect_ratio:
        scaled_width = int(image_size[0] * target_size[1] / image_size[1])
        left_offset = (target_size[0] - scaled_width) // 2
        return PaddedImageInfo(
            left_offset=left_offset,
            top_offset=0,
            width=scaled_width,
            height=target_size[1],
            scale=image_size[1] / target_size[1],
        )
    else:
        scaled_height = int(image_size[1] * target_size[0] / image_size[0])
        top_offset = (target_size[1] - scaled_height) // 2
        return PaddedImageInfo(
            left_offset=0,
            top_offset=top_offset,
            width=target_size[0],
            height=scaled_height,
            scale=image_size[0] / target_size[0],
        )


def resize_and_pad_image(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    image = image.copy()

    padded_image_coords = calculate_padded_image_coordinates(image.size, target_size)

    target_image = Image.new("RGB", target_size, "gray")
    resized = image.resize((padded_image_coords.width, padded_image_coords.height))
    target_image.paste(resized, (padded_image_coords.left_offset, padded_image_coords.top_offset))

    return target_image


def image_to_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
