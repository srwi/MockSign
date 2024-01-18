import io
from typing import Tuple

from PIL import Image


def image_to_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def calculate_padded_image_coordinates(
    image_size: Tuple[int, int],
    target_size: Tuple[int, int],
) -> Tuple[int, int, int, int, float]:
    image_aspect_ratio = image_size[0] / image_size[1]
    target_aspect_ratio = target_size[0] / target_size[1]

    if image_aspect_ratio < target_aspect_ratio:
        scaled_width = int(image_size[0] * target_size[1] / image_size[1])
        left_offset = (target_size[0] - scaled_width) // 2
        return left_offset, 0, scaled_width, target_size[1], image_size[1] / target_size[1]
    else:
        scaled_height = int(image_size[1] * target_size[0] / image_size[0])
        top_offset = (target_size[1] - scaled_height) // 2
        return 0, top_offset, target_size[0], scaled_height, image_size[0] / target_size[0]


def resize_and_pad_image(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    image = image.copy()

    left_offset, top_offset, width, height, _ = calculate_padded_image_coordinates(image.size, target_size)

    target_image = Image.new("RGB", target_size, "gray")
    resized = image.resize((width, height))
    target_image.paste(resized, (left_offset, top_offset))

    return target_image
