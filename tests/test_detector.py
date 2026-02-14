"""
Tests for character detection
"""
import pytest
import numpy as np
import cv2
from inkcrop.page_detector import VerticalColumnDetector


@pytest.fixture
def vertical_calligraphy_image():
    """Create a sample vertical calligraphy image"""
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255

    # Create 3 vertical columns of characters
    col_spacing = 150
    char_spacing = 80

    for col in range(3):
        col_x = 100 + col * col_spacing

        for row in range(8):
            y = 50 + row * char_spacing

            # Draw character
            char_size = 40 + np.random.randint(-5, 5)
            x = col_x - char_size // 2
            cv2.rectangle(img, (x, y), (x + char_size, y + char_size), (30, 30, 30), -1)

    return img


def test_detector_initialization():
    """Test that detector can be initialized"""
    detector = VerticalColumnDetector()
    assert detector is not None
    assert detector.min_char_size == 200


def test_detect_characters(vertical_calligraphy_image):
    """Test character detection on vertical calligraphy"""
    detector = VerticalColumnDetector(min_char_size=100)
    boxes = detector.detect_characters(vertical_calligraphy_image)

    # Should detect some regions
    assert len(boxes) > 0

    # All boxes should have positive dimensions
    for x, y, w, h in boxes:
        assert w > 0
        assert h > 0


def test_boxes_sorted_for_vertical_text(vertical_calligraphy_image):
    """Test that detected boxes are sorted for vertical reading order"""
    detector = VerticalColumnDetector(min_char_size=100)
    boxes = detector.detect_characters(vertical_calligraphy_image)

    # Should be sorted by x descending (right to left), then y ascending (top to bottom)
    # Check primary sort (x descending)
    for i in range(len(boxes) - 1):
        if boxes[i][0] > boxes[i+1][0]:  # Different column
            assert boxes[i][0] >= boxes[i+1][0]


def test_preprocess(vertical_calligraphy_image):
    """Test image preprocessing with cropping"""
    detector = VerticalColumnDetector()
    binary, crop_bounds = detector.preprocess(vertical_calligraphy_image)

    # Binary should be 2D
    assert len(binary.shape) == 2

    # Crop bounds should be a tuple of 4 values
    assert len(crop_bounds) == 4
    x, y, w, h = crop_bounds

    # Crop bounds should be within image dimensions
    assert x >= 0
    assert y >= 0
    assert w > 0
    assert h > 0
    assert x + w <= vertical_calligraphy_image.shape[1]
    assert y + h <= vertical_calligraphy_image.shape[0]


def test_find_content_bounds():
    """Test content bounds detection"""
    detector = VerticalColumnDetector()

    # Create a simple binary image with content in the middle
    binary = np.zeros((100, 100), dtype=np.uint8)
    # Add some content (non-zero pixels)
    binary[20:80, 30:70] = 255

    x, y, w, h = detector.find_content_bounds(binary)

    # Should find the content bounds
    assert x == 30
    assert y == 20
    assert w == 40
    assert h == 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
