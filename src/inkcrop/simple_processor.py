"""
Simple processor for Chinese calligraphy
Only crops to content and generates PDF with top/bottom lines
"""
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np

from .simple_detector import SimpleDetector
from .pdf import PDFGenerator


class SimpleProcessor:
    """Simple processor that only crops and adds lines"""

    def __init__(self, dpi: int = 300):
        """
        Initialize the simple processor

        Args:
            dpi: DPI for output PDF
        """
        self.detector = SimpleDetector()
        self.pdf_generator = PDFGenerator((210, 297))
        self.verbose = False

    def process(
        self,
        image_path: str,
        output_path: str,
        debug_mode: bool = False,
    ) -> dict:
        """
        Process a calligraphy image: crop to content and generate PDF

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

        if self.verbose:
            print(f"Loaded image: {image.shape}")

        # Find content bounds and crop
        if self.verbose:
            print("Finding content bounds...")
        cropped_image, crop_bounds = self.detector.crop_to_content(image)

        if self.verbose:
            print(f"Content bounds: {crop_bounds}")
            print(f"Cropped image size: {cropped_image.shape}")

        # Save debug visualization if requested
        if debug_mode:
            debug_path = Path(output_path).parent / f"{Path(output_path).stem}_debug.png"
            vis = image.copy()

            # Draw crop bounds on original image
            x, y, w, h = crop_bounds
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(
                vis,
                f"Cropped: {w}x{h}",
                (x + 5, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            cv2.imwrite(str(debug_path), vis)
            if self.verbose:
                print(f"Saved debug image to {debug_path}")

        # Generate PDF with top and bottom lines
        if self.verbose:
            print("Generating PDF...")
        self.pdf_generator.create_pdf_from_images(
            [cropped_image],
            str(output_path),
            draw_lines=True,
            line_margin_mm=10.0
        )

        return {
            "original_size": image.shape,
            "cropped_size": cropped_image.shape,
            "crop_bounds": crop_bounds,
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

        # Filter to only image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        valid_paths = [p for p in image_paths if Path(p).suffix.lower() in image_extensions]

        for image_path in valid_paths:
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
