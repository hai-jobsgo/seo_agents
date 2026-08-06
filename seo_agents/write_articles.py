import os
import argparse
import gspread
import requests
from bs4 import BeautifulSoup
import time
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from google.oauth2.service_account import Credentials
import googleapiclient.discovery
import asyncio
from gspread.utils import rowcol_to_a1
import logging

from crewai import Agent, Task, Crew, Process
from langchain_community.tools import tool

# Use relative imports when running from within the package
try:
    from .crew import ContentAnalyzerCrew
    from .doc_generator import DocGenerator
    # from .parsers.parsers import create_parser
    from .image_generator import ImageGenerator
    from .article_writer import ArticleWriter
    from .utils import setup_logger
except ImportError:
    # Fall back to absolute imports when running as a script
    from seo_agents.crew import ContentAnalyzerCrew
    from seo_agents.doc_generator import DocGenerator
    # from seo_agents.parsers.parsers import create_parser
    from seo_agents.image_generator import ImageGenerator
    from seo_agents.article_writer import ArticleWriter
    from seo_agents.utils import setup_logger

from seo_agents.task_logger import task_logger

# Base directory (project root — one level above the seo_agents package)
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def parse_target_length(value):
    """Parse the "Target Length" sheet cell into an int, or None if blank/invalid
    (ArticleWriter falls back to the competitor-word-count-based rule when None)."""
    try:
        return int(str(value).strip()) if value else None
    except (TypeError, ValueError):
        return None


class Command:
    def __init__(self):
        self.use_cache = True
        self.debug = True
        
        # Initialize the DocGenerator
        self.doc_generator = DocGenerator()
        
        # Initialize the ImageGenerator
        images_dir = os.path.join(base_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        self.image_generator = ImageGenerator(output_dir=images_dir)

    def prepare_worksheets(self):
        path = os.path.join(base_dir, 'env', 'dashboard-gcloud.json')
        gc = gspread.service_account(filename=path)
        sh = None
        try:
            if self.sheet_id:
                sh = gc.open_by_key(self.sheet_id)
        except:
            print('[write_articles] Spreadsheet not found. Unable to open the specified sheet.')

        if not sh:
            try:
                sh = gc.open(self.sheet_name)
            except:
                print('[write_articles] spreadsheet not found, creating new sheet')
                sh = gc.create(self.sheet_name)
            sh.share('hai.pham@jobsgo.vn', perm_type='user', role='writer')
        
        worksheets = {sheet.title: sheet for sheet in sh.worksheets()}
        return sh, worksheets

    def read_spreadsheet(self, ws):
        row_values = ws.get("A1:G1")[0]
        keyword = row_values[0]
        urls = row_values[1:5]
        reference_url = row_values[5] if len(row_values) > 5 else ''
        target_length = parse_target_length(row_values[6] if len(row_values) > 6 else '')
        return keyword, urls, reference_url, target_length

    async def scan_spreadsheet(self):
        sh, worksheets = self.prepare_worksheets()
        if self.debug:
            print('[write_articles]', worksheets.keys())
        ws1 = worksheets['Sheet1']
        
        # Read all rows from the first worksheet starting at row 2 up to row 100
        rows = ws1.get_all_values()[1:1000]
        print('[write_articles] rows count: ', len(rows))

        for row in rows:
            try:
                keyword = row[0]
                urls = row[1:5]
                reference_url = row[5] if len(row) > 5 else ''
                target_length = parse_target_length(row[6] if len(row) > 6 else '')
                status = row[7]
                link = row[8]
                doc_url = row[9] if len(row) > 9 else None
                sub_keywords = row[10] if len(row) > 10 else ''
                suggested_outline = row[11] if len(row) > 11 else ''
                
                if not keyword:  # no more keyword
                    print('[write_articles] no more keyword!')
                    break

                # if self.debug:
                #     print('[write_articles]', keyword, extra_request)

                ws_name = keyword
                row_index = rows.index(row) + 2
                
                if status == 'Review' and not doc_url:
                    print('Found unpublished keyword: ', keyword)
                    ws = worksheets[ws_name]
                    col_b_values = ws.col_values(2)  # Column B (gspread is 1-indexed for cols)
                    optimized_title = col_b_values[10]
                    optimized_description = col_b_values[11]
                    optimized_h1 = col_b_values[12]
                    current_article = col_b_values[-1]
                    # print('current article: ', len(current_article))
                    
                    doc_url = self.doc_generator.gen_doc_file(current_article, keyword, optimized_title, optimized_description, optimized_h1)

                    if not doc_url:
                        print('try again without formatting tables')
                        # Try one more time without format_table
                        doc_url = self.doc_generator.gen_doc_file(current_article, keyword, optimized_title, optimized_description, optimized_h1, format_table=False)
                    ws1.update_cell(row_index, 10, doc_url)

                elif status == 'Write':
                    # Update status to 'PROCESSING'
                    ws1.update_cell(row_index, 8, "Processing")
                    time.sleep(1)  # To avoid API rate limits
                    
                    attempt = 0
                    while attempt < 10:
                        if ws_name not in worksheets:
                            print('[write_articles] creating worksheet: ', ws_name)
                            # create new sheet
                            try:
                                ws = sh.add_worksheet(title=ws_name, rows=50, cols=10)
                                break
                            except Exception as ex0:
                                print('[write_articles] error adding sheet: ', ex0)
                                # try adding an increasing number to ws_name
                                attempt += 1
                                ws_name = f"{keyword}-{attempt}"
                        else:
                            ws = worksheets[ws_name]
                            break
                    if attempt >= 10:
                        print('[write_articles] Failed to create worksheet after 10 attempts')
                        # update status to failed
                        ws1.update_cell(row_index, 8, "Failed")
                        time.sleep(1)
                        continue

                    # Prepare a single row with keyword and urls
                    values = [[keyword] + urls]
                    range_start = "A1"
                    range_end = rowcol_to_a1(1, len(urls) + 1)
                    ws.update(range_name=f"{range_start}:{range_end}", values=values)
                    try:
                        # self.run(ws, keyword, urls)
                        writer = ArticleWriter()
                        await writer.write_article(ws, keyword, urls, sub_keywords, suggested_outline, reference_url, target_length)
                        status = "Review"
                    except Exception as ex0:
                        import traceback
                        print("[write_articles] Exception: ", ex0)
                        print("[write_articles] Detailed stack trace:")
                        traceback.print_exc()
                        status = "Failed"

                    ws1.update_cell(row_index, 8, status)

                    if not link:
                        link_formula = f'=HYPERLINK("#gid={ws.id}", "{keyword}")'
                        ws1.update_cell(row_index, 9, link_formula)
                        time.sleep(1)


                    if status == 'Review':
                        doc_url = self.doc_generator.gen_doc_file(writer.article_v3, keyword, writer.optimized_title, writer.optimized_description, writer.optimized_h1)
                        ws1.update_cell(row_index, 10, doc_url)

            except Exception as ex:
                import traceback
                print(f"[write_articles] Error processing row: {ex}")
                print("[write_articles] Detailed stack trace:")
                traceback.print_exc()


                
    def normalize_sheet_name(self, sheet_name):
        """
        Normalize sheet name by removing numerical suffixes like _1, _2, etc. and trimming spaces.
        """
        # Remove numerical suffixes like _1, _2, _3, etc.
        normalized = re.sub(r'_\d+$', '', sheet_name).strip()
        return normalized

    def delete_sheets(self):
        print('[write_articles] delete_sheets')
        sh, worksheets = self.prepare_worksheets()
        print('[write_articles]', worksheets.keys())
        ws1 = worksheets['Sheet1']

        # Read all rows from the first worksheet starting at row 2 up to row 500
        rows = ws1.get_all_values()[1:500]

        # Create a mapping of keywords to their status (column H) - case insensitive
        keyword_status_map = {}
        for row in rows:
            if row and len(row) > 7 and row[0]:  # Ensure we have keyword and status column
                keyword = row[0].strip()
                status = row[7] if len(row) > 7 else ''
                # Store with lowercase key for case-insensitive lookup
                keyword_status_map[keyword.lower()] = status

        # Only delete sheets whose corresponding keyword has status "Done"
        for sheet in worksheets:
            if sheet != 'Sheet1':  # Never delete Sheet1
                # Normalize sheet name and convert to lowercase for comparison
                normalized_sheet = self.normalize_sheet_name(sheet)
                lookup_key = normalized_sheet.lower()

                if lookup_key in keyword_status_map:
                    status = keyword_status_map[lookup_key]

                    if status == 'Done':
                        print(f'[write_articles] delete sheet: {sheet} (normalized: {normalized_sheet}, status: {status})')
                        sh.del_worksheet(worksheets[sheet])
                        time.sleep(1)
                    else:
                        print(f'[write_articles] keeping sheet: {sheet} (normalized: {normalized_sheet}, status: {status})')
                else:
                    print(f'[write_articles] sheet {sheet} (normalized: {normalized_sheet}) has no corresponding keyword in Sheet1, skipping deletion')

    async def run(self, ws, keyword, urls, reference_url='', target_length=None, generate_doc=False):
        writer = ArticleWriter()
        await writer.write_article(ws, keyword, urls, reference_url=reference_url, target_length=target_length) # pass other args as needed


@task_logger('write_articles_task')
async def write_articles_task():
    start_time = time.time()
    logger = setup_logger('write_articles.log')
    logger.info("write_articles_task started")
    try:
        # The control sheet for THIS site is set via env (SEO_SHEET_ID / SEO_SHEET_NAME).
        # Each website gets its own copy of the "SEO Flow" spreadsheet.
        sheet_id = os.getenv('SEO_SHEET_ID')
        sheet_name = os.getenv('SEO_SHEET_NAME', 'SEO Flow')
        if not sheet_id:
            logger.error("SEO_SHEET_ID is not set — nothing to scan")
            print('[write_articles] SEO_SHEET_ID not set, skipping')
            return

        print('[write_articles] scan spreadsheet')
        cmd = Command()
        cmd.sheet_name = sheet_name
        cmd.sheet_id = sheet_id
        await cmd.scan_spreadsheet()
        print('[write_articles] scan spreadsheet COMPLETED')
    except Exception as e:
        logger.exception(f"Error occurred in write_articles_task: {e}")
        print(f"[write_articles] Error in scan_spreadsheet_seo_task: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        duration = time.time() - start_time
        logger.info(f"write_articles_task ended, duration: {duration:.2f} seconds.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze URL content structure')
    parser.add_argument(
        '--delete',
        dest='delete',
        action='store_true',
        default=False,
        help='Delete redundant sheets',
    )
    parser.add_argument('--url', help='The URL to analyze')
    parser.add_argument('--keyword', help='The keyword to optimize')
    parser.add_argument(
        '--no-cache',
        dest='no_cache',
        action='store_true',
        default=False,
        help='No not cache content',
    )
    parser.add_argument(
        '--generate-doc',
        dest='generate_doc',
        action='store_true',
        default=False,
        help='Generate or update Google Doc with the article that includes images',
    )
    # parser.add_argument('--output', default='output/outline.md',
    #                    help='Output file path (default: output/outline.md)')

    args = parser.parse_args()
    command = Command()
    if args.no_cache:
        command.use_cache = False
    command.sheet_name = os.getenv('SEO_SHEET_NAME', 'SEO Flow')
    command.sheet_id = os.getenv('SEO_SHEET_ID')

    # command.base_dir = base_dir  # Initialize base_dir from the global variable
    command.debug=True

    if args.delete:
        command.delete_sheets()
    elif args.keyword: # do single keyword
        sh, worksheets = command.prepare_worksheets()
        ws = worksheets.get(args.keyword)
        if ws:
            keyword, urls, reference_url, target_length = command.read_spreadsheet(ws)
            result = command.run(ws, keyword, urls, reference_url=reference_url, target_length=target_length, generate_doc=args.generate_doc)
        else:
            print(f"[write_articles] Worksheet for keyword '{args.keyword}' not found")
    else:
        asyncio.run(command.scan_spreadsheet())