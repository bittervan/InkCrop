#!/usr/bin/env python3
"""
Example usage of inkcrop library
"""
from inkcrop.processor import CalligraphyProcessor
from inkcrop.detector import TextLineDetector
from inkcrop.splitter import PageMargin
import cv2
import numpy as np


def create_sample_calligraphy_image():
    """Create a sample calligraphy-like image for testing"""
    # Create a blank white image
    height = 2000
    width = 1200
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Add multiple text lines
    line_height = 80
    line_spacing = 120
    start_y = 100

    for i in range(15):  # 15 lines of text
        y = start_y + i * line_spacing

        # Add some variation to make it more realistic
        h = line_height + np.random.randint(-10, 10)
        x = 100 + np.random.randint(-20, 20)
        w = 1000 + np.random.randint(-50, 50)

        # Draw rectangle with some noise
        cv2.rectangle(img, (x, y), (x + w, y + h), (30, 30, 30), -1)

        # Add some internal texture
        for _ in range(10):
            tx = x + np.random.randint(0, w)
            ty = y + np.random.randint(0, h)
            tw = np.random.randint(20, 100)
            th = np.random.randint(10, 30)
            cv2.rectangle(img, (tx, ty), (tx + tw, ty + th), (40, 40, 40), -1)

    return img


def main():
    """Main example function"""
    print("Creating sample calligraphy image...")

    # Create sample image
    sample_img = create_sample_calligraphy_image()
    cv2.imwrite("sample_calligraphy.png", sample_img)
    print("Saved sample image to sample_calligraphy.png")

    # Process the image
    print("\nProcessing image...")

    # Create processor with custom settings
    detector = TextLineDetector(
        min_region_size=500,
        morph_kernel_size=(30, 5),
    )

    margin = PageMargin(
        top=80,
        bottom=80,
        left=80,
        right=80,
    )

    processor = CalligraphyProcessor(
        detector=detector,
        dpi=300,
    )
    processor.splitter.margin = margin
    processor.splitter.line_spacing = 40

    # Process with debug mode
    result = processor.process(
        "sample_calligraphy.png",
        "output.pdf",
        debug_mode=True,
    )

    print(f"\n✓ Success!")
    print(f"  Detected: {result['num_lines']} text lines")
    print(f"  Generated: {result['num_pages']} pages")
    print(f"  Output: output.pdf")
    print(f"  Debug files saved to current directory")


if __name__ == "__main__":
    main()
