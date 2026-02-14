"""
PDF generation utilities
"""
from typing import List
import numpy as np
from PIL import Image
from fpdf import FPDF


class PDFGenerator:
    """Generate PDF from page images"""

    def __init__(self, page_size_mm: tuple = (210, 297)):
        """
        Initialize PDF generator

        Args:
            page_size_mm: Page size in millimeters (width, height)
        """
        self.page_size_mm = page_size_mm

    def create_pdf(
        self,
        page_images: List[np.ndarray],
        output_path: str,
        title: str = "书法字帖",
    ) -> None:
        """
        Create PDF from page images

        Args:
            page_images: List of page images (numpy arrays)
            output_path: Output PDF file path
            title: PDF title/subject
        """
        pdf = FPDF(unit="mm", format=self.page_size_mm)

        for i, page_img in enumerate(page_images):
            pdf.add_page()

            # Convert numpy array to PIL Image
            if page_img.dtype != np.uint8:
                page_img = page_img.astype(np.uint8)

            # Handle grayscale images
            if len(page_img.shape) == 2:
                pil_img = Image.fromarray(page_img, mode='L')
            else:
                pil_img = Image.fromarray(page_img, mode='RGB')

            # Calculate dimensions
            page_width_mm, page_height_mm = self.page_size_mm
            img_width_px, img_height_px = pil_img.size

            # Convert to temporary file for FPDF
            temp_path = f"/tmp/temp_page_{i}.png"
            pil_img.save(temp_path, format="PNG", dpi=(300, 300))

            # Place image on full page
            pdf.image(
                temp_path,
                x=0,
                y=0,
                w=page_width_mm,
                h=page_height_mm
            )

        # Save PDF
        pdf.output(output_path)

    def create_pdf_from_images(
        self,
        page_images: List[np.ndarray],
        output_path: str,
        draw_lines: bool = True,
        line_margin_mm: float = 10.0,
    ) -> None:
        """
        Create PDF from page images (each image becomes one PDF page)

        Args:
            page_images: List of page images (numpy arrays)
            output_path: Output PDF file path
            draw_lines: Whether to draw lines at top and bottom of content
            line_margin_mm: Margin in mm from content to lines
        """
        pdf = FPDF(unit="mm", format=self.page_size_mm)

        for i, page_img in enumerate(page_images):
            pdf.add_page()

            # Convert numpy array to PIL Image
            if page_img.dtype != np.uint8:
                page_img = page_img.astype(np.uint8)

            # Handle grayscale images
            if len(page_img.shape) == 2:
                pil_img = Image.fromarray(page_img, mode='L')
            else:
                pil_img = Image.fromarray(page_img, mode='RGB')

            # Get image dimensions
            img_width_mm = pil_img.width / 300 * 25.4  # Convert pixels to mm at 300 DPI
            img_height_mm = pil_img.height / 300 * 25.4

            # Center image on page
            x_offset = (self.page_size_mm[0] - img_width_mm) / 2
            y_offset = (self.page_size_mm[1] - img_height_mm) / 2

            # Draw top line before image
            if draw_lines:
                line_y_top = y_offset - line_margin_mm
                if line_y_top > 0:
                    pdf.line(
                        x_offset,
                        line_y_top,
                        x_offset + img_width_mm,
                        line_y_top
                    )

            # Save to temporary file for FPDF
            temp_path = f"/tmp/temp_page_{i}.png"
            pil_img.save(temp_path, format="PNG", dpi=(300, 300))

            # Place image on page
            pdf.image(
                temp_path,
                x=x_offset,
                y=y_offset,
                w=img_width_mm,
                h=img_height_mm
            )

            # Draw bottom line after image
            if draw_lines:
                line_y_bottom = y_offset + img_height_mm + line_margin_mm
                if line_y_bottom < self.page_size_mm[1]:
                    pdf.line(
                        x_offset,
                        line_y_bottom,
                        x_offset + img_width_mm,
                        line_y_bottom
                    )

        # Save PDF
        pdf.output(output_path)

    def create_pdf_with_metadata(
        self,
        page_images: List[np.ndarray],
        output_path: str,
        metadata: dict = None,
    ) -> None:
        """
        Create PDF with metadata

        Args:
            page_images: List of page images
            output_path: Output PDF file path
            metadata: Optional metadata dictionary
        """
        pdf = FPDF(unit="mm", format=self.page_size_mm)

        if metadata:
            pdf.set_title(metadata.get("title", "书法字帖"))
            pdf.set_author(metadata.get("author", ""))
            pdf.set_subject(metadata.get("subject", "书法练习"))
            pdf.set_creator("inkcrop")

        self.create_pdf(page_images, output_path)
