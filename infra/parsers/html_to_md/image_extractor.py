import os
import base64
import re
import requests
import logging
from bs4 import BeautifulSoup
from typing import Tuple, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

def extract_and_replace_images(html: str, output_dir: str, prefix: str = "img") -> Tuple[str, List[str]]:
    """
    Extract images from HTML and replace them with markdown image references.
    
    Args:
        html: HTML string containing image tags
        output_dir: Directory to save extracted images
        prefix: Prefix for image filenames
        
    Returns:
        Tuple containing:
        - Modified HTML with image tags replaced by markdown image syntax
        - List of paths to saved image files
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    soup = BeautifulSoup(html, 'html.parser')
    saved_images = []
    image_counter = 0
    
    # Find all image tags
    for img in soup.find_all('img'):
        src = img.get('src')
        alt = img.get('alt', '')
        
        # Skip if src is missing or empty
        if not src:
            continue
        
        image_path = None
        image_counter += 1
        filename = f"{prefix}_{image_counter}.png"
        full_path = os.path.join(output_dir, filename)
        relative_path = f"./images/{filename}"
        
        try:
            # Handle base64 encoded images
            if src.startswith('data:image'):
                # Extract the base64 data
                match = re.match(r'data:image/[^;]+;base64,(.+)', src)
                if match:
                    img_data = base64.b64decode(match.group(1))
                    with open(full_path, 'wb') as f:
                        f.write(img_data)
                    image_path = full_path
            
            # Handle remote URLs
            elif src.startswith(('http://', 'https://')):
                response = requests.get(src, stream=True)
                response.raise_for_status()  # Raise exception for bad requests
                
                with open(full_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                image_path = full_path
            
            # Skip local file paths or other src formats
            else:
                continue
                
            # Add to saved images list
            if image_path:
                saved_images.append(image_path)
                
                # Replace the img tag with markdown syntax inside a paragraph
                markdown_img = soup.new_tag('p')
                markdown_img.string = f"![{alt}]({relative_path})"
                img.replace_with(markdown_img)
                
        except Exception as e:
            # Skip this image if there's any error
            print(f"Error processing image {src}: {str(e)}")
            continue
    
    # Return the modified HTML and list of saved images
    return str(soup), saved_images

def extract_images(html: str, base_url: str) -> List[Dict[str, Any]]:
    """
    Extract images from HTML content without modifying the HTML.
    
    Args:
        html: HTML string containing image tags
        base_url: Base URL for resolving relative image URLs
        
    Returns:
        List of dictionaries containing image information:
        - url: Original image URL
        - data: Binary image data
        - alt: Alt text
        - extension: File extension
    """
    soup = BeautifulSoup(html, 'html.parser')
    images = []
    
    for img in soup.find_all('img'):
        src = img.get('src')
        alt = img.get('alt', '')
        
        # Skip if src is missing or empty
        if not src:
            continue
            
        try:
            img_data = None
            extension = '.png'  # Default extension
            
            # Handle base64 encoded images
            if src.startswith('data:image'):
                # Extract the base64 data and determine image type
                match = re.match(r'data:image/([^;]+);base64,(.+)', src)
                if match:
                    img_type = match.group(1)
                    extension = f".{img_type}"
                    img_data = base64.b64decode(match.group(2))
            
            # Handle remote URLs
            elif src.startswith(('http://', 'https://')):
                url = src
                response = requests.get(url, stream=True)
                response.raise_for_status()
                img_data = response.content
                
                # Try to get extension from URL
                if '.' in url.split('/')[-1]:
                    ext = url.split('/')[-1].split('.')[-1].lower()
                    if ext in ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']:
                        extension = f".{ext}"
            
            # Handle relative URLs by combining with base_url
            elif base_url:
                # Remove leading slash if present to avoid double slashes
                src = src.lstrip('/')
                # Make sure base_url ends with slash
                if not base_url.endswith('/'):
                    base_url += '/'
                
                url = f"{base_url}{src}"
                logger.debug(f"Fetching image from: {url}")
                
                response = requests.get(url, stream=True)
                response.raise_for_status()
                img_data = response.content
                
                # Try to get extension from URL
                if '.' in url.split('/')[-1]:
                    ext = url.split('/')[-1].split('.')[-1].lower()
                    if ext in ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']:
                        extension = f".{ext}"
            
            # Skip if we couldn't get the image data
            if img_data:
                images.append({
                    'url': src,
                    'data': img_data,
                    'alt': alt,
                    'extension': extension
                })
                
        except Exception as e:
            logger.error(f"Error processing image {src}: {str(e)}")
            continue
    
    logger.info(f"Extracted {len(images)} images from HTML")
    return images

def update_image_paths(html: str, images: List[Dict[str, Any]], output_dir: str) -> str:
    """
    Update image paths in HTML to point to local saved images.
    
    Args:
        html: Original HTML content
        images: List of image dictionaries from extract_images
        output_dir: Directory where images are saved
        
    Returns:
        HTML with updated image paths
    """
    soup = BeautifulSoup(html, 'html.parser')
    img_tags = soup.find_all('img')
    
    # Create a mapping of original URLs to local paths
    url_to_path = {}
    for idx, img in enumerate(images):
        if 'local_path' in img:
            url_to_path[img['url']] = img['local_path']
    
    # Update img src attributes
    for img_tag in img_tags:
        src = img_tag.get('src')
        if src in url_to_path:
            img_tag['src'] = url_to_path[src]
            img_tag['data-original-src'] = src  # Keep original for reference
    
    return str(soup) 