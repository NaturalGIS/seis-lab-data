#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
Script Name:     mdreader.py
Author:          Massimo Manghi
Date:            2025-09-10
Description:

Usage:

Dependencies:

Notes:

==============================================================================
"""

import argparse
from mdreader import GDALReader
import json


def main():
    parser = argparse.ArgumentParser(
        description="Attempt to extract metadata from GDAL supported data formats."
    )
    parser.add_argument("file_name", help="GDAL supported file path")
    args = parser.parse_args()

    gdal_reader = GDALReader()
    m = gdal_reader.extract_metadata(args.file_name)
    print(json.dumps(m, indent=2))
    print(f"#### {args.file_name} ####")


# Example usage
if __name__ == "__main__":
    main()
