"""
Markdown cleaner module for post-processing and standardizing markdown output.

This module provides functions to clean and standardize markdown content by:
- Removing trailing whitespace
- Normalizing newlines
- Cleaning up lists, tables, and headings
- Removing repeated boilerplate content
"""

import re
import logging

logger = logging.getLogger(__name__)

def clean_markdown(markdown: str) -> str:
    """
    Clean and standardize markdown content.
    
    Args:
        markdown (str): Raw markdown content to be cleaned
        
    Returns:
        str: Cleaned and standardized markdown
        
    Behavior:
        - Remove trailing whitespace from each line
        - Replace 3+ consecutive newlines with 2 newlines
        - Remove lines that are just -, *, or | with no content
        - Collapse malformed list items into proper bullets
        - Ensure tables don't have trailing pipes (unless valid row)
        - Insert 2 newlines after each heading
        - Remove repeated boilerplate lines
    """
    if not markdown:
        return ""
    
    # Split the markdown into lines
    lines = markdown.split('\n')
    
    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in lines]
    
    # Filter out lines that are just decorative separators with no content
    filtered_lines = []
    for i, line in enumerate(lines):
        # Skip lines that are just decorative (-, *, or | with no other content)
        stripped = line.strip()
        if stripped and (
            # Skip if line is just dashes or asterisks (more than 1 character)
            (stripped == '-' * len(stripped) and len(stripped) > 1) or
            (stripped == '*' * len(stripped) and len(stripped) > 1) or
            # Skip if line is just pipes with no content
            (stripped.count('|') > 0 and 
             all(cell.strip() == '' for cell in stripped.split('|')))
        ):
            logger.debug(f"Removing decorative line: {stripped}")
            continue
        
        filtered_lines.append(line)
    
    # Collapse malformed list items
    cleaned_lines = []
    i = 0
    while i < len(filtered_lines):
        line = filtered_lines[i]
        
        # Check for malformed list items (e.g., "- " followed by content on next line)
        list_marker_match = re.match(r'^[\s]*?([-*+])[\s]*$', line)
        if (i < len(filtered_lines) - 1 and 
            list_marker_match and 
            filtered_lines[i + 1].strip()):
            # Get the actual list marker character
            marker = list_marker_match.group(1)
            cleaned_lines.append(f"{marker} {filtered_lines[i + 1].strip()}")
            i += 2
        else:
            cleaned_lines.append(line)
            i += 1
    
    # Clean up table formatting
    table_cleaned_lines = []
    in_table = False
    table_lines = []
    
    for line in cleaned_lines:
        # Detect start of table
        if '|' in line and not in_table:
            in_table = True
            table_lines = [line]
        # Continue collecting table lines
        elif in_table and '|' in line:
            table_lines.append(line)
        # End of table
        elif in_table:
            # Process the collected table lines
            for i, table_line in enumerate(table_lines):
                # Remove trailing pipe and any whitespace after it
                if table_line.rstrip().endswith('|'):
                    parts = table_line.split('|')
                    # If the last cell after the pipe is empty
                    if parts[-1].strip() == '':
                        # Join all parts except the last empty one
                        table_lines[i] = '|'.join(parts[:-1]).rstrip()
            
            # Add processed table lines and current non-table line
            table_cleaned_lines.extend(table_lines)
            table_cleaned_lines.append(line)
            in_table = False
        else:
            table_cleaned_lines.append(line)
    
    # If still in a table at the end, process and add remaining table lines
    if in_table:
        for i, table_line in enumerate(table_lines):
            if table_line.rstrip().endswith('|'):
                parts = table_line.split('|')
                if parts[-1].strip() == '':
                    table_lines[i] = '|'.join(parts[:-1]).rstrip()
        table_cleaned_lines.extend(table_lines)
    
    # Join lines back into a single string
    result = '\n'.join(table_cleaned_lines)
    
    # Replace 3+ consecutive newlines with 2 newlines
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    # Insert 2 newlines after headings (but only 1 newline after the initial newline)
    result = re.sub(r'(^|\n)(#{1,6}[^#\n]+)(\n)', r'\1\2\n\n', result)
    
    # Remove repeated boilerplate lines (appearing 3 or more times)
    lines = result.split('\n')
    boilerplate_count = {}
    
    for line in lines:
        line_stripped = line.strip()
        # Consider non-empty lines with > 5 characters as potential boilerplate
        if len(line_stripped) > 5:
            if line_stripped in boilerplate_count:
                boilerplate_count[line_stripped] += 1
            else:
                boilerplate_count[line_stripped] = 1
    
    # Find repeated lines that might be boilerplate (appearing 3 or more times)
    boilerplate_patterns = set(line for line, count in boilerplate_count.items() if count >= 3)
    
    # Keep only the first instance of each boilerplate line
    seen_boilerplate = set()
    unique_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped not in boilerplate_patterns or line_stripped not in seen_boilerplate:
            unique_lines.append(line)
            if line_stripped in boilerplate_patterns:
                seen_boilerplate.add(line_stripped)
    
    # Final cleanup of consecutive newlines again (after boilerplate removal)
    result = '\n'.join(unique_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result 