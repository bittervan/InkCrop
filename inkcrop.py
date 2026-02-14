#!/usr/bin/env python3
"""
Simple wrapper script to run inkcrop
"""
import sys
import os

# Add src directory to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
sys.path.insert(0, src_dir)

# Run CLI
if __name__ == '__main__':
    from inkcrop.cli import main
    main()
