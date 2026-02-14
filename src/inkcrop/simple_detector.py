"""
Simple detector for Chinese calligraphy
Only does binarization and finds content bounds (top/bottom with ink)
"""
import cv2
import numpy as np
from typing import Tuple


class SimpleDetector:
    """Simple detector that only binarizes and finds content bounds"""

    def __init__(
        self,
        blur_size: int = 5,
        morph_kernel_size: Tuple[int, int] = (3, 3),
    ):
        """
        Initialize the simple detector

        Args:
            blur_size: Gaussian blur kernel size
            morph_kernel_size: Morphological operation kernel size
        """
        self.blur_size = blur_size
        self.morph_kernel_size = morph_kernel_size

    def find_content_bounds(self, image: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Binarize image and find the bounding box of all content (ink)

        Args:
            image: Input image (grayscale or BGR)

        Returns:
            Tuple of (x, y, width, height) representing the content bounding box
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        # Otsu binarization
        _, binary = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            self.morph_kernel_size
        )
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Find all non-zero pixels (ink/content)
        coords = cv2.findNonZero(binary)

        if coords is None:
            # No content found, return full image bounds
            return (0, 0, image.shape[1], image.shape[0])

        # Get bounding box of all non-zero pixels
        x, y, w, h = cv2.boundingRect(coords)

        return (x, y, w, h)

    def crop_to_content(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        Crop image to content bounds

        Args:
            image: Input image

        Returns:
            Tuple of (cropped_image, bounds) where bounds is (x, y, w, h)
        """
        x, y, w, h = self.find_content_bounds(image)

        # Crop to content bounds
        cropped = image[y:y+h, x:x+w].copy()

        return cropped, (x, y, w, h)
