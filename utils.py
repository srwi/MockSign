import io
from typing import Tuple

from PIL import Image


def convert_pil_image_to_byte_data(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def resize_and_pad_image(image: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    image = image.copy()

    image_aspect_ratio = image.size[0] / image.size[1]
    target_aspect_ratio = target_size[0] / target_size[1]

    target_image = Image.new("RGB", target_size, "gray")

    if image_aspect_ratio < target_aspect_ratio:
        scaled_width = int(image.size[0] * target_size[1] / image.size[1])
        image = image.resize((scaled_width, target_size[1]))
        left_offset = (target_size[0] - scaled_width) // 2
        target_image.paste(image, (left_offset, 0))
    else:
        scaled_height = int(image.size[1] * target_size[0] / image.size[0])
        image = image.resize((target_size[0], scaled_height))
        top_offset = (target_size[1] - scaled_height) // 2
        target_image.paste(image, (0, top_offset))

    return target_image
