#!/usr/bin/env python3
"""
Example usage of inkcrop library for vertical calligraphy
"""
from inkcrop.processor import CalligraphyProcessor
from inkcrop.detector import CharacterDetector
from inkcrop.splitter import PageMargin
import cv2
import numpy as np


def create_vertical_calligraphy_image():
    """Create a sample vertical calligraphy-like image for testing"""
    # Create a blank white image
    height = 2000
    width = 1200
    img = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Vertical calligraphy has multiple columns (vertical lines)
    # Each column has characters arranged vertically
    num_columns = 5
    chars_per_column = 12

    col_spacing = width // (num_columns + 1)
    char_spacing = 120

    for col in range(num_columns):
        col_x = col_spacing * (col + 1)

        for row in range(chars_per_column):
            y = 100 + row * char_spacing

            # Add some variation to make it more realistic
            char_size = np.random.randint(50, 70)
            x_offset = np.random.randint(-15, 15)

            # Draw character (dark rectangle with some texture)
            x = col_x + x_offset - char_size // 2

            # Main character body
            cv2.rectangle(img, (x, y), (x + char_size, y + char_size), (30, 30, 30), -1)

            # Add some internal texture
            for _ in range(3):
                tx = x + np.random.randint(5, char_size - 10)
                ty = y + np.random.randint(5, char_size - 10)
                tw = np.random.randint(10, 25)
                th = np.random.randint(10, 25)
                cv2.rectangle(img, (tx, ty), (tx + tw, ty + th), (40, 40, 40), -1)

    return img


def main():
    """Main example function"""
    print("Creating sample vertical calligraphy image...")

    # Create sample image
    sample_img = create_vertical_calligraphy_image()
    cv2.imwrite("sample_vertical.png", sample_img)
    print("Saved sample image to sample_vertical.png")

    # Process the image
    print("\nProcessing image...")

    # Create processor with custom settings for vertical text
    detector = CharacterDetector(
        min_char_size=300,
        max_char_size=8000,
        morph_kernel_size=(3, 3),
    )

    margin = PageMargin(
        top=100,
        bottom=100,
        left=100,
        right=100,
    )

    processor = CalligraphyProcessor(
        detector=detector,
        dpi=300,
    )
    processor.splitter.margin = margin
    processor.splitter.char_margin = 40
    processor.splitter.grid_cols = 4  # 4 characters per row
    processor.splitter.grid_rows = 10  # 10 rows per page

    # Process with debug mode
    result = processor.process(
        "sample_vertical.png",
        "output_vertical.pdf",
        debug_mode=True,
    )

    print(f"\n✓ Success!")
    print(f"  Detected: {result['num_characters']} character regions")
    print(f"  Generated: {result['num_pages']} pages")
    print(f"  Output: output_vertical.pdf")
    print(f"  Debug files saved to current directory")


if __name__ == "__main__":
    main()
