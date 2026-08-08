import os
import re
import uuid
import io
import logging
import requests
import json
import base64
import numpy as np
from datetime import datetime
from PIL import Image
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from unidecode import unidecode
from urllib.parse import urlparse

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google API scopes required for accessing Google Docs
SCOPES = [
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

# Emitted inline (in Doc order) at each image position by _extract_text_with_formatting,
# then swapped for the uploaded WordPress image by _replace_image_placeholders. An HTML
# comment survives the BeautifulSoup round-trip in _modify_html unchanged.
IMAGE_PLACEHOLDER = '<!--IMAGE_PLACEHOLDER-->'

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'env', 'dashboard-gcloud.json')
MEDIA_DIR = os.path.join(BASE_DIR, 'data', 'output', 'media')
JOBSGO_DIR = os.path.join(BASE_DIR, 'data', 'input', 'jobsgo')

# Ensure media directory exists
os.makedirs(MEDIA_DIR, exist_ok=True)

class GoogleDocsToWordPress:
    """Tool to publish content from Google Docs to WordPress using REST API."""
    
    def __init__(self, wp_url, username, password):
        """Initialize the Google Docs to WordPress tool."""
        self.credentials = None
        self.docs_service = None
        self.drive_service = None
        
        # WordPress API settings
        self.wp_api_url = f"{wp_url}/wp-json/wp/v2"
        self.username = username
        self.password = password
        self.auth_header = self._get_auth_header()
        
        # Initialize Google API services
        self._init_google_api()
    
    def _init_google_api(self):
        """Initialize Google API services."""
        try:
            self.credentials = Credentials.from_service_account_file(
                CREDENTIALS_PATH, scopes=SCOPES
            )
            self.docs_service = build('docs', 'v1', credentials=self.credentials)
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            logger.info("Google API services initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google API services: {e}")
            raise
    
    def _get_auth_header(self):
        """Get the authorization header for WordPress API."""
        token = base64.b64encode(f"{self.username}:{self.password}".encode())
        return {"Authorization": f"Basic {token.decode('utf-8')}"}
    
    def get_doc_content(self, doc_id):
        """Retrieve the content and structure of a Google Doc."""
        try:
            document = self.docs_service.documents().get(documentId=doc_id).execute()
            logger.info(f"Retrieved document: {document.get('title')}")
            return document
        except Exception as e:
            logger.error(f"Failed to retrieve document {doc_id}: {e}")
            raise
    
    def _extract_text_with_formatting(self, doc):
        """Extract text with formatting from Google Docs content with specific SEO fields."""
        content = doc.get('body', {}).get('content', [])
        html_parts = []
        
        self.image_positions = {}
        current_element_index = 0
        current_text_index = 0
        
        yoast_seo_title = None
        yoast_seo_description = None
        post_title = None

        h1_count = 0
        p_count = 0
        
        # Flag to track if we're in a bullet list
        in_bullet_list = False
        bullet_list_items = []
    
        for element in content:
            if 'paragraph' in element:
                para = element['paragraph']
                para_style = para.get('paragraphStyle', {})
                named_style = para_style.get('namedStyleType', 'NORMAL_TEXT')
                
                # Check if the paragraph has bullet points
                bullet = para.get('bullet')
                is_bullet_point = bullet is not None
                
                heading_tag = None
                if named_style == 'HEADING_1':
                    heading_tag = 'h1'
                    h1_count += 1
                elif named_style == 'HEADING_2':
                    heading_tag = 'h2'
                elif named_style == 'HEADING_3':
                    heading_tag = 'h3'
                elif named_style == 'HEADING_4':
                    heading_tag = 'h4'
                
                text_parts = []
                paragraph_text_index = 0
                para_image_ids = []  # inline images in this paragraph, in Doc order

                for text_element in para.get('elements', []):
                    if 'textRun' in text_element:
                        text_content = text_element.get('textRun', {}).get('content', '')
                        if not text_content or text_content == '\n':
                            continue
                        
                        text_style = text_element.get('textRun', {}).get('textStyle', {})
                        is_bold = text_style.get('bold', False)
                        is_italic = text_style.get('italic', False)
                        link_url = text_style.get('link', {}).get('url', None)
                        
                        formatted_text = text_content
                        if is_bold and formatted_text != '':
                            formatted_text = f"<strong>{formatted_text}</strong>"
                        if is_italic and formatted_text != '':
                            formatted_text = f"<i>{formatted_text}</i>"
                        if link_url and formatted_text != '':
                            formatted_text = f' <a href="{link_url}">{formatted_text}</a>'
                        
                        text_parts.append(formatted_text)
                        paragraph_text_index += len(text_content)
                        
                    elif 'inlineObjectElement' in text_element:
                        image_id = text_element['inlineObjectElement']['inlineObjectId']
                        para_image_ids.append(image_id)
                        self.image_positions[image_id] = {
                            'element_index': current_element_index,
                            'text_position': current_text_index + paragraph_text_index,
                            'paragraph_position': paragraph_text_index,
                            'is_standalone': len(text_parts) == 0 and paragraph_text_index == 0
                        }
                
                if text_parts:
                    paragraph_text = ''.join(text_parts)
                    current_text_index += len(paragraph_text)

                    # Process based on element type and position
                    if heading_tag == 'h1':
                        if h1_count == 1:
                            # First h1 is Yoast SEO title
                            yoast_seo_title = BeautifulSoup(paragraph_text, 'html.parser').get_text()
                        elif h1_count == 2:
                            # Second h1 is post title
                            post_title = BeautifulSoup(paragraph_text, 'html.parser').get_text()

                    # Handle bullet points specifically
                    if is_bullet_point:
                        # If this is the first bullet point, start a new list
                        if not in_bullet_list:
                            in_bullet_list = True
                            bullet_list_items = []

                        # Add the bullet item
                        bullet_list_items.append(f"<li>{paragraph_text}</li>")
                    else:
                        # If we were in a bullet list but now found a non-bullet paragraph,
                        # finalize the list and add it to appropriate content
                        if in_bullet_list:
                            bullet_html = f"<ul>\n{''.join(bullet_list_items)}\n</ul>"
                            html_parts.append(bullet_html)
                            in_bullet_list = False
                            bullet_list_items = []

                        # Generate HTML for non-bullet content
                        html_element = ""
                        if heading_tag:
                            html_element = f"<{heading_tag}>{paragraph_text}</{heading_tag}>"
                        else:
                            p_count += 1
                            if p_count == 1:
                                # First p is Yoast SEO description
                                clean_text = BeautifulSoup(paragraph_text, 'html.parser').get_text()
                                yoast_seo_description = clean_text[:157] + "..." if len(clean_text) > 160 else clean_text
                            html_element = f"<p>{paragraph_text}</p>"

                        # Skip h1 tags and yoast_seo_description in post_content
                        if not (heading_tag == 'h1' or (p_count == 1 and not heading_tag)):
                            html_parts.append(html_element)

                    # Image(s) embedded inside this text paragraph — place them right after it.
                    for _ in para_image_ids:
                        html_parts.append(IMAGE_PLACEHOLDER)

                    current_element_index += 1

                elif para_image_ids:
                    # Standalone image paragraph(s): emit a placeholder for each, in order.
                    for _ in para_image_ids:
                        html_parts.append(IMAGE_PLACEHOLDER)
                    current_element_index += 1

            elif 'table' in element:
                # If we were in a bullet list, finalize it before processing the table
                if in_bullet_list:
                    bullet_html = f"<ul>\n{''.join(bullet_list_items)}\n</ul>"
                    html_parts.append(bullet_html)
                    in_bullet_list = False
                    bullet_list_items = []

                table_html = self._process_table(element['table'])
                html_parts.append(table_html)
                current_element_index += 1
                current_text_index += len(table_html)

            # Process lists (preserve ul/li)
            elif 'list' in element:
                # If we were in a bullet list, finalize it before processing another list
                if in_bullet_list:
                    bullet_html = f"<ul>\n{''.join(bullet_list_items)}\n</ul>"
                    html_parts.append(bullet_html)
                    in_bullet_list = False
                    bullet_list_items = []

                list_html = self._process_list(element['list'])
                html_parts.append(list_html)
                current_element_index += 1
                current_text_index += len(list_html)

        # Finalize any remaining bullet list at the end of the document
        if in_bullet_list:
            bullet_html = f"<ul>\n{''.join(bullet_list_items)}\n</ul>"
            html_parts.append(bullet_html)

        # Fallback for title if no h1s were found
        if post_title is None:
            post_title = doc.get('title', 'Untitled Document')

        # Combine all the extracted information
        post_content = '\n'.join(html_parts)

        return {
            'yoast_seo_title': yoast_seo_title,
            'yoast_seo_description': yoast_seo_description,
            'post_title': post_title,
            'post_content': post_content,
        }
        
    def _process_list(self, list_element):
        """Process list elements to preserve ul/li structure."""
        list_items = list_element.get('listItems', [])
        list_type = list_element.get('listType', 'BULLET')
        
        tag = 'ul' if list_type == 'BULLET' else 'ol'
        list_html_parts = [f'<{tag}>']
        
        for item in list_items:
            content = item.get('content', '')
            if content:
                formatted_content = self._format_text(content)
                list_html_parts.append(f'<li>{formatted_content}</li>')
        
        list_html_parts.append(f'</{tag}>')
        return '\n'.join(list_html_parts)
    
    def _format_text(self, text_elements):
        """Helper method to format text with styling."""
        formatted_parts = []
        
        for element in text_elements:
            if 'textRun' in element:
                text = element.get('textRun', {}).get('content', '')
                style = element.get('textRun', {}).get('textStyle', {})
                
                if style.get('bold'):
                    text = f'<strong>{text}</strong>'
                if style.get('italic'):
                    text = f'<i>{text}</i>'
                if style.get('link', {}).get('url'):
                    url = style.get('link', {}).get('url')
                    text = f'<a href="{url}">{text}</a>'
                    
                formatted_parts.append(text)
        
        return ''.join(formatted_parts)
    
    def _build_wp_image_html(self, image, index, main_keyword):
        """Download, optimize and upload one Google Docs image to WordPress, returning
        (gutenberg_image_html, media_id). Returns ('', None) on any failure so the caller
        can simply skip it. The temporary local file is always cleaned up."""
        alt_text = image.get('alt', '')
        if not alt_text:
            title = image.get('title', '')
            alt_text = f"{main_keyword} - {title}" if title else f"{main_keyword} - image {index + 1}"
        alt_text = alt_text.replace('"', '&quot;').strip()

        try:
            local_path, filename = self._download_and_optimize_image(image['url'], alt_text)
            if not local_path:
                logger.error(f"Failed to download or optimize image {image['url']}")
                return '', None

            media_data = self._upload_image_to_wordpress(local_path, filename, alt_text)
            try:
                os.remove(local_path)
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {local_path}: {e}")

            if not media_data:
                logger.error(f"Failed to upload image {image['url']} to WordPress")
                return '', None

            img_html = f'<!-- wp:image {{"id":{media_data["id"]},"sizeSlug":"large","linkDestination":"none"}} -->\n'
            img_html += f'<figure class="wp-block-image size-large">'
            img_html += f'<img src="{media_data["source_url"]}" alt="{alt_text}" '
            img_html += f'class="wp-image-{media_data["id"]}"/>'
            img_html += f'</figure>\n<!-- /wp:image -->'
            return img_html, media_data["id"]
        except Exception as e:
            logger.error(f"Error processing image {index}: {e}")
            return '', None

    def _replace_image_placeholders(self, html_content, images, main_keyword):
        """Replace each inline placeholder (emitted in Doc order by
        _extract_text_with_formatting) with its corresponding uploaded WordPress image, so
        images land at the exact position they occupy in the Doc. Images with no matching
        placeholder are appended at the end; the first successfully uploaded image becomes
        the featured image.

        Returns (HTML content with WordPress image blocks, featured image ID or None).
        """
        featured_image_id = None
        image_index = 0

        # Split on the placeholder — the first chunk has no image before it, and each
        # subsequent chunk is preceded by the next image (in Doc order).
        parts = html_content.split(IMAGE_PLACEHOLDER)
        result_elements = [parts[0]]

        for segment in parts[1:]:
            if image_index < len(images):
                img_html, media_id = self._build_wp_image_html(
                    images[image_index], image_index, main_keyword
                )
                if img_html:
                    result_elements.append(img_html)
                    if featured_image_id is None:
                        featured_image_id = media_id
                        logger.info(f"Set image {media_id} as featured image")
                image_index += 1
            result_elements.append(segment)

        # Any images beyond the number of placeholders — append at the end.
        for i in range(image_index, len(images)):
            img_html, media_id = self._build_wp_image_html(images[i], i, main_keyword)
            if img_html:
                result_elements.append(img_html)
                if featured_image_id is None:
                    featured_image_id = media_id

        return '\n'.join(result_elements), featured_image_id
    
    def _process_table(self, table):
        html = ['<figure class="wp-block-table"><table>']
        align_map = {"START": "left", "CENTER": "center", "END": "right"}

        for i, row in enumerate(table.get('tableRows', [])):
            html.append('<tr>')
            for cell in row.get('tableCells', []):
                cell_content = []
                for content in cell.get('content', []):
                    if 'paragraph' in content:
                        para_text = []
                        is_list = content['paragraph'].get('bullet', False)
                        alignment = align_map.get(content['paragraph'].get('paragraphStyle', {}).get('alignment', "START"), "left")
                        for element in content['paragraph'].get('elements', []):
                            if 'textRun' in element:
                                text_content = element['textRun'].get('content', '')
                                text_style = element['textRun'].get('textStyle', {})
                                if text_style.get('bold', False):
                                    text_content = f"<strong>{text_content}</strong>"
                                if text_style.get('italic', False):
                                    text_content = f"<em>{text_content}</em>"
                                if 'link' in text_style:
                                    text_content = f'<a href="{text_style["link"].get("url", "")}">{text_content}</a>'
                                para_text.append(text_content)
                        paragraph_html = ''.join(para_text)
                        item_html = f'<li style="text-align: {alignment}">{paragraph_html}</li>' if is_list else f'<div style="text-align: {alignment}">{paragraph_html}</div>'
                        cell_content.append(item_html)
                if any('</li>' in item for item in cell_content):
                    cell_content = ['<ul>'] + cell_content + ['</ul>']
                tag = 'th' if i == 0 else 'td'
                html.append(f'<{tag}>{"".join(cell_content)}</{tag}>')
            html.append('</tr>')

        html.append('</table></figure>')
        return '\n'.join(html)


    
    def _find_images(self, doc_id):
        """
        Find all images in a Google Doc and return them in order from top to bottom.
        
        Args:
            doc_id (str): The ID of the Google Document
            
        Returns:
            list: A list of dictionaries containing image information, ordered by position
        """
        document = self.docs_service.documents().get(documentId=doc_id).execute()
        inline_objects = document.get('inlineObjects', {})
        
        # Create a list to store images with their positions
        positioned_images = []
        
        # Get the document content
        content = document.get('body', {}).get('content', [])
        
        # Iterate through the document content to find inline object IDs and their positions
        for element in content:
            if 'paragraph' in element:
                paragraph_elements = element.get('paragraph', {}).get('elements', [])
                for para_element in paragraph_elements:
                    if 'inlineObjectElement' in para_element:
                        obj_id = para_element.get('inlineObjectElement', {}).get('inlineObjectId')
                        if obj_id and obj_id in inline_objects:
                            # Get position information - could be index in document or actual position values
                            # Here using the index in our processing as an approximation
                            position = len(positioned_images)
                            
                            # Get the object data
                            obj_data = inline_objects[obj_id]
                            embed_obj = obj_data.get('inlineObjectProperties', {}).get('embeddedObject', {})
                            
                            # Check if it's an image
                            if 'imageProperties' in embed_obj:
                                image_url = embed_obj.get('imageProperties', {}).get('contentUri')
                                if image_url:
                                    positioned_images.append({
                                        'id': obj_id,
                                        'url': image_url,
                                        'title': embed_obj.get('title', ''),
                                        'alt': embed_obj.get('description', ''),
                                        'position': position
                                    })
        
        # Sort images by their position
        positioned_images.sort(key=lambda x: x['position'])
        
        # Remove the position key from the final output if not needed
        images = [{k: v for k, v in img.items() if k != 'position'} for img in positioned_images]
        
        logger.info(f"Found {len(images)} images in document {doc_id}")
        return images
    
    def _download_and_optimize_image(self, image_url, alt_text):
        """
        Download, optimize, and add the most suitable watermark to an image from Google Docs.
        
        Args:
            image_url (str): URL of the image to download
            alt_text (str): Alternative text for the image (used in filename generation)
        
        Returns:
            tuple: (file_path, filename) or (None, None) if download/optimization fails
        """
        try:
            # Download image with streaming and timeout
            response = requests.get(
                image_url, 
                stream=True, 
                timeout=(10, 30)  # (connect timeout, read timeout)
            )
            response.raise_for_status()
            
            # Sanitize filename from alt text
            sanitized_keyword = re.sub(
                r'[^a-zA-Z0-9]+', 
                '-', 
                unidecode(alt_text).lower()
            ).strip('-')
            filename = f"{sanitized_keyword}.jpg"
            file_path = os.path.join(MEDIA_DIR, filename)
            
            # Watermark paths
            watermark_white_path = os.path.join(JOBSGO_DIR, 'logo_white.png')
            watermark_blue_path = os.path.join(JOBSGO_DIR, 'logo_blue.png')
            
            # Open and convert image
            with Image.open(io.BytesIO(response.content)) as original_img:
                # Ensure RGB mode
                img = original_img.convert("RGB")
                
                # Resize large images if needed
                max_size = (2000, 2000)  # Adjust as per your requirements
                img.thumbnail(max_size, Image.LANCZOS)
                
                # Add watermark if watermark images exist
                # if (
                #     os.path.exists(watermark_white_path)
                #     and os.path.exists(watermark_blue_path)
                # ):
                #     img = self._add_watermark(
                #         img,
                #         watermark_white_path,
                #         watermark_blue_path
                #     )
                #     logger.info(f"Watermark added for image: {filename}")

                
                # Save optimized image
                img.save(
                    file_path, 
                    'JPEG', 
                    optimize=True, 
                    quality=85
                )
            
            logger.info(f"Downloaded and optimized image: {filename}")
            return file_path, filename
        
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Network error downloading image: {req_err}")
        except IOError as io_err:
            logger.error(f"Image processing error: {io_err}")
        except Exception as e:
            logger.error(f"Unexpected error in image download/optimization: {e}")
        
        return None, None
    
    def _add_watermark(self, img, watermark_white_path, watermark_blue_path):
        """
        Add watermark to the image in the least detailed corner.
        
        Args:
            img (PIL.Image): Input image
            watermark_white_path (str): Path to white watermark
            watermark_blue_path (str): Path to blue watermark
        
        Returns:
            PIL.Image: Image with watermark added
        """
        # Open and convert watermark images
        watermark_white = Image.open(watermark_white_path).convert("RGBA")
        watermark_blue = Image.open(watermark_blue_path).convert("RGBA")
        
        # Watermark size calculation
        wm_ratio = 0.25
        wm_width = int(img.width * wm_ratio)
        wm_height = int(watermark_white.height * (wm_width / watermark_white.width))
        
        # Resize watermarks
        watermark_white = watermark_white.resize((wm_width, wm_height), Image.LANCZOS)
        watermark_blue = watermark_blue.resize((wm_width, wm_height), Image.LANCZOS)
        
        # Define corner positions with padding
        padding = min(20, int(min(img.width, img.height) * 0.05))
        corners = [
            (padding, padding),  # top-left
            (img.width - wm_width - padding, padding),  # top-right
            (padding, img.height - wm_height - padding),  # bottom-left
            (img.width - wm_width - padding, img.height - wm_height - padding)  # bottom-right
        ]
        
        # Find the least detailed corner (lowest variance)
        best_corner_index = 0
        min_variance = float('inf')
        
        for i, (x, y) in enumerate(corners):
            # Crop the area where watermark will be placed
            area = img.crop((x, y, x + wm_width, y + wm_height))
            area_array = np.array(area.convert('L'))
            
            # Calculate variance as a measure of detail/complexity
            area_variance = np.var(area_array)
            
            # Select the corner with lowest variance (least detail)
            if area_variance < min_variance:
                min_variance = area_variance
                best_corner_index = i
        
        # Select corner and watermark
        x, y = corners[best_corner_index]
        selected_watermark = (
            watermark_white if np.mean(np.array(img.crop((x, y, x + wm_width, y + wm_height)).convert('L'))) < 128 
            else watermark_blue
        )
        
        # Create a copy of the image and add watermark
        watermarked_img = img.copy()
        watermarked_img.paste(selected_watermark, (x, y), selected_watermark)
        
        return watermarked_img


    
    def _upload_image_to_wordpress(self, file_path, filename, alt_text):
        """Upload an image to WordPress using the REST API."""
        try:
            upload_url = f"{self.wp_api_url}/media"
            
            with open(file_path, 'rb') as img_file:
                files = {'file': (filename, img_file, 'image/jpeg')}
                data = {'alt_text': alt_text}
                
                response = requests.post(
                    upload_url,
                    headers=self.auth_header,
                    files=files,
                    data=data
                )
                
                response.raise_for_status()
                media_data = response.json()
                logger.info(f"Uploaded image to WordPress: {filename} (ID: {media_data['id']})")
                
                return media_data
        except Exception as e:
            logger.error(f"Failed to upload image to WordPress: {e}")
            return None
    
    def _get_post_id_from_url(self, post_url):
        """Get WordPress post ID from URL."""
        try:
            post_url = post_url.rstrip('/')
            slug = post_url.split('/')[-1]
            
            response = requests.get(
                f"{self.wp_api_url}/posts",
                params={'slug': slug},
                headers=self.auth_header
            )
            
            response.raise_for_status()
            posts = response.json()
            
            if posts:
                return posts[0]['id']
            return None
        except Exception as e:
            logger.error(f"Failed to get post ID from URL {post_url}: {e}")
            return None

    def _get_post_media_ids(self, post_id):
        """Return the media IDs used by an existing post (inline images + featured image),
        so they can be cleaned up when the post is overwritten."""
        try:
            response = requests.get(
                f"{self.wp_api_url}/posts/{post_id}",
                params={'_fields': 'content,featured_media'},
                headers=self.auth_header
            )
            response.raise_for_status()
            data = response.json()
            ids = {int(m) for m in re.findall(r'wp-image-(\d+)', data.get('content', {}).get('rendered', ''))}
            featured = data.get('featured_media')
            if featured:
                ids.add(int(featured))
            return ids
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Could not fetch existing media for post {post_id}: {e}")
            return set()

    def _delete_media(self, media_ids):
        """Permanently delete the given WordPress media items (used to purge the previous
        version's images after an overwrite)."""
        for mid in media_ids:
            try:
                requests.delete(
                    f"{self.wp_api_url}/media/{mid}",
                    params={'force': 'true'},
                    headers=self.auth_header
                )
                logger.info(f"Deleted old media {mid}")
            except requests.RequestException as e:
                logger.warning(f"Failed to delete old media {mid}: {e}")

    def _modify_html(self, html_content, main_keyword):
        soup = BeautifulSoup(html_content, "html.parser")

        for a_tag in soup.find_all("a"):
            if "NATCenter" in a_tag.get_text():
                a_tag["target"] = "_blank"

        text_nodes = [node for node in soup.find_all(string=re.compile(r'\bNATCenter\b', re.IGNORECASE)) if not node.find_parent("a")]
        if text_nodes:
            last_node = text_nodes[-1]
            last_text = str(last_node)
            last_text = re.sub(r'\b(NATCenter)\b', r'<a href="https://natcenter.vn" target="_blank">\1</a>', last_text, count=1)
            last_node.replace_with(BeautifulSoup(last_text, "html.parser"))

        return str(soup)
        
    def _resolve_category_id(self, category, fallback_slug='tin-tuc'):
        """Look up a WordPress category ID from the sheet's Category cell, falling back to
        `fallback_slug` if blank or not found. natcenter.vn has no ACF/Yoast REST exposure,
        so unlike SEO meta, categories are a real, writable wp/v2 field — worth getting right.

        The cell may hold either a plain category name or a full category URL
        (e.g. https://natcenter.vn/category/tu-van-lop-xe-o-to/); a URL is resolved by its
        slug, a name by search."""
        def _lookup(params):
            try:
                response = requests.get(f"{self.wp_api_url}/categories", params=params, headers=self.auth_header)
                response.raise_for_status()
                data = response.json()
                return data[0]['id'] if data else None
            except requests.RequestException as e:
                logger.warning(f"Failed to look up category {params}: {e}")
                return None

        if category and category.strip():
            category = category.strip()
            if category.startswith(('http://', 'https://')):
                # Extract the slug — the last non-empty path segment of the category URL.
                segments = [s for s in urlparse(category).path.split('/') if s]
                slug = segments[-1] if segments else ''
                category_id = _lookup({'slug': slug}) if slug else None
            else:
                category_id = _lookup({'search': category})
            if category_id:
                return category_id
            logger.warning(f"Category '{category}' not found — falling back to '{fallback_slug}'")

        return _lookup({'slug': fallback_slug})

    def publish_to_wordpress(self, doc_url, meta_title=None, meta_description=None,
                           keywords=None, tag=None, category=None, status='publish', existing_post_url=None):
        """Publish a Google Docs document to WordPress using the REST API."""
        try:
            doc_id = doc_url.split('/d/')[1].split('/')[0]
            doc = self.get_doc_content(doc_id)
            doc_title = doc.get('title', 'Untitled Document')

            extracted_data = self._extract_text_with_formatting(doc);

            html_content = extracted_data['post_content']
            post_title = extracted_data['post_title']
            yoast_seo_title = extracted_data['yoast_seo_title']
            yoast_seo_description = extracted_data['yoast_seo_description']

            images = self._find_images(doc_id)
            main_keyword = keywords[0] if keywords and len(keywords) > 0 else post_title

            html_content = self._modify_html(html_content, main_keyword)
            html_content, featured_image_id = self._replace_image_placeholders(
                html_content, images, main_keyword
            )

            # natcenter.vn runs RankMath (not Yoast) and has no ACF REST exposure —
            # `wp/v2/posts` only accepts registered meta keys (confirmed: none of
            # RankMath's or ACF's are), so SEO title/description can't be set here.
            # The FAQ section stays inline in post_content instead of a separate field.
            post_data = {
                'title': post_title,
                'content': html_content,
                'status': status,
                "date": datetime.now().isoformat(),
            }

            category_id = self._resolve_category_id(category)
            if category_id:
                post_data['categories'] = [category_id]

            # Check not existing_post_url
            if existing_post_url and isinstance(existing_post_url, str):
                existing_post_url = existing_post_url.strip()
                parsed_url = urlparse(existing_post_url)
                path = parsed_url.path  # Ví dụ: "/wp/client-la-gi/"
                segments = path.strip('/').split('/')  # ['wp', 'client-la-gi']
                slug = segments[-1] if segments else ''
                print(f'URL: {existing_post_url}, Path: {path}, Segments: {segments}, Slug: {slug}')
                post_data['slug'] = slug
            else:
                post_data['slug'] = main_keyword
                        
            if featured_image_id:
                post_data['featured_media'] = featured_image_id

            tags = []
            
            if tag:
                tag_slug = re.sub(
                    r'[^a-zA-Z0-9]+', 
                    '-', 
                    unidecode(tag.strip()).lower()
                ).strip('-')
            
                try:
                    response = requests.get(
                        f"{self.wp_api_url}/tags",
                        params={'slug': tag_slug},
                        headers=self.auth_header
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if data:
                        tag_id = data[0]['id']
                        tags.append(tag_id)
                        logger.info(f"Using existing tag '{tag_slug}' with ID {tag_id}")
                    else:
                        logger.info(f"Tag '{tag_slug}' not found — skipping")
                except requests.RequestException as e:
                    logger.warning(f"Failed to fetch tag '{tag_slug}': {e}")
            
            if tags:
                post_data['tags'] = tags
            
                            
            post_id = None
            if existing_post_url:
                post_id = self._get_post_id_from_url(existing_post_url)

            # When overwriting, remember the previous version's media so it can be purged
            # after a successful update (the new images were just uploaded with fresh IDs).
            old_media_ids = self._get_post_media_ids(post_id) if post_id else set()

            if post_id:
                response = requests.put(
                    f"{self.wp_api_url}/posts/{post_id}",
                    json=post_data,
                    headers=self.auth_header
                )
                logger.info(f"Updated existing post (ID: {post_id})")
            else:
                response = requests.post(
                    f"{self.wp_api_url}/posts",
                    json=post_data,
                    headers=self.auth_header
                )
                logger.info(f"Created new post")

            response.raise_for_status()
            post_data = response.json()

            if old_media_ids:
                self._delete_media(old_media_ids)
                       
            return {
                'id': post_data['id'],
                'url': post_data['link'],
                'status': post_data['status'],
                'title': post_data['title']['rendered'],
                'meta_title': meta_title or post_title,
                'meta_description': meta_description or yoast_seo_description,
                'featured_image': featured_image_id
            }
        
        except Exception as e:
            logger.error(f"Failed to publish to WordPress: {e}")
            raise

def publish_doc(
    doc_url,
    wp_url,
    username,
    password,
    meta_title=None,
    meta_description=None,
    keywords=None,
    tag=None,
    category=None,
    status='private',
    existing_post_url=None
):
    """Publish a Google Docs document to WordPress with auto-detected metadata."""
    publisher = GoogleDocsToWordPress(wp_url, username, password)
    post_info = publisher.publish_to_wordpress(
        doc_url=doc_url,
        meta_title=meta_title,
        meta_description=meta_description,
        keywords=keywords,
        tag=tag,
        category=category,
        status=status,
        existing_post_url=existing_post_url
    )
    return post_info

if __name__ == "__main__":
    wp_url = os.getenv("WP_URL")
    username = os.getenv("WP_USERNAME")
    password = os.getenv("WP_PASSWORD")

    result = publish_doc(
        doc_url="https://docs.google.com/document/d/13pf1NbK742OV2-Ar4NRsNgeUQIz_WvkX7hL4aKyFpbI/edit",
        wp_url=wp_url,
        username=username,
        password=password,
        meta_title=None,
        meta_description=None,
        keywords=None,
        tag=None,
        status="private",
        existing_post_url=None
    )
    
    print(f"Published post: {result['url']} (ID: {result['id']}, Status: {result['status']})")
    print(f"Meta Title: {result['meta_title']}")
    print(f"Meta Description: {result['meta_description']}")
    print(f"Featured Image ID: {result['featured_image']}")
