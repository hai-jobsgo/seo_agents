import os
import gspread
from gspread.utils import rowcol_to_a1
import time
from datetime import datetime
from pathlib import Path

# Use relative imports when running from within the package
try:
    from .crew import ContentAnalyzerCrew
    from .doc_generator import DocGenerator
    from .parsers.parsers import create_parser
    from .image_generator import ImageGenerator
    from .utils import limit_words
except ImportError:
    # Fall back to absolute imports when running as a script
    from seo_agents.crew import ContentAnalyzerCrew
    from seo_agents.doc_generator import DocGenerator
    from seo_agents.parsers.parsers import create_parser
    from seo_agents.image_generator import ImageGenerator
    from seo_agents.utils import limit_words

# Base directory
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class ArticleWriter:
    def __init__(self):
        # Initialize the DocGenerator
        self.doc_generator = DocGenerator()
        
        # Initialize the ImageGenerator
        images_dir = os.path.join(base_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        self.image_generator = ImageGenerator(output_dir=images_dir)
        
        # Properties to store results
        self.improved_outline = None
        self.optimized_title = None
        self.optimized_description = None
        self.optimized_h1 = None
        self.suggested_content = None
        self.image_prompts = None
        # self.seo_review = None
        # self.improved_article = None
        # self.article_with_images = None
    
    async def write_article(self, ws, keyword, urls, sub_keywords='', suggested_outline='', reference_url='', target_length=None):
        """
        Run the URL analyzer crew.
        """
        col = 2
        outlines = []

        # Real current month/year, passed to prompts that may need to reference "now" for
        # genuinely time-sensitive content (e.g. price lists) - never hardcode a year in prompts.
        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # Add Header - Note: Content File header is removed as requested
        headers = ['Title', 'Meta Description', 'H1', 'Word Count', 'Keyword Density', 'Image Count', 'Table Count', 'Outline',
                   'Suggested Outline', 'Suuggested Title', 'Suggested Description', 'Suggested H1', 
                   'Article v1', 'Article v2', 'Article v3', 'Article v4', 'Article v5']
          
        
        # Calculate the A1 notation for the range
        start_a1 = rowcol_to_a1(2, 1)
        end_a1 = rowcol_to_a1(len(headers)+1, 1)
        
        # Update the header row with the headers
        values = [[header] for header in headers]
        ws.update(range_name=f"{start_a1}:{end_a1}", values=values)

        # Call the helper function to process URLs
        titles, descriptions, h1s, outlines, word_counts = await self._process_urls(ws, keyword, urls)
        word_count_guidance, word_count_ceiling = self._build_word_count_guidance(target_length, word_counts)
        print('word_count_guidance: ', word_count_guidance)
        print('word_count_ceiling: ', word_count_ceiling)

        # print('h1s: ', h1s)

        # print('outlines: ', outlines)

        # Read all relevant cells in one batch to reduce API calls
        cell_ranges = {
            'improved_outline': 'B10',
            'optimized_title': 'B11',
            'optimized_description': 'B12',
            'optimized_h1': 'B13',
            'article_v1': 'B14',
            'ai_review': 'F14',
            'article_v2': 'B15',
            'image_prompts': 'F15',
            'article_v3': 'B16',
            'article_v4': 'B17',
            'article_v5': 'B18',
            'reference_content': 'B19'
        }

        # Get all values in one API call
        cell_values = ws.batch_get([range_name for range_name in cell_ranges.values()])

        # Extract values from the returned data
        improved_outline = cell_values[0][0][0] if cell_values[0] and cell_values[0][0] else None
        optimized_title = cell_values[1][0][0] if cell_values[1] and cell_values[1][0] else None
        optimized_description = cell_values[2][0][0] if cell_values[2] and cell_values[2][0] else None
        optimized_h1 = cell_values[3][0][0] if cell_values[3] and cell_values[3][0] else None
        article_v1 = cell_values[4][0][0] if cell_values[4] and cell_values[4][0] else None
        ai_review = cell_values[5][0][0] if cell_values[5] and cell_values[5][0] else None
        article_v2 = cell_values[6][0][0] if cell_values[6] and cell_values[6][0] else None
        image_prompts = cell_values[7][0][0] if cell_values[7] and cell_values[7][0] else None
        article_v3 = cell_values[8][0][0] if cell_values[8] and cell_values[8][0] else None
        reference_content = cell_values[11][0][0] if cell_values[11] and cell_values[11][0] else None

        if reference_content is None:
            # Not cached yet - scrape the Reference URL (authoritative source for exact
            # product specs/data) once and cache the result for subsequent runs. Cache a
            # non-empty sentinel even when there's nothing to scrape, since gspread reads
            # an actually-blank cell back as falsy and we'd otherwise re-scrape every run.
            scraped = ''
            if reference_url:
                try:
                    ref_parser = create_parser(reference_url)
                    ref_parser.parse()
                    scraped = limit_words(ref_parser.article_content or '', 1500)
                except Exception as ex:
                    print('[write_articles] Error parsing reference URL:', ex)
            reference_content = scraped or 'N/A'
            ws.batch_update([
                {'range': 'B19', 'values': [[reference_content]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits
        reference_content = '' if reference_content == 'N/A' else reference_content

        if not improved_outline:
            # Check if we have a suggested_outline to follow
            if suggested_outline:
                print('[write_articles] Following suggested outline')
                inputs = {
                    "keyword": keyword,
                    "suggested_outline": suggested_outline,
                    "our_outline": outlines[0] if outlines[0] else "",
                    "competitor_1_outline": outlines[1],
                    "competitor_2_outline": outlines[2],
                    "competitor_3_outline": outlines[3],
                    "reference_content": reference_content,
                    "word_count_guidance": word_count_guidance
                }
                crew = ContentAnalyzerCrew().outline_following_crew()
            else:
                print('[write_articles] Generating new outline')
                inputs = {
                    "keyword": keyword,
                    "competitor_1_outline": outlines[1],
                    "competitor_2_outline": outlines[2],
                    "competitor_3_outline": outlines[3],
                    "reference_content": reference_content,
                    "word_count_guidance": word_count_guidance
                }
                crew = ContentAnalyzerCrew().outline_generation_crew()

            result = await crew.kickoff_async(inputs=inputs)
            improved_outline = result.raw
            # Update the improved outline to the spreadsheet
            ws.batch_update([
                {'range': 'B10', 'values': [[improved_outline]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits

            print("Improved outline: ", improved_outline)


        if not optimized_title:
            crew = ContentAnalyzerCrew().seo_content_optimization_crew()
            inputs = {
                "keyword": keyword,
                "content_outline": improved_outline,
                "current_title": titles[0],
                "current_meta_description": descriptions[0],
                "current_h1": h1s[0],
                "competitor_1_title": titles[1],
                "competitor_1_meta_description": descriptions[1],
                "competitor_1_h1": h1s[1],
                "competitor_2_title": titles[2],
                "competitor_2_meta_description": descriptions[2],
                "competitor_2_h1": h1s[2],
                "competitor_3_title": titles[3],
                "competitor_3_meta_description": descriptions[3],
                "competitor_3_h1": h1s[3],
                "current_month": current_month,
                "current_year": current_year
            }
            result = await crew.kickoff_async(inputs=inputs)
            print("SEO Improvement: ", result.json_dict)
            optimized_title = result.json_dict['title']
            optimized_description = result.json_dict['description']
            optimized_h1 = result.json_dict['h1']
            print(f"Token Usage: {result.token_usage}")
            # update the optimized elements to the spreadsheet using range update
            
            ws.batch_update([
                {'range': 'B11', 'values': [[optimized_title]]},
                {'range': 'B12', 'values': [[optimized_description]]},
                {'range': 'B13', 'values': [[optimized_h1]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits

        if not article_v1:
            print('Writing Article')
            writer = ContentAnalyzerCrew().seo_writer_crew()
            inputs = {
                "keyword": keyword,
                "content_outline": improved_outline,
                "optimized_title": optimized_title,
                "optimized_description": optimized_description,
                "optimized_h1": optimized_h1,
                "extra_request": sub_keywords,
                "word_count_guidance": word_count_guidance,
                "current_month": current_month,
                "current_year": current_year
            }
            result = await writer.kickoff_async(inputs=inputs)
            article_v1 = result.raw
            actual_word_count = len(article_v1.split())
            print("Generated content with word count:", actual_word_count)
            print(f"Token Usage: {result.token_usage}")

            # The writer agent doesn't reliably self-enforce the word-count ceiling from the
            # prompt alone, so trim explicitly here if it overshot.
            if word_count_ceiling and actual_word_count > word_count_ceiling:
                print(f"[write_articles] Article ({actual_word_count} words) exceeds ceiling "
                      f"({word_count_ceiling} words) - trimming")
                trimmer = ContentAnalyzerCrew().trim_article_crew()
                trim_inputs = {
                    "original_article": article_v1,
                    "target_word_count": word_count_ceiling,
                    "keyword": keyword
                }
                trim_result = await trimmer.kickoff_async(inputs=trim_inputs)
                trimmed_article = trim_result.raw
                trimmed_word_count = len(trimmed_article.split())
                print(f"[write_articles] Trimmed word count: {trimmed_word_count}")
                if trimmed_word_count < actual_word_count:
                    article_v1 = trimmed_article

            # Save result to file
            # with open(parser.get_file_path('out.txt'), 'w+') as f:
            #     f.write(article_v1)

            ws.batch_update([
                {'range': 'B14', 'values': [[article_v1]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits

        # SEO Review step
        if not ai_review:
            # print('Reviewing Article')
            # reviewer = ContentAnalyzerCrew().seo_reviewer_crew()
            # inputs = {
            #     "keyword": keyword,
            #     "article_content": article_v1
            # }
            # result = await reviewer.kickoff_async(inputs=inputs)
            # print("AI Review completed")
            # print(f"Token Usage: {result.token_usage}")
            # ai_review = result.raw
            ai_review = 'Skipped'
            ws.batch_update([
                {'range': 'F14', 'values': [[ai_review]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits

        
        # Rewrite step
        if not article_v2:
            article_v2 = article_v1
            ws.batch_update([
                {'range': 'B15', 'values': [[article_v2]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits

        # return

        # Generate image prompts
        if not image_prompts:
            print('Generating Image Prompts')
            image_generator = ContentAnalyzerCrew().image_prompts_crew()
            inputs = {
                "keyword": keyword,
                "article": article_v2
            }
            result = await image_generator.kickoff_async(inputs=inputs)
            image_prompts = result.raw
            print("Image prompts generation completed")
            print(f"Token Usage: {result.token_usage}")
            ws.batch_update([
                {'range': 'F15', 'values': [[image_prompts]]}
            ])
            time.sleep(1)  # Add a small delay to avoid API rate limits


        if not article_v3:
            print('Generating and inserting images')
            
            # Create a directory for this keyword's images
            keyword_image_dir = os.path.join(base_dir, 'images', keyword)
            print('keyword_image_dir: ', keyword_image_dir)
            os.makedirs(keyword_image_dir, exist_ok=True)

            
            # Update the output directory for this specific keyword
            self.image_generator.output_dir = keyword_image_dir
            
            # Generate images based on the image prompts
            # if image_prompts:
            try:
                # Parse image prompts and generate images
                generated_prompts = self.image_generator.generate_all_images(image_prompts)
                print('image prompts: ', generated_prompts)
                # print(f"Generated {len(generated_prompts)} images for {keyword}")
                
                
                # Save the paths of generated images for reference
                image_paths = [prompt.image_path for prompt in generated_prompts if prompt.image_path]
                print(f"Image paths: {image_paths}")

                # Insert images into the article
                article_v3 = self.image_generator.insert_images_into_article(article_v2, generated_prompts)
                ws.batch_update([
                    {'range': 'B16', 'values': [[article_v3]]}
                ])
                time.sleep(1)  # Add a small delay to avoid API rate limits
            except Exception as e:
                article_v3 = "Error generating images: " + str(e)
                print(f"Error generating images: {str(e)}")
                # If image generation fails, use the improved article without images
                # article_with_images = improved_article
        print('optimized_title: ', optimized_title)
        print('optimized_description: ', optimized_description)
        print('optimized_h1: ', optimized_h1)

        self.improved_outline = improved_outline
        self.optimized_title = optimized_title
        self.optimized_description = optimized_description
        self.optimized_h1 = optimized_h1
        self.article_v1 = article_v1
        self.ai_review = ai_review
        self.article_v2 = article_v2
        self.image_prompts = image_prompts
        self.article_v3 = article_v3

        # self.format_sheet(ws)

        return 'DONE'
        
    async def _process_urls(self, ws, keyword, urls):
        """
        Helper function to process URLs, fetch data from spreadsheet and parse URLs if needed.
        
        Args:
            ws: Worksheet object
            keyword: Keyword for SEO analysis
            urls: List of URLs to process
            
        Returns:
            tuple: (titles, descriptions, h1s, articles, outlines)
        """
        titles = ["" for _ in range(len(urls))]
        descriptions = ["" for _ in range(len(urls))]
        h1s = ["" for _ in range(len(urls))]
        # articles = ["" for _ in range(len(urls))]
        outlines = ["" for _ in range(len(urls))]
        word_counts = ["" for _ in range(len(urls))]

        # Read all cell values at once outside the loop to minimize API calls
        col_start = 2
        col_end = col_start + len(urls) - 1
        row_start = 2
        row_end = 9  # Row 9 has the outline (previously row 10 before we removed content_file row)
        
        # Create range for all cells we need (e.g. B2:Z9)
        start_col_letter = chr(64 + col_start)
        end_col_letter = chr(64 + col_end) if col_end <= 26 else chr(64 + int(col_end/26)) + chr(64 + (col_end % 26))
        range_str = f"{start_col_letter}{row_start}:{end_col_letter}{row_end}"
        
        # Get all cell values in one API call
        print(f"Reading range: {range_str}")
        all_values = ws.get_values(range_str)
        
        # Pad with empty rows if needed
        if not all_values:
            all_values = []
        while len(all_values) < (row_end - row_start + 1):
            all_values.append([])
            
        # Make sure each row has enough columns
        for i in range(len(all_values)):
            while len(all_values[i]) < len(urls):
                all_values[i].append("")

        col = 2  # Reset column counter for the loop

        for url in urls:
            if url:
                idx = col - col_start  # Index into our all_values array
                
                # Extract values from the pre-loaded data
                title = all_values[0][idx] if len(all_values) > 0 and len(all_values[0]) > idx else ""
                meta_desc = all_values[1][idx] if len(all_values) > 1 and len(all_values[1]) > idx else ""
                h1 = all_values[2][idx] if len(all_values) > 2 and len(all_values[2]) > idx else ""
                word_count = all_values[3][idx] if len(all_values) > 3 and len(all_values[3]) > idx else ""
                keyword_density = all_values[4][idx] if len(all_values) > 4 and len(all_values[4]) > idx else ""
                img_count = all_values[5][idx] if len(all_values) > 5 and len(all_values[5]) > idx else ""
                table_count = all_values[6][idx] if len(all_values) > 6 and len(all_values[6]) > idx else ""
                outline = all_values[7][idx] if len(all_values) > 7 and len(all_values[7]) > idx else ""
                
                # Only run parser if any of these values are empty
                should_run_parser = any(v is None or v == "" for v in [
                    title, meta_desc, h1, word_count, 
                    keyword_density, img_count, table_count, outline
                ])
                print('should_run_parser: ', url,  should_run_parser)
                
                # If we need to run parser due to missing data
                if should_run_parser:
                    # Create parser
                    parser = create_parser(url)
                    content = ""
                    toc = ""
                    print('Running parser for missing data')
                    for attemp in range(3):
                        if attemp > 0: 
                            print(f"Retry {attemp}")
                        try:
                            parser.parse()
                            parser.stats(keyword)

                            title = parser.title
                            meta_desc = parser.meta_desc
                            h1 = parser.h1
                            word_count = parser.word_count
                            keyword_density = parser.keyword_density
                            img_count = parser.img_count
                            table_count = parser.table_count
                            toc = parser.table_of_contents
                            content = parser.article_content
                            break
                        except Exception as ex:
                            print(ex)


                    if content:
                        inputs = {
                            'content': content,
                            'toc': toc
                        }
                        crew = ContentAnalyzerCrew().outline_extraction_crew()
                        result = await crew.kickoff_async(inputs=inputs)
                        print(f"Token Usage: {result.token_usage}")
                        outline = result.raw
                    else:
                        outline = "Content not available"

                    values = [
                        [parser.title or "NA"],
                        [parser.meta_desc or "NA"],
                        [parser.h1 or "NA"],
                        [parser.word_count],
                        [parser.keyword_density],
                        [parser.img_count],
                        [parser.table_count],
                        [outline or "NA"]
                    ]
                    print('values: ', values)
                    start_a1 = rowcol_to_a1(2, col)
                    end_a1 = rowcol_to_a1(9, col)  # Row 8 as we removed content_file row
                    cell_range = f"{start_a1}:{end_a1}"
                    ws.update(cell_range, values)
                    # ws.update_cell(9, col, outline)  # Changed from 10 to 9 as we removed content_file row
                else:
                    print('URL already parsed: ', url)
                
                # articles[col-2] = content
                titles[col-2] = title
                descriptions[col-2] = meta_desc
                h1s[col-2] = h1
                outlines[col-2] = outline
                word_counts[col-2] = word_count
            
            
                # Skip URLs that are empty
            col += 1
            

        print(titles)
        print(descriptions)
        print(h1s)
        # print(outlines)

        return titles, descriptions, h1s, outlines, word_counts
        # return titles, descriptions, h1s, articles, outlines

    def _build_word_count_guidance(self, target_length, word_counts):
        """
        Build a Vietnamese guidance string on target article length, and a hard
        numeric ceiling.

        If an explicit Target Length was set on the sheet row, it takes priority
        and overrides everything else. Otherwise, falls back to the original
        rule: derive the target from the word counts of the competitor source
        articles (urls[1:]; urls[0] is our own site's reference article,
        excluded from the competitor stats).

        Returns:
            tuple: (guidance_text: str, ceiling: int | None)
        """
        if target_length and target_length > 0:
            ceiling = round(target_length * 1.1)
            guidance = (
                f"Mục tiêu độ dài bài viết: khoảng {target_length} từ. "
                f"KHÔNG viết dài hơn đáng kể so với mục tiêu (tối đa vượt khoảng 10%, tức khoảng {ceiling} từ)."
            )
            return guidance, ceiling

        counts = []
        for wc in word_counts[1:]:
            try:
                n = int(str(wc).strip())
                if n > 0:
                    counts.append(n)
            except (TypeError, ValueError):
                continue

        if not counts:
            guidance = ("Không có dữ liệu số từ của đối thủ. Viết bài với độ dài vừa đủ để trả lời "
                        "đầy đủ ý định tìm kiếm của từ khóa, không kéo dài không cần thiết.")
            return guidance, None

        avg = round(sum(counts) / len(counts))
        lo, hi = min(counts), max(counts)
        ceiling = round(hi * 1.15)
        guidance = (
            f"Số từ các bài đối thủ: {', '.join(str(c) for c in counts)} "
            f"(trung bình ~{avg} từ, dao động {lo}-{hi} từ). "
            f"Mục tiêu độ dài bài viết của chúng ta: xấp xỉ mức trung bình này. "
            f"KHÔNG viết dài hơn đáng kể so với đối thủ dài nhất (tối đa vượt khoảng 10-15%, "
            f"tức khoảng {ceiling} từ)."
        )
        return guidance, ceiling
