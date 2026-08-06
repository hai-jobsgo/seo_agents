import os
import argparse
import gspread
import time
import re
from urllib.parse import urlparse
from dotenv import load_dotenv
from seo_agents.doc_to_wp_api import publish_doc
from seo_agents.task_logger import task_logger
import traceback  # add for error logging
import logging
import asyncio

# Load environment variables
load_dotenv()

# Set up base directory (project root — one level above the seo_agents package)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- Logging Setup ---
# LOG_DIR is configurable (defaults to <project>/logs) so the service works without root.
LOG_DIR = os.getenv("LOG_DIR", os.path.join(base_dir, "logs"))
LOG_FILE = os.path.join(LOG_DIR, "publish_articles.log")

# Create the directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


class PublishCommand:
    def __init__(self, spreadsheet_id=None):
        self.wp_url = os.getenv("WP_URL")
        self.wp_username = os.getenv("WP_USERNAME")
        self.wp_password = os.getenv("WP_PASSWORD")
        self.spreadsheet_id = spreadsheet_id
        
        if not all([self.wp_url, self.wp_username, self.wp_password]):
            raise ValueError("WordPress credentials are not properly configured in environment variables")

    def prepare_worksheets(self):
        """Connect to Google Sheets and retrieve worksheets"""
        path = os.path.join(base_dir, 'env', 'dashboard-gcloud.json')
        gc = gspread.service_account(filename=path)
        try:
            sh = gc.open_by_key(self.spreadsheet_id)
        except:
            print('[publish_articles] Spreadsheet not found. Unable to open the specified sheet.', self.spreadsheet_id)
            try:
                name = "SEO Flow"
                sh = gc.open(name)
            except:
                print('[publish_articles] spreadsheet not found, creating new sheet')
                sh = gc.create(name)
                sh.share('hai.pham@jobsgo.vn', perm_type='user', role='writer')
        
        worksheets = {sheet.title: sheet for sheet in sh.worksheets()}
        return sh, worksheets

    def extract_keywords_from_title(self, title, keyword=None):
        """Extract keywords from article title for tagging"""
        if not title:
            return [keyword] if keyword else []
        
        # Add the main keyword if provided
        keywords = [keyword] if keyword else []
        
        # Extract additional keywords from the title
        # This is a simplified approach - remove common words, split by spaces and punctuation
        common_words = ['và', 'là', 'gì', 'các', 'những', 'để', 'khi', 'với', 'từ', 'cho', 
                        'cách', 'trong', 'của', 'tại', 'bạn', 'mới', 'nhất']
        
        # Clean title and split into potential keywords
        title_words = re.sub(r'[^\w\s]', ' ', title.lower()).split()
        
        # Filter words and add as keywords
        for word in title_words:
            if (word not in common_words and 
                len(word) > 3 and 
                word not in keywords and
                len(keywords) < 5):  # Limit to 5 keywords total
                keywords.append(word)
        
        return keywords

    def publish_to_wordpress(self, doc_url, wp_target_url, keyword, tag, category):
        """Publish Google Doc content to WordPress"""
        try:
            print(f"[publish_articles] Publishing document {doc_url} to {wp_target_url}")

            # Extract keywords/tags from the URL or use defaults
            keywords = self.extract_keywords_from_title(keyword, keyword)

            # Only treat wp_target_url as an existing post to update if it's actually
            # on the configured WP_URL host — otherwise (blank, or some other site) a
            # new post is created, which is the correct default for this site.
            existing_post_url = None
            if wp_target_url and urlparse(wp_target_url).netloc == urlparse(self.wp_url).netloc:
                existing_post_url = wp_target_url

            # Publish the document
            result = publish_doc(
                doc_url=doc_url,
                wp_url=self.wp_url,
                username=self.wp_username,
                password=self.wp_password,
                keywords=keywords,
                tag=tag,
                category=category,
                status='publish',  # Always publish
                existing_post_url=existing_post_url
            )
            url = result['url']
            print(f"[publish_articles] Published successfully: {url}")
            return True, url

        except Exception as e:
            print(f"[publish_articles] Failed to publish document: {str(e)}")
            return False, str(e)

    def scan_spreadsheet(self):
        """Scan spreadsheet for articles ready to publish"""
        sh, worksheets = self.prepare_worksheets()
        # print(f"Found {len(worksheets)} worksheets in spreadsheet")
        # print('[publish_articles]', worksheets.keys())
        ws1 = worksheets['Sheet1']
        
        # Read all rows from the first worksheet starting at row 2
        print('[publish_articles] getting cells...')
        rows = ws1.get("A2:P2000")  # only columns A–P, rows 2–1000

        print('[publish_articles] rows count: ', len(rows))
        found_publish = False

        for row in rows:
            try:
                if len(row) < 10:  # Ensure row has enough columns
                    continue

                keyword = row[0]
                wp_target_url = row[1]  # URL in WordPress where to publish
                status = row[7]
                doc_url = row[9] if len(row) > 9 else None
                tag = row[15] if len(row) > 15 else None
                category = row[13] if len(row) > 13 else None
                
                if not keyword:  # No more keywords
                    print('[publish_articles] no more keyword')
                    break
                
                # Skip rows that aren't ready to publish or don't have docs
                #if not (keyword == 'thuế PIT là gì' and doc_url):
                if status.lower() != 'publish' or not doc_url:
                    continue
                
                found_publish = True
                print(f"[publish_articles] Found article to publish: {keyword}")
                
                # Get current row index (for updating status later)
                row_index = rows.index(row) + 2  # +2 because sheet is 1-indexed and we skipped header
                
                # Update status to 'Processing'
                ws1.update_cell(row_index, 8, "Processing")
                time.sleep(1)  # Avoid API rate limits

                # Publish to WordPress
                success, result = self.publish_to_wordpress(doc_url, wp_target_url, keyword, tag, category)

                # Update status based on result
                new_status = "Done" if success else "Failed"
                ws1.update_cell(row_index, 8, new_status)

                # If successful, update the target URL cell if it was empty
                if success and (not wp_target_url or wp_target_url == ""):
                    ws1.update_cell(row_index, 2, result)
                
                # Add a small delay to avoid hitting API limits
                time.sleep(2)
                
            except Exception as e:
                print(f"[publish_articles] Error processing row: {str(e)}")
                continue
        
        if not found_publish:
            print("[publish_articles] No articles found with 'publish' status")

async def main():
    parser = argparse.ArgumentParser(description='Publish articles from Google Docs to WordPress')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no actual publishing)')

    args = parser.parse_args()
    await publish_article_task()

    # if args.dry_run:
    #     print("[publish_articles] DRY RUN MODE: Would check for articles to publish but won't actually publish them")
    # else:
    #     command.scan_spreadsheet()

@task_logger('publish_article_task')
async def publish_article_task():
    """Scheduled task to publish articles from Google Docs to WordPress"""
    start_time = time.time()
    logger.info("publish_article_task started")
    try:
        print('[publish_articles] publish_article_task')
        sheet_id = os.getenv('SEO_SHEET_ID')
        if not sheet_id:
            logger.error("SEO_SHEET_ID is not set — nothing to publish")
            print('[publish_articles] SEO_SHEET_ID not set, skipping')
            return
        cmd = PublishCommand(sheet_id)
        cmd.scan_spreadsheet()
    except Exception as e:
        logger.exception(f"Error occurred in publish_article_task: {e}")
        print(f"[publish_articles] Error in publish_article_task: {e}")
        traceback.print_exc()
    finally:
        duration = time.time() - start_time
        logger.info(f"publish_article_task ended, duration: {duration:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(main())
