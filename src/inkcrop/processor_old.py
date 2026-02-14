"""
Main processor for calligraphy sheet splitting
"""
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np

from .detector import VerticalColumnDetector
from .pdf import PDFGenerator


class CalligraphyProcessor:
    """Process calligraphy images and generate print-ready PDF"""

    def __init__(
        self,
        detector: Optional[VerticalColumnDetector] = None,
        dpi: int = 300,
        min_chars_per_page: int = 2,
        max_chars_per_page: int = 100,
    ):
        """
        Initialize the processor

        Args:
            detector: Vertical column detector instance
            dpi: DPI for output pages
            min_chars_per_page: Minimum characters per page
            max_chars_per_page: Maximum characters per page
        """
        self.detector = detector or VerticalColumnDetector()
        self.pdf_generator = PDFGenerator((210, 297))
        self.verbose = False
        self.min_chars_per_page = min_chars_per_page
        self.max_chars_per_page = max_chars_per_page

    def process(
        self,
        image_path: str,
        output_path: str,
        debug_mode: bool = False,
    ) -> dict:
        """
        Process a calligraphy image and generate PDF

        Args:
            image_path: Path to input image
            output_path: Path to output PDF
            debug_mode: If True, save debug images

        Returns:
            Dictionary with processing statistics
        """
        # Load image
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")

        # Detect character regions
        if self.verbose:
            print("Detecting character regions...")
        char_boxes = self.detector.detect_characters(image)
        if self.verbose:
            print(f"Found {len(char_boxes)} character regions")

        if not char_boxes:
            raise ValueError("No characters detected in image")

        # Group into columns
        if self.verbose:
            print("Grouping into columns...")
        columns = self.detector.group_into_columns(char_boxes)
        if self.verbose:
            print(f"Found {len(columns)} columns")

        # Calculate page boundaries
        if self.verbose:
            print("Calculating page boundaries...")
        a4_ratio = 297 / 210  # A4 height/width ratio
        page_bounds = self.detector.calculate_page_bounds(
            columns,
            a4_ratio=a4_ratio,
            min_chars_per_page=self.min_chars_per_page,
            max_chars_per_page=self.max_chars_per_page
        )
        if self.verbose:
            print(f"Calculated {len(page_bounds)} pages")

        # Save debug visualization if requested
        if debug_mode:
            debug_path = Path(output_path).parent / "debug_detection.png"
            vis = self.detector.visualize_detections(
                image,
                char_boxes,
                columns,
                page_bounds
            )
            cv2.imwrite(str(debug_path), vis)
            if self.verbose:
                print(f"Saved debug image to {debug_path}")

        # Extract pages
        if self.verbose:
            print("Extracting pages...")
        page_images = []
        for i, (x, y, w, h) in enumerate(page_bounds):
            # Extract page region from original image
            page_img = image[y:y + h, x:x + w].copy()
            page_images.append(page_img)

            # Save individual page if debug mode
            if debug_mode:
                page_path = Path(output_path).parent / f"page_{i + 1}.png"
                cv2.imwrite(str(page_path), page_img)

        # Generate PDF
        if self.verbose:
            print("Generating PDF...")
        self.pdf_generator.create_pdf_from_images(page_images, str(output_path))

        return {
            "num_pages": len(page_bounds),
            "num_columns": len(columns),
            "num_characters": len(char_boxes),
            "image_size": image.shape,
        }

    def process_batch(
        self,
        image_paths: List[str],
        output_dir: str,
    ) -> List[dict]:
        """
        Process multiple images

        Args:
            image_paths: List of input image paths
            output_dir: Output directory for PDFs

        Returns:
            List of processing results
        """
        results = []
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for image_path in image_paths:
            image_name = Path(image_path).stem
            pdf_path = output_path / f"{image_name}.pdf"

            try:
                result = self.process(str(image_path), str(pdf_path))
                result["input"] = str(image_path)
                result["output"] = str(pdf_path)
                result["status"] = "success"
                results.append(result)
            except Exception as e:
                results.append({
                    "input": str(image_path),
                    "status": "error",
                    "error": str(e),
                })

        return results
