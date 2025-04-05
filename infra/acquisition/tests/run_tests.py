"""
Test runner for acquisition module tests.

This script runs the SEC Filing Fetcher test suite with proper asyncio handling.
"""

import asyncio
import logging
import sys
import unittest
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("acquisition_tests.log", mode="w"),
    ],
)
logger = logging.getLogger(__name__)

# Import the test cases
from infra.acquisition.tests.test_sec_fetcher import TestSECFetcher


class AsyncioTestRunner:
    """Custom test runner for handling async tests."""

    @staticmethod
    def run_async_test(test_case, test_func):
        """Run an async test function within an event loop."""
        if asyncio.iscoroutinefunction(test_func):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(test_func(test_case))
            finally:
                loop.close()
        else:
            return test_func(test_case)


def patch_test_case_run(original_run):
    """Patch TestCase.run to handle async test methods."""

    def patched_run(self, result=None):
        if result is None:
            result = self.defaultTestResult()

        result.startTest(self)
        test_method = getattr(self, self._testMethodName)

        try:
            self.setUp()
        except Exception as e:
            result.addError(self, sys.exc_info())
            result.stopTest(self)
            return

        try:
            AsyncioTestRunner.run_async_test(self, test_method)
        except Exception as e:
            result.addFailure(self, sys.exc_info())
        else:
            result.addSuccess(self)

        try:
            self.tearDown()
        except Exception as e:
            result.addError(self, sys.exc_info())
            result.stopTest(self)
            return

        result.stopTest(self)

    return patched_run


def main():
    """Run the acquisition module tests."""
    logger.info("Starting acquisition module tests")

    # Create the test directory if it doesn't exist
    Path("test_cache").mkdir(exist_ok=True)

    # Patch TestCase.run to handle async tests
    original_run = unittest.TestCase.run
    unittest.TestCase.run = patch_test_case_run(original_run)

    try:
        # Create the test suite
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()

        # Add tests to the suite
        suite.addTest(loader.loadTestsFromTestCase(TestSECFetcher))

        # Run the tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        # Return the appropriate exit code
        return 0 if result.wasSuccessful() else 1
    finally:
        # Restore the original run method
        unittest.TestCase.run = original_run


if __name__ == "__main__":
    sys.exit(main())
