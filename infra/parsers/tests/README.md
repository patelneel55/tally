# PDF Parser Tests

This directory contains tests for the PDF parser implementation using the unittest framework.

## Running the Tests

You can run the tests in two ways:

### 1. Using the run_tests.py script:

```bash
# Run from the infra/parsers/tests directory
python run_tests.py
```

### 2. Using the unittest module directly:

```bash
# Run from the project root
python -m unittest infra/parsers/tests/test_pdf_parser.py
```

## Test Coverage

These tests cover:

1. PDF parser initialization
2. File metadata extraction
3. PDF to markdown conversion
4. Error handling for non-existent files
5. Exception handling during parsing
6. The full parsing flow

## Test Structure

The tests follow the standard unittest framework structure:
- `setUp` method sets up the test environment
- Individual test methods with assertions
- Mocking of external dependencies

## Sample Data

For integration tests, you'll need a sample PDF file. You can create one in the `test/resources` directory:

```bash
mkdir -p test/resources
# Place a sample PDF file in test/resources/sample.pdf
```

Or you can run just the unit tests which use mocks and don't require a real PDF file.

## Requirements

Make sure you have the following Python packages installed:

- unittest (part of Python standard library)
- pymupdf4llm
- langchain-core 