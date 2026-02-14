"""
Page region detection for Chinese calligraphy sheets
Detects individual page frames (not individual characters)
"""
import cv2
import numpy as np
from typing import List, Tuple


class PageDetector:
    """Detect individual page frames in calligraphy scan images"""

    def __init__(
        self,
        min_page_size: int = 200000,  # 200k pixels = ~447x447 minimum
        max_page_size: int = 5000000,  # 5M pixels = ~2236x2236 maximum
        morph_kernel_size: Tuple[int, int] = (5, 5),
        blur_size: int = 7,
        canny_threshold1: int = 50,
        canny_threshold2: int = 150,
    ):
        """
        Initialize the detector

        Args:
            min_page_size: Minimum size of page region to keep (pixels)
            max_page_size: Maximum size of page region to keep (pixels)
            morph_kernel_size: Size of morphological operation kernel (width, height)
            blur_size: Size of Gaussian blur kernel
            canny_threshold1: Lower threshold for Canny edge detection
            canny_threshold2: Upper threshold for Canny edge detection
        """
        self.min_page_size = min_page_size
        self.max_page_size = max_page_size
        self.morph_kernel_size = morph_kernel_size
        self.blur_size = blur_size
        self.canny_threshold1 = canny_threshold1
        self.canny_threshold2 = canny_threshold2

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image to extract page regions

        Args:
            image: Input image (grayscale or BGR)

        Returns:
            Binary image with page regions highlighted
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        # Use Canny edge detection to find page borders
        edges = cv2.Canny(blurred, self.canny_threshold1, self.canny_threshold2)

        # Dilate edges to connect broken lines
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            self.morph_kernel_size
        )
        edges = cv2.dilate(edges, kernel, iterations=2)

        return edges

    def detect_pages(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect individual page regions in the image

        Args:
            image: Input image (grayscale or BGR)

        Returns:
            List of bounding boxes in format (x, y, width, height)
            Sorted in reading order (typically top to bottom, right to left for vertical text)
        """
        # Preprocess
        edges = self.preprocess(image)

        # Find contours
        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # Get bounding boxes for each page region
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Filter by size
            area = w * h
            if self.min_page_size <= area <= self.max_page_size:
                # Also filter aspect ratio (pages should be roughly rectangular)
                aspect_ratio = max(w, h) / min(w, h)
                if aspect_ratio < 10.0:  # Not too elongated
                    boxes.append((x, y, w, h))

        # Sort for Chinese vertical text reading order:
        # Primary: y coordinate ascending (top to bottom)
        # Secondary: x coordinate descending (right to left)
        boxes.sort(key=lambda b: (b[1], -b[0]))

        return boxes

    def visualize_detections(
        self,
        image: np.ndarray,
        boxes: List[Tuple[int, int, int, int]]
    ) -> np.ndarray:
        """
        Draw detected boxes on image for visualization

        Args:
            image: Original image
            boxes: List of bounding boxes

        Returns:
            Image with boxes drawn
        """
        vis = image.copy()
        for i, (x, y, w, h) in enumerate(boxes):
            # Use different colors to show reading order
            color = (
                min(255, 50 + i * 10),  # R
                max(100, 255 - i * 5),  # G
                50,                      # B
            )
            cv2.rectangle(vis, (x, y), (x + w, y + h), color, 3)
            cv2.putText(
                vis,
                str(i + 1),
                (x + 10, y + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                color,
                2
            )

        return vis
