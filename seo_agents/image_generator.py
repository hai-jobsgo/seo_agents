# https://ai.google.dev/gemini-api/docs/image-generation
# https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-generate-preview-06-06
# https://cloud.google.com/vertex-ai/generative-ai/docs/models/imagen/4-0-fast-generate-preview-06-06
import os
import re
import base64
import requests
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional
# import google.generativeai as genai
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
import logging
import argparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import settings

# Load environment variables
load_dotenv(override=True)

# Configure the Gemini API
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     raise ValueError("GEMINI_API_KEY environment variable is not set")

# genai.configure(api_key=GEMINI_API_KEY)

class ImagePrompt:
    """Class to represent an image prompt extracted from the article."""
    
    def __init__(self, section: str, prompt: str, alt_text: str, caption: str, filename: str):
        self.section = section
        self.prompt = prompt
        self.alt_text = alt_text
        self.caption = caption
        self.filename = filename
        self.image_path = None  # Will be set after image generation
        self.image_url = None # Will be set after uploading images
        
    
    def __str__(self) -> str:
        return f"Section: {self.section}\nPrompt: {self.prompt[:100]}...\nFilename: {self.filename}\nAlt Text: {self.alt_text}\nCaption: {self.caption}"


class ImageGenerator:
    """Class to parse image prompts from articles and generate images using Gemini."""
    
    def __init__(self, output_dir: str = "images"):
        """
        Initialize the ImageGenerator.
        
        Args:
            output_dir: Directory to save generated images
        """
        self.output_dir = output_dir
        # self.model = genai.GenerativeModel('gemini-2.0-image-generation')
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.gcloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.gcloud_location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    
    def parse_image_prompts(self, image_prompts_text: str) -> List[ImagePrompt]:
        """
        Parse image prompts from the text.
        
        Args:
            image_prompts_text: Text containing image prompts
            
        Returns:
            List of ImagePrompt objects
        """
        image_prompts = []
        
        # Split by image sections (## Image X)
        image_sections = re.split(r'##\s+Image\s+\d+', image_prompts_text)
        
        # Skip the first element if it's empty (before the first ## Image)
        if image_sections and not image_sections[0].strip():
            image_sections = image_sections[1:]
        
        for i, section in enumerate(image_sections):
            if not section.strip():
                continue
                
            # Split the section into lines for easier processing
            lines = section.strip().split('\n')
            section_placement = f"Section {i+1}"
            prompt = ""
            alt_text = ""
            caption = ""
            filename = f"image_{i+1}.jpg"
            
            # Current field being processed
            current_field = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if "**Section Placement:**" in line:
                    section_placement = line.split("**Section Placement:**")[1].strip()
                    current_field = None
                elif "**Image Generation Prompt:**" in line:
                    prompt = line.split("**Image Generation Prompt:**")[1].strip()
                    current_field = "prompt"
                elif "**Alt Text (Vietnamese):**" in line:
                    alt_text = line.split("**Alt Text (Vietnamese):**")[1].strip()
                    current_field = "alt_text"
                elif "**Caption (Vietnamese):**" in line:
                    caption = line.split("**Caption (Vietnamese):**")[1].strip()
                    current_field = "caption"
                elif "**File Name:**" in line:
                    filename = line.split("**File Name:**")[1].strip()
                    current_field = None
                elif current_field == "prompt":
                    prompt += " " + line
                elif current_field == "alt_text":
                    alt_text += " " + line
                elif current_field == "caption":
                    caption += " " + line
            
            # Create ImagePrompt object
            image_prompt = ImagePrompt(
                section=section_placement,
                prompt=prompt,
                alt_text=alt_text,
                caption=caption,
                filename=filename
            )

            # print('parsed image prompt: ', image_prompt)
            
            image_prompts.append(image_prompt)
        
        return image_prompts
    
    def generate_image_gemini(self, prompt: ImagePrompt) -> Optional[str]:
        """
        Generate an image using Gemini based on the prompt.
        
        Args:
            prompt: ImagePrompt object containing the prompt
            
        Returns:
            Path to the saved image file or None if generation failed
        """
        print('generate_image: ', prompt)
        try:
            logger.info(f"Generating image for: {prompt.filename}")
            
            # Prepare the prompt for image generation
            generation_prompt = f"""
            Create a high-quality, professional image based on the following description:
            
            {prompt.prompt}
            
            The image should be suitable for a professional article about auto parts and car care (tires, oil, maintenance).
            """
            
            
            # Generate the image
            response = self.client.models.generate_content(
                # model="gemini-2.0-flash-exp-image-generation",
                model="gemini-2.5-flash-image",
                contents=(generation_prompt),
                config=types.GenerateContentConfig(
                    response_modalities=['Text', 'Image']
                )
            )
            
            # Check if we got a valid response
            if not response or not hasattr(response, 'candidates') or not response.candidates:
                logger.error(f"No valid response received for {prompt.filename}")
                return None
            
            # Get the image data from the response
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO((part.inline_data.data)))
                    image_path = os.path.join(self.output_dir, prompt.filename)
                    image.save(image_path)
                    prompt.image_path = image_path
                    return image_path
            # for part in response.parts:
            #     if part.text is not None:
            #         print(part.text)
            #     elif part.inline_data is not None:
            #         image = part.as_image()
            #         image_path = os.path.join(self.output_dir, prompt.filename)
            #         image.save(image_path)
            #         print('image saved')
            
            logger.error(f"No image data found in response for {prompt.filename}")
            return None
            
        except Exception as e:
            logger.error(f"Error generating image for {prompt.filename}: {str(e)}")
            return None

    
    def generate_image_imagen(self, prompt: ImagePrompt) -> Optional[str]:
        """
        Generate an image using Gemini based on the prompt.
        
        Args:
            prompt: ImagePrompt object containing the prompt
            
        Returns:
            Path to the saved image file or None if generation failed
        """
        print('generate_image: ', prompt)
        logger.info(f"Generating image for: {prompt.filename}")
        
        # Prepare the prompt for image generation
        generation_prompt = f"""
        Create a high-quality, professional image based on the following description:
        
        {prompt.prompt}
        
        The image should be suitable for a professional article about auto parts and car care (tires, oil, maintenance).
        """

        # gemini-2.5-flash-image: $0.039 per image
        # imagen-3.0-generate-002: $0.03 per image
        
        # Generate the image
        image = self.client.models.generate_images(
            model="gemini-2.5-flash-image",
            prompt=(generation_prompt),
            config=types.GenerateImagesConfig(
                number_of_images= 1,
                aspect_ratio="4:3",
            ),
        )
        image_path = os.path.join(self.output_dir, prompt.filename)
        image.generated_images[0].image.save(image_path)
        prompt.image_path = image_path
        return image_path

    def generate_image_direct(self, prompt: str, filename: str) -> Optional[str]:
        """
        Generates an image using a POST request to the Imagen API.

        Args:
            prompt: The text prompt for image generation.
            filename: The filename to save the image as.

        Returns:
            Path to the saved image file or None if generation failed.
        """
        logger.info(f"Generating image for prompt: {prompt}")

        try:
            # Get gcloud access token
            token_process = os.popen('gcloud auth print-access-token')
            token = token_process.read().strip()
            token_process.close()

            if not token:
                logger.error("Failed to get gcloud access token.")
                return None

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            }

            data = {
                "instances": [
                    {
                        "prompt": prompt
                    }
                ],
                "parameters": {
                    "sampleCount": 1
                }
            }

            url = f"https://{self.gcloud_location}-aiplatform.googleapis.com/v1/projects/{self.gcloud_project}/locations/{self.gcloud_location}/publishers/google/models/imagen-4.0-generate-preview-05-20:predict"

            response = requests.post(url, headers=headers, json=data)

            if response.status_code == 200:
                response_data = response.json()
                if 'predictions' in response_data and len(response_data['predictions']) > 0:
                    image_data_base64 = response_data['predictions'][0]['bytesBase64Encoded']
                    image_data = base64.b64decode(image_data_base64)
                    
                    image_path = os.path.join(self.output_dir, filename)
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    
                    logger.info(f"Image saved to {image_path}")
                    return image_path
                else:
                    logger.error(f"No predictions found in response for prompt: {prompt}")
                    return None
            else:
                logger.error(f"Error generating image for prompt: {prompt}. Status code: {response.status_code}, Response: {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error generating image for prompt {prompt}: {str(e)}")
            return None

    
    def generate_all_images(self, image_prompts_text: str) -> List[ImagePrompt]:
        """
        Parse image prompts and generate all images.
        
        Args:
            image_prompts_text: Text containing image prompts
            
        Returns:
            List of ImagePrompt objects with image_path set
        """
        print('generate_all_images')
        # Parse the image prompts
        image_prompts = self.parse_image_prompts(image_prompts_text)
        print('image_prompts: ', len(image_prompts))
        
        # Generate images for each prompt
        for prompt in image_prompts:
            # Add a small delay to avoid rate limiting
            time.sleep(1)
            self.generate_image(prompt)

        # Upload images to Google Drive and get public URLs
        image_prompts = self._upload_images_to_drive(image_prompts)

        return image_prompts

    def generate_image(self, prompt: ImagePrompt) -> Optional[str]:
        # return self.generate_image_imagen(prompt)
        return self.generate_image_gemini(prompt)
    
    def insert_images_into_article(self, article_text: str, image_prompts: List[ImagePrompt]) -> str:
        """
        Insert image markdown into the article at appropriate sections.
        
        Args:
            article_text: The article text
            image_prompts: List of ImagePrompt objects
            
        Returns:
            Updated article text with image markdown inserted
        """
        print('insert_images_into_article: ', len(image_prompts))
        
        # Sort image prompts by section to ensure proper ordering
        # image_prompts.sort(key=lambda x: x.section)
        
        # Create a copy of the article text to modify
        updated_article = article_text
        
        # Find headings in the article
        headings = re.finditer(r'^(#+)\s+(.*?)$', article_text, re.MULTILINE)
        heading_positions = [(m.group(2).strip(), m.end()) for m in headings]
        print('heading_positions: ', heading_positions)
        
        # Insert images at appropriate positions
        for prompt in image_prompts:
            if not prompt.image_url:
                logger.warning(f"Skipping image insertion for {prompt.filename} - no image URL available")
                continue
                
            # print("alt text: ", prompt.alt_text)
            
            # Create image markdown with the public URL
            image_markdown = f'\n\n![{prompt.alt_text}]({prompt.image_url} "{prompt.caption}")\n\n'
            
            # Find the appropriate section to insert the image
            section_name = prompt.section
            print('section_name: ', section_name)
            # Try to find an exact match for the section
            insert_position = None
            for heading, pos in heading_positions:
                if section_name.lower() in heading.lower():
                    # Insert after the first paragraph of the section rather than
                    # immediately under the heading - find the next paragraph break.
                    para_break = article_text.find('\n\n', pos)
                    insert_position = para_break if para_break != -1 else pos
                    break
            print('insert_position: ', insert_position)
            # If no exact match, use a heuristic approach
            if insert_position is None:
                # If it's the first image, insert after the first paragraph
                if prompt == image_prompts[0]:
                    # Find the end of the first paragraph
                    first_para_end = article_text.find('\n\n', 0)
                    if first_para_end != -1:
                        insert_position = first_para_end
                    else:
                        # If no paragraph break, insert at 25% of the article
                        insert_position = len(article_text) // 4
                else:
                    # For other images, distribute evenly
                    index = image_prompts.index(prompt)
                    portion = len(article_text) / (len(image_prompts) + 1)
                    target_position = int(portion * (index + 1))
                    
                    # Find the nearest paragraph break
                    para_breaks = [m.start() for m in re.finditer(r'\n\n', article_text)]
                    if para_breaks:
                        # Find the closest paragraph break
                        insert_position = min(para_breaks, key=lambda x: abs(x - target_position))
                    else:
                        insert_position = target_position
            
            # Insert the image markdown at the calculated position
            if insert_position is not None:
                updated_article = updated_article[:insert_position] + image_markdown + updated_article[insert_position:]
                
                # Update heading positions for subsequent insertions
                for i in range(len(heading_positions)):
                    if heading_positions[i][1] > insert_position:
                        heading_name, pos = heading_positions[i]
                        heading_positions[i] = (heading_name, pos + len(image_markdown))
        
        return updated_article
    
    def _upload_images_to_drive(self, image_prompts: List[ImagePrompt]) -> List[ImagePrompt]:
        """
        Upload images to Google Drive and update image prompts with public URLs.
        
        Args:
            image_prompts: List of ImagePrompt objects with local image paths
            
        Returns:
            List of ImagePrompt objects with image_url attribute set
        """
        print('Uploading images to Google Drive...')
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2 import service_account
        import mimetypes
        
        try:
            # Set up Google Drive API client
            SCOPES = ['https://www.googleapis.com/auth/drive']
            SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'env', 'dashboard-gcloud.json')
            
            credentials = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            drive_service = build('drive', 'v3', credentials=credentials)
            
            # Create or get the target folder
            folder_name = 'blogs/images'
            folder_id = self._get_or_create_folder(drive_service, folder_name)
            
            # Upload each image
            for prompt in image_prompts:
                if not prompt.image_path or not os.path.exists(prompt.image_path):
                    logger.warning(f"Skipping upload for {prompt.filename} - file not found")
                    continue
                
                # Determine MIME type
                mime_type, _ = mimetypes.guess_type(prompt.image_path)
                if not mime_type:
                    mime_type = 'image/jpeg'
                
                # Upload the file
                file_metadata = {
                    'name': prompt.filename,
                    'parents': [folder_id]
                }
                media = MediaFileUpload(prompt.image_path, mimetype=mime_type, resumable=True)
                file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink, webContentLink'
                ).execute()
                
                # Make the file publicly readable
                drive_service.permissions().create(
                    fileId=file.get('id'),
                    body={'type': 'anyone', 'role': 'reader'}
                ).execute()
                
                # Get the direct download link
                image_url = file.get('webContentLink')
                prompt.image_url = image_url
                logger.info(f"Uploaded {prompt.filename} to Google Drive. URL: {image_url}")

        except Exception as e:
            logger.error(f"Error uploading to Google Drive: {str(e)}")
            
        return image_prompts
    
    def _get_or_create_folder(self, drive_service, folder_name):
        """
        Get the ID of a folder in Google Drive, or create it if it doesn't exist.
        """
        # Check if the folder exists
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        response = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        
        if files:
            # Folder exists
            return files[0].get('id')
        else:
            # Create the folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive_service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate an image from a text prompt.')
    parser.add_argument('--prompt', default='A cat drinking a can of coke', type=str, help='The text prompt for image generation.')
    parser.add_argument('--output_dir', type=str, default='images', help='Directory to save the generated image.')
    parser.add_argument('--filename', type=str, default='generated_image.png', help='Filename for the generated image.')
    args = parser.parse_args()

    image_generator = ImageGenerator(output_dir=args.output_dir)
    image_path = image_generator.generate_image_direct(args.prompt, args.filename)

    if image_path:
        print(f"Image successfully generated and saved to: {image_path}")
    else:
        print("Failed to generate image.")
   

def main():
    """Test the ImageGenerator class."""
    # Example image prompts text
    image_prompts_text = """
## Image 1

**Section Placement:** Introduction

**Image Generation Prompt:** Create a professional photograph showing a technician inspecting a car tire in a clean, modern auto service center. The image should show a realistic, well-lit garage environment with tire-fitting equipment visible in the background. The style should be modern and clean, with a blue color scheme matching NATCenter's branding.

**Alt Text (Vietnamese):** Kỹ thuật viên đang kiểm tra lốp xe tại trung tâm dịch vụ NATCenter

**Caption (Vietnamese):** NATCenter cung cấp dịch vụ kiểm tra và thay lốp xe chuyên nghiệp, nhanh chóng.

**File Name:** natcenter_tire_check_1.jpg

---

## Image 2

**Section Placement:** Benefits of Using NATCenter

**Image Generation Prompt:** Create a split-screen comparison showing a worn, damaged tire on the left versus a brand-new tire being fitted at NATCenter on the right. Use a desaturated color palette for the worn tire side and vibrant colors for the new tire side to emphasize the contrast. Include Vietnamese visual elements subtly in the background.

**Alt Text (Vietnamese):** So sánh lốp xe cũ và lốp xe mới thay tại NATCenter

**Caption (Vietnamese):** NATCenter mang đến trải nghiệm thay lốp nhanh chóng, tiết kiệm thời gian so với các gara truyền thống.

**File Name:** natcenter_comparison_2.jpg
    """
    
    # Create an instance of ImageGenerator
    generator = ImageGenerator(output_dir="test_images")
    
    # Parse image prompts and generate images
    image_prompts = generator.generate_all_images(image_prompts_text)
    
    # Print the results
    for prompt in image_prompts:
        print(f"Generated image for {prompt.filename}: {prompt.image_path}")
    
    # Example article text
    article_text = """# Bảo Dưỡng Xe Ô Tô Hiệu Quả Với NATCenter

## Giới Thiệu

Bảo dưỡng xe ô tô định kỳ không còn là quá trình khó khăn và tốn thời gian như trước đây. Với sự phát triển của các trung tâm dịch vụ chuyên nghiệp, NATCenter đã trở thành địa chỉ đáng tin cậy giúp chủ xe chăm sóc phương tiện của mình một cách nhanh chóng và hiệu quả.

## Lợi Ích Khi Sử Dụng Dịch Vụ NATCenter

NATCenter mang đến nhiều lợi ích vượt trội so với các phương pháp bảo dưỡng truyền thống:

1. Tiết kiệm thời gian và công sức
2. Đội ngũ kỹ thuật viên giàu kinh nghiệm
3. Cập nhật phụ tùng, lốp xe chính hãng mới nhất
4. Hỗ trợ tư vấn bảo dưỡng chuyên nghiệp
5. Ứng dụng công nghệ để kiểm tra và chẩn đoán xe chính xác

## Cách Sử Dụng Dịch Vụ NATCenter Hiệu Quả

Để tận dụng tối đa các dịch vụ của NATCenter, chủ xe nên:

- Cập nhật đầy đủ thông tin và lịch sử bảo dưỡng xe
- Đặt lịch bảo dưỡng định kỳ
- Thiết lập thông báo cho các mốc bảo dưỡng quan trọng
- Chủ động liên hệ với kỹ thuật viên khi có dấu hiệu bất thường

## Kết Luận

NATCenter không chỉ là một trung tâm dịch vụ ô tô thông thường mà còn là người bạn đồng hành đáng tin cậy trên hành trình sử dụng xe của bạn. Hãy chủ động chăm sóc xe để đảm bảo an toàn và kéo dài tuổi thọ phương tiện.
"""
    
    # Insert images into the article
    updated_article = generator.insert_images_into_article(article_text, image_prompts)
    
    # Print the updated article
    print("\nUpdated Article:")
    print(updated_article)


if __name__ == "__main__":
    main()
