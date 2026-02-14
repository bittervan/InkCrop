#!/usr/bin/env python3
"""
Simple script to show content bounds on image
只显示墨迹边界，不生成PDF
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import cv2
import numpy as np
from inkcrop.simple_detector import SimpleDetector


def main():
    if len(sys.argv) < 2:
        print("Usage: python show_bounds.py <image_path> [output_path]")
        print("Example: python show_bounds.py tests/input.jpg output_bounds.jpg")
        sys.exit(1)

    input_path = sys.argv[1]

    # Default output path
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        input_file = Path(input_path)
        output_path = input_file.parent / f"{input_file.stem}_bounds{input_file.suffix}"

    # Read image
    image = cv2.imread(input_path)
    if image is None:
        print(f"Error: Could not load image: {input_path}")
        sys.exit(1)

    print(f"Loaded image: {image.shape}")

    # Create detector
    detector = SimpleDetector()

    # Find content bounds
    print("Finding content bounds...")
    x, y, w, h = detector.find_content_bounds(image)

    print(f"Content bounds:")
    print(f"  x: {x} (left margin)")
    print(f"  y: {y} (top margin)")
    print(f"  width: {w}")
    print(f"  height: {h}")
    print(f"  right: {x + w}")
    print(f"  bottom: {y + h}")

    # Draw bounds on image
    vis = image.copy()

    # Draw rectangle around content
    cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 3)

    # Draw lines for top and bottom
    cv2.line(vis, (x, y), (x + w, y), (255, 0, 0), 2)  # Top line - blue
    cv2.line(vis, (x, y + h), (x + w, y + h), (255, 0, 0), 2)  # Bottom line - blue

    # Draw lines for left and right
    cv2.line(vis, (x, y), (x, y + h), (0, 0, 255), 2)  # Left line - red
    cv2.line(vis, (x + w, y), (x + w, y + h), (0, 0, 255), 2)  # Right line - red

    # Add text labels
    cv2.putText(vis, f"Top (y={y})", (x + 10, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    cv2.putText(vis, f"Bottom (y={y+h})", (x + 10, y + h + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
    cv2.putText(vis, f"Left (x={x})", (x - 80, y + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.putText(vis, f"Right (x={x+w})", (x + w + 10, y + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # Save visualization
    cv2.imwrite(str(output_path), vis)
    print(f"\n✓ Saved visualization to: {output_path}")
    print(f"  Green rectangle: content boundary")
    print(f"  Blue lines: top and bottom")
    print(f"  Red lines: left and right")


if __name__ == "__main__":
    main()
