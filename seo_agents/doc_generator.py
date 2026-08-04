import os
import googleapiclient.discovery
from google.oauth2.service_account import Credentials
import re

# Base directory
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class DocGenerator:
    """Class to handle Google Doc generation and updating."""
    
    def __init__(self, credentials_path=None, debug=False):
        """
        Initialize the DocGenerator.
        
        Args:
            credentials_path: Path to the Google API credentials file
        """
        if credentials_path is None:
            credentials_path = os.path.join(base_dir, 'env', 'dashboard-gcloud.json')
        self.credentials_path = credentials_path
        self.drive_service = None
        self.docs_service = None
        self.debug = debug
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize Google Drive and Docs services."""
        # Set up the credentials for Google API
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/documents'
        ]
        
        credentials = Credentials.from_service_account_file(self.credentials_path, scopes=SCOPES)
        
        # Create Drive and Docs service objects
        self.drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=credentials)
        self.docs_service = googleapiclient.discovery.build('docs', 'v1', credentials=credentials)
    
    def gen_doc_file(self, content, keyword=None, title='', description='', h1='', format_table=True):
        """
        Generate or update a Google Doc with the provided content.
        
        Args:
            content: The main content to include in the document
            google_doc_url: URL of an existing Google Doc to update (if None, a new doc is created)
            keyword: Keyword for the document title (if creating a new doc)
            title: Suggested title to include at the top of the document
            description: Suggested description to include at the top of the document
            h1: Suggested H1 to include at the top of the document
            image_prompts: Image prompts to include at the top of the document
    
        Returns:
            The URL of the created or updated Google Doc
        """
        print('gen_doc_file format_table=', format_table)
        # Add metadata to the content
        lines = []
        if title:
            lines.append(f"# {title}")
        if description:
            lines.append(f"\n{description}")
        # if h1:
        #     lines.append(f"\n# {h1}")
        # if image_prompts:
        #     lines.append(f"\n{image_prompts}")
        lines.extend(content.split('\n'))
        
        content_with_metadata = '\n'.join(lines)

        # Format the content - returns clean text, paragraph styles, and tables
        clean_content, paragraph_styles = self.format_markdown_for_google_docs(content_with_metadata, format_table)

        # always create new doc
        doc_url = self._create_new_doc(clean_content, paragraph_styles, keyword)

        return doc_url
    
    def _create_new_doc(self, clean_content, paragraph_styles, doc_title):
        """Create a new Google Doc with the provided content."""
        try:
            # Create file
            file_metadata = {
                'name': doc_title,
                'mimeType': 'application/vnd.google-apps.document'
            }
            
            # Create empty document first
            doc_file = self.drive_service.files().create(body=file_metadata).execute()
            doc_id = doc_file['id']
            
            # Insert the content and apply formatting
            requests = []
            
            # First insert all text
            requests.append({
                'insertText': {
                    'location': {'index': 1},
                    'text': clean_content
                }
            })
            
            # Then apply all the stored paragraph styles
            requests.extend(paragraph_styles)
            
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, 
                body={'requests': requests}
            ).execute()
            
            # Make the file public for anyone with the link to edit
            self.drive_service.permissions().create(
                fileId=doc_id,
                body={'type': 'anyone', 'role': 'writer'},
                fields='id'
            ).execute()
            
            # Get the document link
            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
            
            print(f"Created Google Doc: {doc_url}")
            return doc_url
        except Exception as e:
            print(f"Failed to create Google Doc: {str(e)}")
            return None
    
    def _update_existing_doc(self, clean_content, paragraph_styles, google_doc_url):
        """Update an existing Google Doc with the provided content."""
        try:
            # Extract document ID from the URL
            doc_id = google_doc_url.split('/d/')[1].split('/')[0]
            
            # First, get the document to check its content
            doc = self.docs_service.documents().get(documentId=doc_id).execute()
            
            # Create a request to delete all content
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)
                        }
                    }
                }
            ]
            
            # First insert all text
            requests.append({
                'insertText': {
                    'location': {'index': 1},
                    'text': clean_content
                }
            })
            
            # Then apply all the stored paragraph styles
            requests.extend(paragraph_styles)
            
            # Execute the batch update
            self.docs_service.documents().batchUpdate(
                documentId=doc_id, 
                body={'requests': requests}
            ).execute()
            
            # Ensure the document is shared with hai.pham@jobsgo.vn
            try:
                self.drive_service.permissions().create(
                    fileId=doc_id,
                    body={'type': 'user', 'role': 'writer', 'emailAddress': 'hai.pham@jobsgo.vn'},
                    fields='id'
                ).execute()
            except Exception as perm_error:
                # Permission might already exist, just log it
                print(f"Note on sharing permission: {str(perm_error)}")
                
            print(f"Updated Google Doc: {google_doc_url}")
            return google_doc_url
        except Exception as e:
            print(f"Failed to update Google Doc: {str(e)}")
            return google_doc_url
    
    def parse_markdown_table(self, lines, start_index):
        # Returns (table_rows, end_index)
        table_lines = []
        i = start_index
        while i < len(lines):
            line = lines[i]
            if re.match(r'^\s*\|.*\|\s*$', line):
                table_lines.append(line.strip())
                i += 1
            else:
                break
        # Remove separator line (second line)
        if len(table_lines) >= 2:
            del table_lines[1]
        # Parse rows
        rows = []
        for l in table_lines:
            # Remove leading/trailing | and split
            row = [cell.strip() for cell in l.strip('|').split('|')]
            print('row: ', row)
            rows.append(row)
            if len(rows[-1]) != len(rows[0]):
                raise ValueError("Table rows have different number of columns")
        return rows, i

    
    def format_markdown_for_google_docs(self, content, format_table=True):
        """
        Convert markdown content to structured content for Google Docs formatting.
        
        Args:
            content: Markdown content to format
            
        Returns:
            Tuple of (clean_content, paragraph_styles, all_tables_data) where:
                clean_content: Plain text content with markdown removed
                paragraph_styles: List of Google Docs API style requests
                all_tables_data: List of 2D lists, one for each table found
        """
        lines = content.split('\n')
        clean_lines = []
        paragraph_styles = []
        text_styles = []
        image_requests = []
        table_requests = [] # Insert table structure  first
        cell_requests = [] # Insert text to cell later
        
        index = 1  # Starting index for the document
        
        i = 0 # Current line index
        all_tables_data = []
        while i < len(lines):
            line = lines[i]
            if line.startswith('```'):
                # Ignore this line!
                i += 1
                continue
                
            # Process headings and normal text
            style = None
            
            # Check for image markdown
            # Extract image from markdown format: ![alt text](url "caption")
            image_pattern = r'!\[(.*?)\]\((.*?)(?:\s+\"(.*?)\")?\)'
            image_match = re.search(image_pattern, line)
            table_row_pattern = r'^\s*\|.*\|\s*$'
            table_sep_pattern = r'^\s*\|(?:\s*:?-+:?\s*\|)+\s*$'
            table_match = (
                re.match(table_row_pattern, line)
                and i + 1 < len(lines)
                and re.match(table_sep_pattern, lines[i + 1])
            )
            if image_match and image_match.group(2).startswith('http') and not 'placeholder' in image_match.group(2):
                # Extract the alt text and image URL
                alt_text = image_match.group(1)
                image_url = image_match.group(2)
                caption = image_match.group(3)
                print('image match: ', caption)
                # print('image url: ', image_url)
                
                # Add image request
                image_requests.append({
                    'insertInlineImage': {
                        'location': {'index': index},
                        'uri': image_url,
                        'objectSize': {
                            # 'height': {
                            #     'magnitude': 100,
                            #     'unit': 'PT'
                            # },
                            'width': {
                                'magnitude': 480,
                                'unit': 'PT'
                            }
                        }
                    }
                })
                # print(image_requests[-1])
                
                # Add empty line for the image
                clean_lines.append("")
                index += 1

                # Add caption as a separate line
                if caption:
                    clean_lines.append(caption)
                    index += len(caption) + 1
            
                i += 1
                continue
            elif table_match and format_table:
                print('table match')
                # Parse the table
                table_rows, table_end = self.parse_markdown_table(lines, i)
                num_rows = len(table_rows)
                num_cols = len(table_rows[0]) if num_rows > 0 else 0
                print('num_rows: ', num_rows)
                print('num_cols: ', num_cols)

                # Insert the table at the current index
                table_request = {
                    'insertTable': {
                        'rows': num_rows,
                        'columns': num_cols,
                        'location': {'index': index}
                    }
                }
                table_requests.append(table_request)
                table_start_index = index  # Save the index where table was inserted
                # index += 1  # Table is a block element

                # Insert the table structure
                all_tables_data.append(table_rows)
                i = table_end

                # --- Insert text into each cell using calculated indices ---
                if table_rows:
                    num_rows = len(table_rows)
                    num_cols = max(len(row) for row in table_rows)
                    # col_offset = 2
                    # row_offset = 1
                    # insert_requests = []
                    cell_index = table_start_index + 4
                    for r in range(num_rows):
                        for c in range(num_cols):
                            cell_text = table_rows[r][c] if c < len(table_rows[r]) else ""
                            if cell_text:
                                clean_text = ''
                                j = 0
                                while j < len(cell_text):
                                    # Handle bold formatting (**text**)
                                    if j < len(cell_text) - 1 and cell_text[j:j+2] == "**":
                                        # Found opening bold marker
                                        end_marker = cell_text.find("**", j+2)
                                        if end_marker != -1:
                                            # Found closing bold marker
                                            bold_text = cell_text[j+2:end_marker]
                                            clean_text += bold_text
                                            j = end_marker + 2  # Skip past closing marker
                                            continue
                                    
                                    # Regular character
                                    clean_text += cell_text[j]
                                    j += 1

                                # print('clean_text: %s => %s')
                        
                                cell_requests.append({
                                    'insertText': {
                                        'location': {'index': cell_index},
                                        'text': clean_text
                                    }
                                })
                            cell_index += 2
                        cell_index += 1
                        
                        
                    # Reverse the requests to avoid index shifting
                    # for req in reversed(insert_requests):
                    #     table_requests.append(req)
                continue
            elif line.startswith('* '):
                clean_line = line[2:].lstrip()
                style = 'BULLET_POINT'
            # Check for heading markers
            elif line.startswith('# '):
                clean_line = line[2:]
                style = 'HEADING_1'
            elif line.startswith('## '):
                clean_line = line[3:]
                style = 'HEADING_2'
            elif line.startswith('### '):
                clean_line = line[4:]
                style = 'HEADING_3'
            elif line.startswith('#### '):
                clean_line = line[5:]
                style = 'HEADING_4'
            else:
                clean_line = line
            
            # Process bold formatting (**text**)
            current_index = index
            clean_text = ""
            j = 0
            while j < len(clean_line):
                # Handle bold formatting (**text**)
                if j < len(clean_line) - 1 and clean_line[j:j+2] == "**":
                    # Found opening bold marker
                    bold_start = current_index + len(clean_text)
                    end_marker = clean_line.find("**", j+2)
                    if end_marker != -1:
                        # Found closing bold marker
                        bold_text = clean_line[j+2:end_marker]
                        clean_text += bold_text
                        bold_end = bold_start + len(bold_text)
                        # Add text style request for bold text
                        text_styles.append({
                            'updateTextStyle': {
                                'range': {'startIndex': bold_start, 'endIndex': bold_end},
                                'textStyle': {'bold': True},
                                'fields': 'bold'
                            }
                        })
                        j = end_marker + 2  # Skip past closing marker
                        continue
                
                # Handle links [text](url)
                elif clean_line[j] == '[':
                    link_text_start = j + 1
                    link_text_end = clean_line.find(']', link_text_start)
                    
                    # If we found closing bracket and it's followed by opening parenthesis
                    if link_text_end != -1 and link_text_end + 1 < len(clean_line) and clean_line[link_text_end + 1] == '(':
                        link_url_start = link_text_end + 2
                        link_url_end = clean_line.find(')', link_url_start)
                        
                        if link_url_end != -1:
                            # Extract the link text and URL
                            link_text = clean_line[link_text_start:link_text_end]
                            link_url = clean_line[link_url_start:link_url_end]
                            
                            # Add the text to our clean content
                            link_start_index = current_index + len(clean_text)
                            clean_text += link_text
                            link_end_index = link_start_index + len(link_text)
                            
                            # Add text style request for the link
                            text_styles.append({
                                'updateTextStyle': {
                                    'range': {'startIndex': link_start_index, 'endIndex': link_end_index},
                                    'textStyle': {'link': {'url': link_url}},
                                    'fields': 'link'
                                }
                            })
                            
                            # Skip past the entire link
                            j = link_url_end + 1
                            continue
                
                # Regular character
                clean_text += clean_line[j]
                j += 1
            
            clean_lines.append(clean_text)
            
            # If we identified a heading style, store the paragraph style request
            if style:
                # print('style: ', style, clean_text)
                if style == 'BULLET_POINT' and clean_text:
                    paragraph_styles.append({
                        'createParagraphBullets': {
                            'range': {
                                'startIndex': index,
                                'endIndex': index + len(clean_text) + 1
                            },
                            'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
                        }
                    })
                else:
                    paragraph_styles.append({
                        'updateParagraphStyle': {
                            'range': {'startIndex': index, 'endIndex': index + len(clean_text) + 1},
                            'paragraphStyle': {'namedStyleType': style},
                            'fields': 'namedStyleType'
                        }
                    })

                    # Make headings bold
                    if style.startswith('HEADING'):
                        text_styles.append({
                            'updateTextStyle': {
                                'range': {
                                    'startIndex': index,
                                    'endIndex': index + len(clean_text)
                                },
                                'textStyle': {
                                    'bold': True
                                },
                                'fields': 'bold'
                            }
                        })
                
            
            # Update the index for the next line
            index += len(clean_text) + 1  # +1 for newline
            i += 1
        
        # Reverse the requests to avoid index shifting
        cell_requests.reverse()
        clean_content = '\n'.join(clean_lines)

        print(image_requests)

        
        # Combine all formatting requests
        paragraph_styles.extend(text_styles)
        paragraph_styles.extend(image_requests)
        paragraph_styles.extend(table_requests)
        paragraph_styles.extend(cell_requests)

        print('all styles: ', len(paragraph_styles))
        # print('requests[355]: ', paragraph_styles[355])
        # print('requests[340-370]: ', paragraph_styles[340:370])
        return clean_content, paragraph_styles
