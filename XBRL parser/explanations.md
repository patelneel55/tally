# XBRL Parser Documentation

## ixbrl_preprocessor.py

### Purpose
This file contains the `IXBRLPreprocessor` class that loads, processes, and cleans iXBRL (Inline XBRL) HTML files by removing XBRL tags while preserving their inner text content. The result is clean HTML suitable for further processing or analysis.

### Classes and Functions

#### `IXBRLPreprocessor`
A class to preprocess iXBRL HTML files by removing XBRL tags but keeping their content.

**Methods:**
- `__init__(log_level=logging.INFO)`: Initialize the preprocessor with configurable logging level
- `load_file(file_path)`: Load an iXBRL HTML file from the specified path
- `_identify_xbrl_namespaces()`: Identify all XBRL namespaces used in the document (internal method)
- `process()`: Process the loaded file by removing XBRL tags while preserving their content
- `save_to_file(output_path)`: Save the processed HTML to a file
- `get_processed_html()`: Return the processed HTML as a string

### Key Logic Decisions

1. **Namespace detection**: 
   - The class dynamically identifies XBRL namespaces by examining the `xmlns:*` attributes in the HTML tag
   - Common namespaces (ix, xbrli, xbrl) are included by default to ensure coverage of standard tags

2. **Tag selection approach**:
   - Uses two strategies to find all XBRL tags:
     1. CSS selectors to find tags with attributes in XBRL namespaces
     2. Direct tag name matching for tags in XBRL namespaces
   - This comprehensive approach ensures all XBRL content is properly handled

3. **Content preservation**:
   - Rather than simply removing tags, the inner content is extracted and properly preserved
   - Uses BeautifulSoup's parser to ensure proper HTML structure is maintained

4. **Robust error handling**:
   - Defensive programming throughout with try/except blocks
   - Detailed logging at different levels of verbosity
   - Appropriate return values to indicate success/failure

### Best Practices Used

1. **Strong typing**:
   - Type hints for all method parameters and return values
   - Optional types where appropriate

2. **Comprehensive logging**:
   - Different logging levels for different types of information
   - Detailed logs for debugging and error tracing
   - Progress indicators for long-running processes

3. **Clean API design**:
   - Methods return appropriate values (boolean for success/failure, content strings for data)
   - Logical separation of loading, processing and saving functionality

4. **Error resilience**:
   - Validation of inputs and state before operations
   - Proper exception handling with informative error messages

### Alternatives Considered

1. **Regular expressions approach**:
   - Could use regex to find and remove XBRL tags
   - Rejected because HTML parsing is more reliable and safer with BeautifulSoup

2. **LXML-based parsing**:
   - Could use lxml for potentially faster parsing
   - Chose BeautifulSoup for better compatibility and more intuitive API

3. **XPath queries**:
   - Could use XPath to find XBRL elements
   - BeautifulSoup's CSS selectors were chosen for simplicity and readability

## visual_block_extractor.py

### Purpose
This file contains the `VisualBlockExtractor` class that extracts visual content blocks from cleaned iXBRL HTML files (after XBRL tags have been removed). It identifies and extracts block-level elements such as headings, paragraphs, tables, and divs, along with their styling information.

### Classes and Functions

#### `VisualBlockExtractor`
A class to extract structured visual content blocks from cleaned HTML files.

**Methods:**
- `__init__(log_level=logging.INFO)`: Initialize the extractor with configurable logging level
- `load_html(html_content)`: Load HTML content directly as a string
- `load_file(file_path)`: Load HTML from a file path
- `extract_blocks()`: Extract visual blocks from the loaded HTML
- `get_blocks()`: Return the list of extracted block dictionaries

**Helper Methods (Internal):**
- `_extract_text(element)`: Extract and clean visible text from an element
- `_extract_font_size(element)`: Determine font size from style attributes or tag default
- `_is_bold(element)`: Check if an element has bold styling
- `_is_italic(element)`: Check if an element has italic styling
- `_is_underlined(element)`: Check if an element has underline styling
- `_get_block_type(tag_name)`: Map HTML tag name to a block type
- `_is_block_element(element)`: Check if an element is a block-level element
- `_is_text_only_div(element)`: Check if a div contains only text or inline elements

### Key Logic Decisions

1. **Block Type Classification**:
   - Uses predefined mappings (constants) to categorize HTML elements
   - Headings (`h1`-`h6`), paragraphs (`p`), tables (`table`), and other block elements
   - Special handling for divs that contain only text content

2. **Style Detection**:
   - Combines multiple approaches to detect styling:
     - Tag-based detection (e.g., `<b>`, `<i>`, `<u>` tags)
     - CSS style attribute parsing (e.g., `font-weight`, `font-style`, `text-decoration`)
     - Default font sizes based on standard HTML conventions

3. **Text Extraction**:
   - Preserves only the visible text content
   - Normalizes whitespace to create clean text output
   - Skips empty elements (except tables which may have structure without text)

4. **Block Organization**:
   - Attempts to maintain the original document flow by sorting elements
   - Uses line numbering to preserve order for later reconstruction

### Best Practices Used

1. **Strong typing**:
   - Type hints for all method parameters and return values
   - Use of appropriate types for data structures

2. **Comprehensive logging**:
   - Detailed logging at each processing stage
   - Block statistics reported (counts by type)
   - Sample output for manual validation

3. **Error handling**:
   - Defensive programming with input validation
   - Graceful handling of edge cases (empty elements, malformed HTML)

4. **Data structure design**:
   - Clean, consistent dictionary structure for block representation
   - Explicit typing of dictionary fields

### Alternatives Considered

1. **DOM Traversal approach**:
   - Could traverse the DOM tree in order and process each node
   - Current approach uses tag-based selection first, then sorts by position
   - This is more efficient but may not perfectly preserve document order

2. **CSS Class-based extraction**:
   - Could rely on CSS classes for block type detection
   - Tag-based approach is more reliable as CSS classes vary between documents

3. **Parser options**:
   - Could use HTML5lib or lxml parsers
   - html.parser was chosen for wider compatibility and simpler dependencies

### Usage Example

See `test_visual_block_extractor.py` for a demonstration of how to use the `VisualBlockExtractor` class. 

## xbrl_fact_extractor.py

### Purpose
This file contains the `XBRLFactExtractor` class that loads an original iXBRL (inline XBRL) HTML file and extracts all facts embedded within `<ix:nonFraction>` and `<ix:nonNumeric>` tags. These tags contain machine-readable values associated with GAAP/IFRS concepts, offering a structured way to extract financial data.

### Classes and Functions

#### `XBRLFactExtractor`
A class to extract structured XBRL facts from iXBRL HTML files.

**Methods:**
- `__init__(log_level=logging.INFO)`: Initialize the extractor with configurable logging level
- `load_file(file_path)`: Load an iXBRL HTML file from the specified path
- `extract_facts()`: Extract all XBRL facts from the loaded file and return them as a dictionary
- `get_facts_by_name(name)`: Get all facts for a specific concept name

**Helper Methods (Internal):**
- `_process_tag(tag, tag_type)`: Process a single XBRL tag and extract its fact information

### Key Logic Decisions

1. **Fact Extraction Strategy**:
   - Uses a two-tiered approach to find XBRL fact tags:
     1. Regex pattern matching to find tags ending with `nonFraction` or `nonNumeric` (case-insensitive) regardless of namespace
     2. Falls back to direct tag name matching if the regex approach doesn't find any tags
   - Preserves the original tag type ("ix:nonFraction" or "ix:nonNumeric") in the extracted data
   - Works with the original HTML file, not the cleaned version (unlike VisualBlockExtractor)

2. **Data Organization**:
   - Facts are organized by concept name (XBRL taxonomy concept)
   - Each concept can have multiple facts (different time periods, contexts, etc.)
   - Each fact includes its value, context reference, unit reference, and tag type

3. **Attribute Handling**:
   - Handles case variations in attribute names (e.g., 'contextRef', 'contextref')
   - Different attribute requirements for different tag types (unitRef is essential for nonFraction)
   - Gracefully handles missing attributes with appropriate warning logs

4. **Statistical Reporting**:
   - Reports the total number of facts and unique concept names
   - Logs the unique contextRef and unitRef values found
   - Provides a sample of the top 5 concept names and their values for verification

### Best Practices Used

1. **Strong typing**:
   - Type hints for all method parameters and return values
   - Appropriate container types for complex data structures

2. **Comprehensive logging**:
   - Information about the extraction process
   - Warnings about missing or malformed attributes
   - Statistical summary of extraction results

3. **Clean API design**:
   - Separated file loading from extraction logic
   - Utility method to filter facts by name
   - Clear return values and logical organization

4. **Error resilience**:
   - Validation of state before operations
   - Robust exception handling
   - Graceful handling of edge cases

### Alternatives Considered

1. **DOM traversal approach**:
   - Could recursively traverse the DOM and look for XBRL tags
   - Direct tag selection is more efficient for this specific use case

2. **XPath-based extraction**:
   - Could use XPath expressions to find XBRL elements
   - BeautifulSoup's tag selection is more Pythonic and better integrated

3. **Namespace-aware parsing**:
   - Could explicitly handle XML namespaces
   - Simple tag name matching is sufficient and more robust for most iXBRL files

### Usage Example

See `test_xbrl_fact_extractor.py` for a demonstration of how to use the `XBRLFactExtractor` class. 

## markdown_renderer.py

### Purpose
This file contains the `MarkdownRenderer` class that converts visual blocks (from `VisualBlockExtractor`) and optionally XBRL facts (from `XBRLFactExtractor`) into a structured Markdown document. It preserves the original document hierarchy and enriches the content with XBRL semantic metadata when available.

### Classes and Functions

#### `MarkdownRenderer`
A class to convert visual blocks and XBRL facts into a structured Markdown document.

**Methods:**
- `__init__(blocks, facts=None, log_level=logging.INFO)`: Initialize with blocks, optional facts, and logging level
- `render()`: Render blocks into a complete Markdown document and return the resulting string
- `save_to_file(file_path)`: Save the rendered Markdown to a file
- `preview(n=10)`: Preview the first n lines of the rendered Markdown

**Helper Methods (Internal):**
- `_get_heading_level(font_size)`: Determine Markdown heading level based on font size
- `_render_heading(block)`: Render a heading block as Markdown
- `_render_paragraph(block)`: Render a paragraph block as Markdown
- `_render_table(block)`: Render a table block as Markdown
- `_render_other(block)`: Render other block types as Markdown
- `_add_fact_footnotes(text)`: Add footnotes for any XBRL facts found in text

### Key Logic Decisions

1. **Font Size to Heading Mapping**:
   - Uses predefined thresholds to map font sizes to Markdown heading levels
   - Follows a hierarchical approach where larger fonts become higher-level headings
   - Font size ≥ 24 → # (H1), ≥ 22 → ## (H2), ≥ 20 → ### (H3), etc.
   - Falls back to paragraph rendering if no appropriate heading level is found

2. **XBRL Fact Integration**:
   - When facts are provided, scans text for matching concept names
   - Creates footnotes with context and unit information for relevant concepts
   - Uses superscript references ([^1], [^2], etc.) to link text with footnotes
   - Appends all footnotes at the end of the document

3. **Block Rendering Strategy**:
   - Processes blocks in their original document order (using line_number)
   - Applies appropriate styling (bold, italic, underline) to each block
   - Special handling for tables to preserve their structure (as HTML)
   - Adds proper spacing between blocks for readability

4. **Document Structure**:
   - Maintains hierarchical organization through heading levels
   - Preserves logical flow of content from the original document
   - Adds footnotes section at the end for XBRL metadata
   - Creates clean, well-formatted Markdown suitable for LLMs or human readers

### Best Practices Used

1. **Strong typing**:
   - Type hints for all method parameters and return values
   - Appropriate types for complex input structures

2. **Comprehensive logging**:
   - Detailed logging at each processing stage
   - Statistics on rendered blocks by type
   - Sample output for verification

3. **Error handling**:
   - Graceful handling of missing attributes or empty blocks
   - Fallback rendering when specific attributes are not available
   - Safe string operations with None checks

4. **Clean API design**:
   - Three clear output options: string, file, or preview
   - On-demand rendering (only generates Markdown when needed)
   - Optional parameters for flexible usage

### Alternatives Considered

1. **HTML to Markdown conversion**:
   - Could convert HTML blocks directly to Markdown
   - Custom processing gives more control over the output format and structure

2. **Direct table conversion**:
   - Could attempt to convert HTML tables to Markdown tables
   - HTML tables are preserved as-is for better compatibility with complex structures

3. **Natural language XBRL fact detection**:
   - Could use NLP to detect mentions of XBRL concepts even without exact matches
   - Simple string matching is more reliable and less prone to false positives

### Usage Example

```python
# Create a MarkdownRenderer with blocks and facts
renderer = MarkdownRenderer(visual_blocks, xbrl_facts)

# Generate Markdown and save to file
markdown = renderer.render()
renderer.save_to_file("output.md")

# Preview the first 10 lines
preview = renderer.preview(10)
``` 