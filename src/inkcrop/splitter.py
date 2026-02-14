"""
Split calligraphy image into A4-sized pages with grid layout
"""
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PageSize:
    """Page size configuration (in pixels at given DPI)"""
    width_mm: float
    height_mm: float
    dpi: int = 300

    @property
    def width_px(self) -> int:
        """Page width in pixels"""
        return int(self.width_mm / 25.4 * self.dpi)

    @property
    def height_px(self) -> int:
        """Page height in pixels"""
        return int(self.height_mm / 25.4 * self.dpi)


@dataclass
class PageMargin:
    """Margin configuration for each page"""
    top: int = 50
    bottom: int = 50
    left: int = 50
    right: int = 50


class GridPageSplitter:
    """Split character regions into A4-sized pages with grid layout"""

    def __init__(
        self,
        page_size: PageSize = PageSize(210, 297, dpi=300),  # A4 at 300 DPI
        margin: PageMargin = PageMargin(50, 50, 50, 50),
        char_margin: int = 30,
        grid_cols: int = 4,  # Number of characters per row
        grid_rows: int = 10,  # Number of characters per column
    ):
        """
        Initialize the page splitter

        Args:
            page_size: Target page size
            margin: Margins around each page
            char_margin: Margin around each character
            grid_cols: Number of columns in grid (for vertical text layout)
            grid_rows: Number of rows in grid (for vertical text layout)
        """
        self.page_size = page_size
        self.margin = margin
        self.char_margin = char_margin
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows

    def calculate_pages(
        self,
        char_boxes: List[Tuple[int, int, int, int]],
        image_width: int,
        image_height: int
    ) -> List[List[Tuple[int, int, int, int]]]:
        """
        Group character boxes into pages

        Args:
            char_boxes: List of character bounding boxes (x, y, w, h)
            image_width: Width of original image
            image_height: Height of original image

        Returns:
            List of pages, where each page is a list of character boxes
        """
        chars_per_page = self.grid_cols * self.grid_rows
        pages = []

        # Split into pages (character boxes are already in reading order)
        for i in range(0, len(char_boxes), chars_per_page):
            page_boxes = char_boxes[i:i + chars_per_page]
            pages.append(page_boxes)

        return pages

    def extract_page(
        self,
        image: np.ndarray,
        char_boxes: List[Tuple[int, int, int, int]],
        page_index: int = 0,
    ) -> np.ndarray:
        """
        Extract a page from the image and arrange characters in grid

        Args:
            image: Source image
            char_boxes: List of character boxes for this page
            page_index: Page number for identification

        Returns:
            Page image with A4 dimensions
        """
        # Create blank page
        page = np.ones(
            (self.page_size.height_px, self.page_size.width_px, 3),
            dtype=np.uint8
        ) * 255

        if not char_boxes:
            return page

        # Calculate grid cell size
        available_width = (
            self.page_size.width_px
            - self.margin.left
            - self.margin.right
        )
        available_height = (
            self.page_size.height_px
            - self.margin.top
            - self.margin.bottom
        )

        cell_width = available_width // self.grid_cols
        cell_height = available_height // self.grid_rows

        # Place each character in grid position
        for idx, box in enumerate(char_boxes):
            if idx >= self.grid_cols * self.grid_rows:
                break

            # Calculate grid position (row-major order for display)
            # Characters come in reading order (right-to-left, top-to-bottom)
            # But we want to display them in a grid
            col = idx % self.grid_cols
            row = idx // self.grid_cols

            # Calculate cell position
            cell_x = self.margin.left + col * cell_width
            cell_y = self.margin.top + row * cell_height

            # Extract character from original image with margin
            x, y, w, h = box
            char_x1 = max(0, x - self.char_margin)
            char_y1 = max(0, y - self.char_margin)
            char_x2 = min(image.shape[1], x + w + self.char_margin)
            char_y2 = min(image.shape[0], y + h + self.char_margin)

            char_img = image[char_y1:char_y2, char_x1:char_x2]

            if char_img.size == 0:
                continue

            # Center character in cell
            char_h, char_w = char_img.shape[:2]

            # Calculate position to center in cell
            x_offset = cell_x + (cell_width - char_w) // 2
            y_offset = cell_y + (cell_height - char_h) // 2

            # Place character on page
            if (
                y_offset + char_h <= self.page_size.height_px
                and x_offset + char_w <= self.page_size.width_px
            ):
                page[
                    y_offset:y_offset + char_h,
                    x_offset:x_offset + char_w
                ] = char_img

        return page
