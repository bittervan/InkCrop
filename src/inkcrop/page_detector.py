"""
Vertical column detection for Chinese calligraphy
Detects character regions and groups them into columns
"""
import cv2
import numpy as np
from typing import List, Tuple
from collections import defaultdict


class VerticalColumnDetector:
    """Detect characters and group them into vertical columns"""

    def __init__(
        self,
        min_char_size: int = 200,
        max_char_size: int = 10000,
        morph_kernel_size: Tuple[int, int] = (3, 3),
        blur_size: int = 5,
        column_merge_threshold: int = 100,  # Maximum horizontal distance to be in same column
    ):
        """
        Initialize the detector

        Args:
            min_char_size: Minimum character region size
            max_char_size: Maximum character region size
            morph_kernel_size: Morphological operation kernel size
            blur_size: Gaussian blur kernel size
            column_merge_threshold: Max horizontal distance for characters in same column
        """
        self.min_char_size = min_char_size
        self.max_char_size = max_char_size
        self.morph_kernel_size = morph_kernel_size
        self.blur_size = blur_size
        self.column_merge_threshold = column_merge_threshold

    def find_content_bounds(self, binary: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Find the bounding box of all non-zero pixels (ink/content) in the binary image.

        Args:
            binary: Binary image where non-zero pixels represent content

        Returns:
            Tuple of (x, y, width, height) representing the bounding box
            If no content is found, returns (0, 0, binary.shape[1], binary.shape[0])
        """
        # Find all non-zero pixels
        coords = cv2.findNonZero(binary)

        if coords is None:
            # No content found, return full image bounds
            return (0, 0, binary.shape[1], binary.shape[0])

        # Get bounding box of all non-zero pixels
        x, y, w, h = cv2.boundingRect(coords)

        return (x, y, w, h)

    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """
        Preprocess image to extract character regions and crop to content bounds.

        Args:
            image: Input image (grayscale or BGR)

        Returns:
            Tuple of (cropped_binary, crop_bounds):
            - cropped_binary: Preprocessed binary image cropped to content bounds
            - crop_bounds: (x, y, w, h) of the crop in original image coordinates
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)
        _, binary = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            self.morph_kernel_size
        )
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # Find content bounds (highest and lowest points with ink)
        x, y, w, h = self.find_content_bounds(binary)

        # Crop to content bounds
        cropped_binary = binary[y:y+h, x:x+w]

        return cropped_binary, (x, y, w, h)

    def detect_characters(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect individual character regions.

        Args:
            image: Input image (grayscale or BGR)

        Returns:
            List of character bounding boxes in original image coordinates
        """
        # Preprocess and get cropped binary image with bounds
        binary, crop_bounds = self.preprocess(image)
        crop_x, crop_y, crop_w, crop_h = crop_bounds

        # Find contours in cropped binary image
        contours, _ = cv2.findContours(
            binary,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # Extract character boxes and convert coordinates back to original image space
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Convert from cropped coordinates to original image coordinates
            orig_x = x + crop_x
            orig_y = y + crop_y

            area = w * h
            if self.min_char_size <= area <= self.max_char_size:
                aspect_ratio = max(w, h) / min(w, h)
                if aspect_ratio < 5.0:
                    boxes.append((orig_x, orig_y, w, h))

        # Sort for vertical text reading order (right to left, top to bottom)
        boxes.sort(key=lambda b: (-b[0], b[1]))
        return boxes

    def group_into_columns(
        self,
        char_boxes: List[Tuple[int, int, int, int]]
    ) -> List[List[Tuple[int, int, int, int]]]:
        """
        Group characters into vertical columns

        Args:
            char_boxes: List of character bounding boxes

        Returns:
            List of columns, where each column is a list of character boxes sorted top to bottom
        """
        if not char_boxes:
            return []

        # Group by x position (columns)
        columns = defaultdict(list)

        # Sort by x position for grouping
        sorted_by_x = sorted(char_boxes, key=lambda b: b[0])

        # Group into columns based on horizontal proximity
        current_col_x = sorted_by_x[0][0]
        current_col = []

        for box in sorted_by_x:
            x, y, w, h = box
            center_x = x + w // 2

            # If horizontal distance is small, add to current column
            if abs(center_x - current_col_x) <= self.column_merge_threshold:
                current_col.append(box)
            else:
                # Save current column and start new one
                if current_col:
                    col_id = int(current_col_x)
                    columns[col_id].extend(current_col)
                current_col = [box]
                current_col_x = center_x

        # Add last column
        if current_col:
            col_id = int(current_col_x)
            columns[col_id].extend(current_col)

        # Sort characters in each column by y position (top to bottom)
        for col_id in columns:
            columns[col_id].sort(key=lambda b: b[1])

        # Sort columns by x position (right to left)
        sorted_columns = [columns[col_id] for col_id in sorted(columns.keys(), reverse=True)]

        return sorted_columns

    def calculate_page_bounds(
        self,
        columns: List[List[Tuple[int, int, int, int]]],
        a4_ratio: float = 297 / 210,  # A4 height/width ratio
        min_chars_per_page: int = 2,
        max_chars_per_page: int = 100,
    ) -> List[Tuple[int, int, int, int]]:
        """
        Calculate page boundaries based on character positions and A4 ratio

        Args:
            columns: List of columns with character boxes
            a4_ratio: Target aspect ratio (height/width)
            min_chars_per_page: Minimum characters per page
            max_chars_per_page: Maximum characters per page

        Returns:
            List of page bounding boxes (x, y, w, h)
        """
        if not columns:
            return []

        # Flatten all character boxes with their column info
        all_chars = []
        for col_idx, col in enumerate(columns):
            for char_idx, char_box in enumerate(col):
                x, y, w, h = char_box
                all_chars.append({
                    'box': char_box,
                    'col': col_idx,
                    'row': char_idx,
                    'center_x': x + w // 2,
                    'center_y': y + h // 2,
                })

        if not all_chars:
            return []

        # Calculate optimal page size based on A4 ratio
        # We want to include as many columns as possible while maintaining A4 ratio

        pages = []
        chars_processed = 0
        total_chars = len(all_chars)

        while chars_processed < total_chars:
            # Find range for next page
            remaining_chars = all_chars[chars_processed:]

            if not remaining_chars:
                break

            # Try different number of columns to find best A4 fit
            best_page = None
            best_score = 0

            # Try from 1 column up to all remaining columns
            max_cols_to_try = min(len(columns), 20)  # Reasonable limit

            for num_cols in range(1, max_cols_to_try + 1):
                # Get characters in these columns
                page_chars = remaining_chars
                # Filter to only characters in the first num_cols columns
                max_col_idx = max(c['col'] for c in page_chars[:min_chars_per_page * num_cols])
                page_chars = [c for c in page_chars if c['col'] <= max_col_idx][:max_chars_per_page * num_cols]

                if len(page_chars) < min_chars_per_page:
                    continue

                # Calculate bounding box
                min_x = min(c['box'][0] for c in page_chars)
                max_x = max(c['box'][0] + c['box'][2] for c in page_chars)
                min_y = min(c['box'][1] for c in page_chars)
                max_y = max(c['box'][1] + c['box'][3] for c in page_chars)

                page_width = max_x - min_x
                page_height = max_y - min_y

                # Calculate ratio score (closer to A4 ratio is better)
                if page_width > 0:
                    ratio = page_height / page_width
                    score = len(page_chars) / (1 + abs(ratio - a4_ratio) * 2)

                    if score > best_score:
                        best_score = score
                        best_page = (min_x, min_y, page_width, page_height, len(page_chars))

            if best_page:
                x, y, w, h, num_chars = best_page
                pages.append((x, y, w, h))
                chars_processed += num_chars
            else:
                break

        return pages

    def visualize_detections(
        self,
        image: np.ndarray,
        char_boxes: List[Tuple[int, int, int, int]],
        columns: List[List[Tuple[int, int, int, int]]] = None,
        page_bounds: List[Tuple[int, int, int, int]] = None,
        crop_bounds: Tuple[int, int, int, int] = None,
    ) -> np.ndarray:
        """
        Draw detected elements on image for visualization.

        Args:
            image: Original image
            char_boxes: List of character bounding boxes
            columns: List of columns (optional)
            page_bounds: List of page bounding boxes (optional)
            crop_bounds: (x, y, w, h) of crop region to visualize (optional)

        Returns:
            Visualization image with all detected elements drawn
        """
        vis = image.copy()

        # Draw crop bounds if provided
        if crop_bounds:
            x, y, w, h = crop_bounds
            cv2.rectangle(vis, (x, y), (x + w, y + h), (255, 255, 0), 2)
            cv2.putText(
                vis,
                "Crop Region",
                (x + 5, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                2
            )

        # Draw character boxes in light colors
        for box in char_boxes:
            x, y, w, h = box
            cv2.rectangle(vis, (x, y), (x + w, y + h), (200, 200, 200), 1)

        # Draw columns
        if columns:
            for i, col in enumerate(columns):
                if len(col) == 0:
                    continue
                # Get column bounds
                min_x = min(b[0] for b in col)
                max_x = max(b[0] + b[2] for b in col)
                min_y = min(b[1] for b in col)
                max_y = max(b[1] + b[3] for b in col)
                cv2.rectangle(vis, (min_x, min_y), (max_x, max_y), (255, 0, 0), 2)

        # Draw page bounds
        if page_bounds:
            for i, (x, y, w, h) in enumerate(page_bounds):
                cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 3)
                cv2.putText(
                    vis,
                    f"Page {i + 1}",
                    (x + 5, y + 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

        return vis
