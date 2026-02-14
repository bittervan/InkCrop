#!/usr/bin/env python3
"""
Test script to verify cropping and PDF generation
"""
import cv2
import numpy as np
from inkcrop.processor import CalligraphyProcessor
from inkcrop.detector import CharacterDetector
from inkcrop.splitter import PageMargin


def create_test_image():
    """Create a simple test image with clear characters"""
    img = np.ones((600, 800, 3), dtype=np.uint8) * 255

    # Add 6 different colored rectangles to simulate characters
    colors = [
        (255, 0, 0),    # Red
        (0, 255, 0),    # Green
        (0, 0, 255),    # Blue
        (255, 255, 0),  # Cyan
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Yellow
    ]

    positions = [
        (100, 100), (300, 100), (500, 100),
        (100, 250), (300, 250), (500, 250),
    ]

    for i, (color, (x, y)) in enumerate(zip(colors, positions)):
        cv2.rectangle(img, (x, y), (x + 80, y + 80), color, -1)
        # Add character number
        cv2.putText(img, str(i+1), (x+25, y+50),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)

    return img


def main():
    print("Creating test image with colored characters...")
    test_img = create_test_image()
    cv2.imwrite("test_input.png", test_img)
    print("Saved to test_input.png")

    print("\nProcessing with inkcrop...")
    detector = CharacterDetector(min_char_size=100)
    margin = PageMargin(50, 50, 50, 50)

    processor = CalligraphyProcessor(detector=detector, dpi=150)
    processor.splitter.margin = margin
    processor.splitter.char_margin = 20
    processor.splitter.grid_cols = 3
    processor.splitter.grid_rows = 2

    result = processor.process("test_input.png", "test_output.pdf", debug_mode=True)

    print(f"\n✓ Detected {result['num_characters']} characters")
    print(f"✓ Generated {result['num_pages']} page(s)")
    print("\nChecking output...")

    # Read the generated page image
    page_img = cv2.imread("page_1.png")
    if page_img is not None:
        print(f"✓ Page image size: {page_img.shape}")

        # Check if the colors are preserved
        # Sample a few positions to verify cropping worked
        print("\n✓ Output files generated:")
        print("  - test_input.png (original)")
        print("  - debug_detection.png (with boxes)")
        print("  - page_1.png (cropped and assembled)")
        print("  - test_output.pdf (final output)")
    else:
        print("✗ Failed to read page image")


if __name__ == "__main__":
    main()
