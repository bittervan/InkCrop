#!/usr/bin/env python3
"""
Batch process all test images and show bounds
"""
import sys
from pathlib import Path
import glob

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from show_bounds import main as show_bounds_main


def batch_process():
    # Find all jpg files in tests directory
    test_images = glob.glob("tests/*.jpg")
    test_images.sort()

    print(f"Found {len(test_images)} test images\n")

    for i, img_path in enumerate(test_images, 1):
        print(f"\n[{i}/{len(test_images)}] Processing: {img_path}")

        # Generate output path
        input_file = Path(img_path)
        output_path = Path("output") / f"{input_file.stem}_bounds{input_file.suffix}"

        # Call the show_bounds function
        try:
            # Import and process
            import cv2
            import numpy as np
            from inkcrop.simple_detector import SimpleDetector

            image = cv2.imread(img_path)
            if image is None:
                print(f"  ✗ Failed to load")
                continue

            detector = SimpleDetector()
            x, y, w, h = detector.find_content_bounds(image)

            print(f"  ✓ Bounds: x={x}, y={y}, w={w}, h={h}")

            # Draw visualization
            vis = image.copy()
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.line(vis, (x, y), (x + w, y), (255, 0, 0), 2)
            cv2.line(vis, (x, y + h), (x + w, y + h), (255, 0, 0), 2)
            cv2.line(vis, (x, y), (x, y + h), (0, 0, 255), 2)
            cv2.line(vis, (x + w, y), (x + w, y + h), (0, 0, 255), 2)

            # Save
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), vis)

        except Exception as e:
            print(f"  ✗ Error: {e}")

    print(f"\n✓ All done! Check output/ directory")


if __name__ == "__main__":
    batch_process()
