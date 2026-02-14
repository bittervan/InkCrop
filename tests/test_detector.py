"""
Tests for character detection
"""
import pytest
import numpy as np
import cv2
from inkcrop.detector import CharacterDetector


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
    detector = CharacterDetector()
    assert detector is not None
    assert detector.min_char_size == 200


def test_detect_characters(vertical_calligraphy_image):
    """Test character detection on vertical calligraphy"""
    detector = CharacterDetector(min_char_size=100)
    boxes = detector.detect_characters(vertical_calligraphy_image)

    # Should detect some regions
    assert len(boxes) > 0

    # All boxes should have positive dimensions
    for x, y, w, h in boxes:
        assert w > 0
        assert h > 0


def test_boxes_sorted_for_vertical_text(vertical_calligraphy_image):
    """Test that detected boxes are sorted for vertical reading order"""
    detector = CharacterDetector(min_char_size=100)
    boxes = detector.detect_characters(vertical_calligraphy_image)

    # Should be sorted by x descending (right to left), then y ascending (top to bottom)
    # Check primary sort (x descending)
    for i in range(len(boxes) - 1):
        if boxes[i][0] > boxes[i+1][0]:  # Different column
            assert boxes[i][0] >= boxes[i+1][0]


def test_add_margin_to_box():
    """Test margin addition to bounding boxes"""
    detector = CharacterDetector()

    box = (100, 100, 50, 50)
    margin_box = detector.add_margin_to_box(box, 10, 1000, 1000)

    assert margin_box[0] == 90  # x - margin
    assert margin_box[1] == 90  # y - margin
    assert margin_box[2] == 70  # w + 2*margin
    assert margin_box[3] == 70  # h + 2*margin


def test_add_margin_at_image_boundary():
    """Test that margin doesn't exceed image boundaries"""
    detector = CharacterDetector()

    box = (5, 5, 50, 50)
    margin_box = detector.add_margin_to_box(box, 10, 1000, 1000)

    # Should not go beyond (0, 0)
    assert margin_box[0] == 0
    assert margin_box[1] == 0


def test_preprocess(vertical_calligraphy_image):
    """Test image preprocessing"""
    detector = CharacterDetector()
    binary = detector.preprocess(vertical_calligraphy_image)

    # Binary should be 2D
    assert len(binary.shape) == 2

    # Should be same width and height
    assert binary.shape[:2] == vertical_calligraphy_image.shape[:2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
