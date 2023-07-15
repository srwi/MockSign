import utils
import pytest
from PIL import Image


@pytest.mark.parametrize(
    "image_size,target_size,expected",
    [
        (
            (80, 160),
            (40, 40),
            (10, 0, 20, 40)
        ),
        (
            (160, 80),
            (40, 40),
            (0, 10, 40, 20)
        ),
        (
            (40, 40),
            (80, 160),
            (0, 40, 80, 80)
        )
    ]
)
def test_calculate_padded_image_coordinates(image_size, target_size, expected):
    left, top, width, height = utils.calculate_padded_image_coordinates(image_size, target_size)
    expected_left, expected_top, expected_width, expected_height = expected
    assert expected_left == left
    assert expected_top == top
    assert expected_width == width
    assert expected_height == height


@pytest.mark.parametrize(
    "graph_coordinates,graph_size,page_size,expected_page_coordinates",
    [
        (
            (20, 20),
            (40, 40),
            (160, 80),
            (80, 40)
        ),
        (
            (10, 30),
            (40, 40),
            (160, 80),
            (40, 80)
        )
    ]
)
def test_graph_to_page_coordinates(graph_coordinates, graph_size, page_size, expected_page_coordinates):
    x, y = utils.graph_to_page_coordinates(graph_coordinates, graph_size, page_size)
    expected_x, expected_y = expected_page_coordinates
    assert expected_x == x
    assert expected_y == y


@pytest.mark.parametrize(
    "expected_graph_coordinates,graph_size,page_size,page_coordinates",
    [
        (
            (20, 20),
            (40, 40),
            (160, 80),
            (80, 40)
        ),
        (
            (10, 30),
            (40, 40),
            (160, 80),
            (40, 80)
        )
    ]
)
def test_page_to_graph_coordinates(expected_graph_coordinates, graph_size, page_size, page_coordinates):
    x, y = utils.page_to_graph_coordinates(page_coordinates, graph_size, page_size)
    expected_x, expected_y = expected_graph_coordinates
    assert expected_x == x
    assert expected_y == y
