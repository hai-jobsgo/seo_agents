"""
Minimal project settings for the standalone seo_agents service.

Only what the copied SEO scripts actually reference is kept here (chiefly
`settings.BASE_DIR`, used by image_generator to locate the Google service-account
key). Environment variables come from the project-root `.env` file.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env from the project root (override=True mirrors jg_agents' settings.py).
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

DATA_DIR = os.path.join(BASE_DIR, 'data')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
LOG_DIR = os.getenv('LOG_DIR', os.path.join(BASE_DIR, 'logs'))

# --- WordPress target (the new website) ---
WP_URL = os.getenv('WP_URL')
WP_USERNAME = os.getenv('WP_USERNAME')
WP_PASSWORD = os.getenv('WP_PASSWORD')

# --- Google Sheets control sheet for this site ---
SEO_SHEET_ID = os.getenv('SEO_SHEET_ID')
SEO_SHEET_NAME = os.getenv('SEO_SHEET_NAME', 'SEO Flow')

# --- LLM / image API keys (read directly from env by crewai / google-genai) ---
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
