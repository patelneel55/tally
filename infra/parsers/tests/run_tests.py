#!/usr/bin/env python
"""
Test Runner for PDF Parser Tests

This script runs all unit tests for the PDF parser implementation.
"""

import os
import sys
import unittest
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Import test modules
from test_pdf_parser import TestPDFParser


def run_tests():
    """
    Run all tests for the parsers package.
    """
    # Create a test suite
    test_suite = unittest.TestSuite()

    # Add all tests from TestPDFParser
    test_suite.addTest(unittest.makeSuite(TestPDFParser))

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Return non-zero exit code if tests failed
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
