#!/usr/bin/env python3
"""Wrapper script to run the GeneralScaler operator."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run
import kopf
from generalscaler.operator import *

if __name__ == "__main__":
    kopf.cli.main()
