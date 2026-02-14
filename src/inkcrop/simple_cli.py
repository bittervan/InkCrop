"""
Simple command-line interface for inkcrop
Only crops to content and adds top/bottom lines
"""
import argparse
from pathlib import Path

from .simple_processor import SimpleProcessor


def main():
    parser = argparse.ArgumentParser(
        description="Crop Chinese calligraphy sheets and add top/bottom lines to PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single image
  inkcrop-simple input.jpg output.pdf

  # Show detailed processing information
  inkcrop-simple input.jpg output.pdf -v

  # Save debug images
  inkcrop-simple input.jpg output.pdf --debug

  # Batch process multiple images
  inkcrop-simple *.jpg -o output_dir/

  # Custom DPI
  inkcrop-simple input.jpg output.pdf --dpi 600
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
        help="Save debug images showing crop bounds"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed processing information"
    )

    args = parser.parse_args()

    # Determine if batch processing: batch if multiple inputs OR output is a directory
    is_batch = len(args.inputs) > 1
    if args.output:
        output_path = Path(args.output)
        # If output exists and is a directory, treat as batch
        if output_path.exists() and output_path.is_dir():
            is_batch = True
    else:
        output_path = None

    # Create processor
    processor = SimpleProcessor(dpi=args.dpi)
    processor.verbose = args.verbose

    # Process
    try:
        if is_batch:
            # Batch processing
            output_dir = str(output_path) if output_path else "output"
            results = processor.process_batch(args.inputs, output_dir)

            # Print summary
            if args.verbose:
                print("\n" + "=" * 50)
                print("Batch processing complete!")
                for result in results:
                    if result["status"] == "success":
                        crop = result["crop_bounds"]
                        print(f"  ✓ {Path(result['input']).name}")
                        print(f"      Original: {result['original_size'][1]}x{result['original_size'][0]}")
                        print(f"      Cropped: {crop[2]}x{crop[3]} (offset: {crop[0]}, {crop[1]})")
                    else:
                        print(f"  ✗ {Path(result['input']).name}: {result.get('error', 'Unknown error')}")
            else:
                print(f"✓ Processed {len(results)} image(s)")
        else:
            # Single image
            single_output = str(output_path) if output_path else f"{Path(args.inputs[0]).stem}.pdf"
            result = processor.process(
                args.inputs[0],
                single_output,
                debug_mode=args.debug,
            )
            if args.verbose:
                crop = result["crop_bounds"]
                print(f"\n✓ Generated PDF from {Path(args.inputs[0]).name}")
                print(f"  Original size: {result['original_size'][1]}x{result['original_size'][0]}")
                print(f"  Cropped size: {crop[2]}x{crop[3]}")
                print(f"  Crop offset: ({crop[0]}, {crop[1]})")
                print(f"  Output: {single_output}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
