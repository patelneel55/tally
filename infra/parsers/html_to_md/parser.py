"""
HTML parser module for HTML to Markdown conversion.
"""
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
import logging


class Node:
    """
    Represents a node in the HTML document tree.
    
    This class is used to create a semantic tree structure of the HTML document
    that can be traversed and converted to Markdown.
    """
    
    def __init__(
        self, 
        tag: str, 
        content: str = "", 
        children: Optional[List["Node"]] = None,
        level: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a Node object.
        
        Args:
            tag: The HTML tag name (e.g., 'h1', 'p', 'div')
            content: The text content of this node
            children: List of child nodes
            level: Nesting level in the document (useful for headers)
            metadata: Additional information about the node (e.g., attributes)
        """
        self.tag = tag
        self.content = content
        self.children = children or []
        self.level = level
        self.metadata = metadata or {}


def clean_html(html: str) -> str:
    """
    Clean HTML by removing script tags, style tags, noscript tags, and comments.
    
    Args:
        html: Raw HTML input
        
    Returns:
        Cleaned HTML string
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script tags
    for script in soup.find_all('script'):
        script.decompose()
    
    # Remove style tags
    for style in soup.find_all('style'):
        style.decompose()
    
    # Remove noscript tags
    for noscript in soup.find_all('noscript'):
        noscript.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    return str(soup)


def _process_inline_formatting(element, parent_is_bold=False, parent_is_italic=False):
    """
    Process inline formatting (bold, italic) recursively within an element.
    
    Args:
        element: BeautifulSoup element to process
        parent_is_bold: Whether the parent element is already bold
        parent_is_italic: Whether the parent element is already italic
        
    Returns:
        List of Node objects representing the text with formatting metadata
    """
    result = []
    
    # Process each element in the contents list
    for child in element.contents:
        # If it's a NavigableString (text node)
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():  # Skip empty text nodes
                node = Node(
                    tag="text",
                    content=text,
                    metadata={}
                )
                
                # Apply formatting based on parent tags
                if parent_is_bold:
                    node.metadata["bold"] = True
                if parent_is_italic:
                    node.metadata["italic"] = True
                    
                result.append(node)
        
        # If it's a Tag (element node)
        elif isinstance(child, Tag):
            # Determine if this tag applies bold or italic formatting
            is_bold = parent_is_bold or child.name in ["b", "strong"]
            is_italic = parent_is_italic or child.name in ["i", "em"]
            
            # Recursively process this element
            child_nodes = _process_inline_formatting(child, is_bold, is_italic)
            result.extend(child_nodes)
    
    return result


def build_semantic_tree(soup: BeautifulSoup) -> Node:
    """
    Build a semantic tree from a BeautifulSoup object.
    
    This function creates a Node tree representing the semantic structure of the HTML document,
    focusing on headings, paragraphs, and tables while ignoring other elements. It also preserves
    inline styling like bold and italic text.
    
    Args:
        soup: BeautifulSoup object representing a parsed HTML document
        
    Returns:
        A root Node containing child nodes for headings and paragraphs
    """
    # Create the root node
    root = Node(tag="document")
    
    # If there's a body tag, use that as the search scope
    if soup.body:
        search_scope = soup.body
    else:
        # If there's no body tag, search the entire document
        search_scope = soup
    
    # Process all elements in the scope
    for element in search_scope.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'table'], recursive=True):
        if element.name.startswith('h') and len(element.name) == 2:
            # Handle headings (h1-h6)
            try:
                level = int(element.name[1])
                # Create the heading node
                heading_node = Node(
                    tag=element.name,
                    level=level
                )
                
                # Process inline formatting in the heading
                heading_node.children = _process_inline_formatting(element)
                
                # Add to root
                root.children.append(heading_node)
            except ValueError:
                # Skip if heading level is not a valid number
                continue
        elif element.name == 'p':
            # Handle paragraphs
            p_node = Node(tag='p')
            
            # Process inline formatting in the paragraph
            p_node.children = _process_inline_formatting(element)
            
            # Add to root
            root.children.append(p_node)
        elif element.name == 'table':
            # Handle tables
            table_node = Node(tag='table')
            
            # Process all rows in the table
            for tr in element.find_all('tr', recursive=True):
                # Create a row node
                tr_node = Node(tag='tr')
                
                # Process all header and data cells in the row
                for cell in tr.find_all(['th', 'td'], recursive=False):
                    # Create a cell node with the appropriate tag
                    cell_node = Node(
                        tag=cell.name,
                        content=cell.get_text().strip()
                    )
                    
                    # Add the cell to the row
                    tr_node.children.append(cell_node)
                
                # Add the row to the table
                table_node.children.append(tr_node)
            
            # Add the table to the root
            root.children.append(table_node)
    
    return root


def render_tree_to_markdown(root: Node) -> str:
    """
    Render a semantic tree as Markdown.
    
    Args:
        root: The root Node of the tree to render
        
    Returns:
        Markdown formatted string
    """
    lines = []
    
    for node in root.children:
        if node.tag.startswith('h'):
            # Handle headings
            level = node.level
            content = _render_inline_formatting(node.children)
            lines.append(f"{'#' * level} {content}")
            # Add a blank line after headings
            lines.append("")
        elif node.tag == 'p':
            # Handle paragraphs
            content = _render_inline_formatting(node.children)
            if content.strip():  # Skip empty paragraphs
                lines.append(content)
                # Add a blank line after paragraphs
                lines.append("")
        elif node.tag == 'table':
            # Handle tables
            table_md = _render_table_to_markdown(node)
            lines.append(table_md)
            # Add a blank line after tables
            lines.append("")
    
    # Join lines and return
    return "\n".join(lines)


def _render_table_to_markdown(table_node: Node) -> str:
    """
    Render a table node as Markdown.
    
    Args:
        table_node: The table Node to render
        
    Returns:
        Markdown formatted string for the table
    """
    logger = logging.getLogger(__name__)
    
    if not table_node.children:
        return ""
    
    rows = []
    header_row = []
    max_columns = 0
    
    # First pass: determine the maximum number of columns and identify header row
    has_header = False
    if table_node.children and table_node.children[0].children:
        first_row = table_node.children[0]
        if any(cell.tag == 'th' for cell in first_row.children):
            has_header = True
    
    # Process rows and find maximum column count
    for tr_node in table_node.children:
        if not tr_node.children:
            continue
        max_columns = max(max_columns, len(tr_node.children))
    
    # Second pass: process and normalize rows
    for i, tr_node in enumerate(table_node.children):
        # Skip if this row doesn't have any cells
        if not tr_node.children:
            continue
        
        row_cells = []
        for cell_node in tr_node.children:
            # Handle line breaks in cells by replacing with <br>
            cell_content = cell_node.content.replace('\n', ' <br> ').replace('|', '\\|')
            row_cells.append(cell_content)
        
        # Check if this row is just noise (only one meaningful cell)
        non_empty_cells = [cell for cell in row_cells if cell.strip()]
        if len(non_empty_cells) <= 1:
            logger.debug(f"Skipping row with only one non-empty cell: {row_cells}")
            continue
            
        # Normalize row to match the maximum number of columns
        while len(row_cells) < max_columns:
            row_cells.append("")
        
        if i == 0 and has_header:
            # This is a header row
            header_row = row_cells
        else:
            # This is a regular row
            rows.append(row_cells)
    
    # If no header was found, assume the first row is the header
    if not has_header and rows:
        header_row = rows.pop(0)
    
    # Check if we have any rows to display
    if not header_row:
        logger.warning("Table has no valid header row or data rows")
        return ""
    
    # Generate the Markdown table
    result = []
    
    # Add the header row
    result.append("| " + " | ".join(header_row) + " |")
    # Add the separator row
    result.append("| " + " | ".join(["---"] * len(header_row)) + " |")
    
    # Add the data rows, truncating if necessary
    max_rows_to_display = 50
    if len(rows) > max_rows_to_display:
        displayed_rows = rows[:max_rows_to_display]
        result.extend([f"| {' | '.join(row)} |" for row in displayed_rows])
        result.append(f"\n[Table truncated for readability: {len(rows) - max_rows_to_display} additional rows not shown]")
        logger.info(f"Truncated table with {len(rows)} rows to {max_rows_to_display} rows")
    else:
        result.extend([f"| {' | '.join(row)} |" for row in rows])
    
    # Log statistics
    logger.info(f"Rendered table with {len(rows)} rows and {len(header_row)} columns")
    
    return "\n".join(result)


def _render_inline_formatting(nodes: List[Node]) -> str:
    """
    Render a list of text nodes with inline formatting applied.
    
    Args:
        nodes: List of Node objects representing text with formatting metadata
        
    Returns:
        Markdown formatted string with inline formatting applied
    """
    result = []
    
    for node in nodes:
        text = node.content
        
        # Apply formatting if present
        if node.metadata.get("bold") and node.metadata.get("italic"):
            # Both bold and italic
            text = f"***{text}***"
        elif node.metadata.get("bold"):
            # Bold only
            text = f"**{text}**"
        elif node.metadata.get("italic"):
            # Italic only
            text = f"*{text}*"
        
        result.append(text)
    
    return "".join(result) 