import os
import re
import gspread
import logging
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def limit_words(text, max_words=500):
    words = re.findall(r'\S+', text)
    if len(words) > max_words:
        word_iter = re.finditer(r'\S+', text)
        end_pos = 0
        for i, match in enumerate(word_iter):
            if i == max_words:
                end_pos = match.end()
                break
        print(f'truncated segment to {max_words} words')
        return text[:end_pos]
    else:
        return text

def prepare_worksheets(sheet_name, sheet_id):
        path = os.path.join(base_dir, 'env', 'dashboard-gcloud.json')
        gc = gspread.service_account(filename=path)
        sh = None
        try:
            if sheet_id:
                sh = gc.open_by_key(sheet_id)
        except:
            print('[write_articles] Spreadsheet not found. Unable to open the specified sheet.')

        if not sh:
            try:
                sh = gc.open(sheet_name)
            except:
                print('[write_articles] spreadsheet not found, creating new sheet')
                sh = gc.create(sheet_name)
            sh.share('hai.pham@jobsgo.vn', perm_type='user', role='writer')
        
        worksheets = {sheet.title: sheet for sheet in sh.worksheets()}
        return sh, worksheets

def setup_logger(file_name):
    # --- Logging Setup ---
    LOG_DIR = os.getenv("LOG_DIR", os.path.join(base_dir, "logs"))
    LOG_FILE = os.path.join(LOG_DIR, file_name)

    # Create the directory if it doesn't exist
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger
