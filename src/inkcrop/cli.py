"""
Command-line interface for inkcrop
"""
import argparse
from pathlib import Path

from .processor import CalligraphyProcessor


def main():
    parser = argparse.ArgumentParser(
        description="Split Chinese calligraphy sheets into print-ready PDF pages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single image
  inkcrop input.jpg output.pdf

  # Show detailed processing information
  inkcrop input.jpg output.pdf -v

  # Save debug images
  inkcrop input.jpg output.pdf --debug

  # Batch process multiple images
  inkcrop *.jpg -o output_dir/

  # Custom DPI (higher resolution)
  inkcrop input.jpg output.pdf --dpi 600
        """
    )

    parser.add_argument(
        "inputs",
        nargs="+",
        help="Input image path(s)"
    )

    parser.add_argument(
        "-o", "--output",
        help="Output PDF path or directory for batch processing"
    )

    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Output DPI (default: 300)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help=argparse.SUPPRESS
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed processing information"
    )

    parser.add_argument(
        "--min-chars-per-page",
        type=int,
        default=2,
        help="Minimum characters per page (default: 2)"
    )

    parser.add_argument(
        "--max-chars-per-page",
        type=int,
        default=100,
        help="Maximum characters per page (default: 100)"
    )

    args = parser.parse_args()

    # Determine if batch processing
    is_batch = len(args.inputs) > 1 or (args.output and Path(args.output).is_dir())

    # Create processor
    from .detector import VerticalColumnDetector

    detector = VerticalColumnDetector()
    processor = CalligraphyProcessor(
        detector=detector,
        dpi=args.dpi,
        min_chars_per_page=args.min_chars_per_page,
        max_chars_per_page=args.max_chars_per_page,
    )

    # Set verbosity
    processor.verbose = args.verbose

    # Process
    try:
        if is_batch:
            # Batch processing
            output_dir = args.output or "output"
            results = processor.process_batch(args.inputs, output_dir)

            # Print summary
            if args.verbose:
                print("\n" + "=" * 50)
                print("Batch processing complete!")
                for result in results:
                    if result["status"] == "success":
                        print(f"  ✓ {Path(result['input']).name} -> {result['num_pages']} pages")
                    else:
                        print(f"  ✗ {Path(result['input']).name}: {result.get('error', 'Unknown error')}")
            else:
                print(f"✓ Processed {len(results)} image(s)")
        else:
            # Single image
            output_path = args.output or f"{Path(args.inputs[0]).stem}.pdf"
            result = processor.process(
                args.inputs[0],
                output_path,
                debug_mode=args.debug,
            )
            if args.verbose:
                print(f"\n✓ Generated {result['num_pages']} pages from {result['num_characters']} characters")
                print(f"  Output: {output_path}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
