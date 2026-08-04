from bs4 import BeautifulSoup
import requests
import hashlib
import os
import re
from selenium import webdriver
import zipfile
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse
import json

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# List of all supported SERP feature names
SERP_FEATURE_NAMES = [
    'FAQ',
    'Breadcrumb',
    'Video',
    'Image',
    'Ratings',          # For AggregateRating
    'SitelinksSearchBox',
    'GeneralSitelinksPotential', # Heuristic for good navigation
    'Table',
    'Price',            # For Product/Offer schema
    'JobPosting',
    'Event',
    'HowTo',
    'Recipe',
    'Article',          # General Article, BlogPosting, NewsArticle
    'LocalBusiness',
    'Organization',
    # 'Dataset',        # Uncomment if you need to check for Dataset schema
    # 'QAPage',         # Uncomment if you need to check for QAPage schema
]
# SERP_FEATURE_NAMES = [
#     'FAQ',
#     'Breadcrumb',
#     'Video',
#     'Image',
#     'Ratings',
#     'Sitelinks',
#     'Table',
#     'Price',
#     'Job Posting',
#     'Event',
# ]

class BaseParser:
    def __init__(self, url):
        self.soup = None
        self.title = None
        self.meta_desc = None
        self.h1 = None
        self.article_html = None
        self.article_content = None
        self.table_of_contents = None
        self.word_count = None
        self.keyword_density = None
        self.img_count = None
        self.table_count = None
        self.url = url
        self.json_ld_data = []
        self.url_hash = hashlib.md5(url.encode()).hexdigest()[:10]

    # def detect_serp_features(self):
    #     """
    #     Detect common SERP features from the HTML content.
    #     Returns a dict {feature_name: True/False}
    #     """
    #     soup = self.soup
    #     features = {k: False for k in SERP_FEATURE_NAMES}

    #     # FAQ: Look for FAQPage schema or FAQ markup
    #     if soup.find_all(attrs={"itemtype": "https://schema.org/FAQPage"}) or 'FAQPage' in str(soup):
    #         features['FAQ'] = True
    #     # Breadcrumb: schema or nav/breadcrumb markup
    #     if soup.find_all(attrs={"itemtype": "https://schema.org/BreadcrumbList"}) or soup.find(class_="breadcrumb"):
    #         features['Breadcrumb'] = True
    #     # Video: <video> tag or VideoObject schema
    #     if soup.find("video") or 'VideoObject' in str(soup):
    #         features['Video'] = True
    #     # Image: og:image or ImageObject schema
    #     if soup.find("meta", property="og:image") or 'ImageObject' in str(soup):
    #         features['Image'] = True
    #     # Ratings: AggregateRating schema
    #     if 'AggregateRating' in str(soup):
    #         features['Ratings'] = True
    #     # Sitelinks: nav with many links or Sitelinks Searchbox schema
    #     navs = soup.find_all('nav')
    #     if any(len(nav.find_all('a')) >= 4 for nav in navs) or 'SitelinksSearchBox' in str(soup):
    #         features['Sitelinks'] = True
    #     # Table: <table> tag
    #     if soup.find('table'):
    #         features['Table'] = True
    #     # Price: Product/Offer schema or price in text
    #     if 'Product' in str(soup) or 'Offer' in str(soup) or 'price' in str(soup).lower():
    #         features['Price'] = True
    #     # Job Posting: JobPosting schema
    #     if 'JobPosting' in str(soup):
    #         features['Job Posting'] = True
    #     # Event: Event schema
    #     if 'Event' in str(soup):
    #         features['Event'] = True
    #     return features

    def _parse_json_ld(self):
        """Parses all JSON-LD scripts and stores the data."""
        for script in self.soup.find_all('script', type='application/ld+json'):
            try:
                if script.string:
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        self.json_ld_data.extend(item for item in data if isinstance(item, dict))
                    elif isinstance(data, dict):
                        self.json_ld_data.append(data)
            except (json.JSONDecodeError, TypeError):
                # Malformed JSON or script.string is None, or data is not a dict/list of dicts
                continue

    def _check_schema_type(self, schema_type_names) -> bool:
        """
        Checks if any of the given schema types are present in Microdata or pre-parsed JSON-LD.

        Args:
            schema_type_names: A string or a list of strings representing schema.org types
                               (e.g., "FAQPage" or ["Product", "Offer"]).

        Returns:
            True if any of the schema types are found, False otherwise.
        """
        if not isinstance(schema_type_names, list):
            schema_type_names = [schema_type_names]

        # Check JSON-LD
        for item in self.json_ld_data:
            item_type = item.get('@type', '')
            if isinstance(item_type, list):
                if any(st_name in item_type for st_name in schema_type_names):
                    return True
            elif isinstance(item_type, str):
                if item_type in schema_type_names:
                    return True

        # Check Microdata
        for st_name in schema_type_names:
            if self.soup.find(attrs={"itemtype": f"http://schema.org/{st_name}"}) or \
               self.soup.find(attrs={"itemtype": f"https://schema.org/{st_name}"}):
                return True
        return False

    def detect_serp_features(self) -> dict:
        """
        Detects on-page elements that make a website eligible for common Google SERP features.

        Returns:
            A dict {feature_name: True/False} indicating eligibility.
        """
        self._parse_json_ld()

        features = {name: False for name in SERP_FEATURE_NAMES}

        # FAQ
        if self._check_schema_type('FAQPage'):
            features['FAQ'] = True

        # Breadcrumb
        if self._check_schema_type('BreadcrumbList'):
            features['Breadcrumb'] = True
        elif self.soup.find("nav", attrs={"aria-label": "breadcrumb"}): # Common ARIA pattern
            features['Breadcrumb'] = True
        # elif self.soup.find(class_=re.compile(r'\b(breadcrumb|breadcrumbs)\b', re.I)): # More flexible class check
            # features['Breadcrumb'] = True


        # Video
        if self._check_schema_type('VideoObject') or bool(self.soup.find("video")):
            features['Video'] = True

        # Image (Eligibility for image rich snippets/thumbnails)
        # og:image is a strong signal. ImageObject can also specify main images.
        if bool(self.soup.find("meta", property="og:image")) or self._check_schema_type('ImageObject'):
            features['Image'] = True

        # Ratings
        if self._check_schema_type('AggregateRating'): # Could also check for 'Review' schema
            features['Ratings'] = True

        # Sitelinks Search Box
        if self._check_schema_type('WebSite'): # SitelinksSearchBox is often part of WebSite schema
            for item in self.json_ld_data: # More specific check for SitelinksSearchBox
                if isinstance(item.get('@type'), str) and item.get('@type') == 'WebSite' and 'potentialAction' in item:
                    if isinstance(item['potentialAction'], dict) and \
                       item['potentialAction'].get('@type') == 'SearchAction':
                        features['SitelinksSearchBox'] = True
                        break
                    elif isinstance(item['potentialAction'], list):
                        for action in item['potentialAction']:
                            if isinstance(action, dict) and action.get('@type') == 'SearchAction':
                                features['SitelinksSearchBox'] = True
                                break
                        if features['SitelinksSearchBox']: break
            if not features['SitelinksSearchBox']: # Microdata check
                 website_schema = self.soup.find(attrs={"itemtype": "http://schema.org/WebSite"}) or \
                                  self.soup.find(attrs={"itemtype": "https://schema.org/WebSite"})
                 if website_schema and website_schema.find(attrs={"itemprop": "potentialAction", "itemtype": "http://schema.org/SearchAction"}):
                     features['SitelinksSearchBox'] = True


        # General Sitelinks Potential (Heuristic based on navigation)
        # This is a rough indicator; Google's sitelink generation is complex.
        navs = self.soup.find_all('nav')
        if any(len(nav.find_all('a', href=True)) >= 4 for nav in navs): # At least 4 links in a nav
            features['GeneralSitelinksPotential'] = True

        # Table (Can be used for Featured Snippets)
        if bool(self.soup.find('table')):
            features['Table'] = True

        # Price (Product/Offer schema)
        if self._check_schema_type(['Product', 'Offer']):
            features['Price'] = True
        # else: # Your original very broad fallback, less reliable for *eligibility*
            # soup_str_lower = str(self.soup).lower()
            # if 'price' in soup_str_lower:
            # features['Price'] = True

        # Job Posting
        if self._check_schema_type('JobPosting'):
            features['JobPosting'] = True

        # Event
        if self._check_schema_type('Event'):
            features['Event'] = True

        # HowTo
        if self._check_schema_type('HowTo'):
            features['HowTo'] = True

        # Recipe
        if self._check_schema_type('Recipe'):
            features['Recipe'] = True

        # Article (includes NewsArticle, BlogPosting as they are subtypes)
        if self._check_schema_type(['Article', 'NewsArticle', 'BlogPosting']):
            features['Article'] = True

        # LocalBusiness
        if self._check_schema_type('LocalBusiness') or \
           any(self._check_schema_type(subtype) for subtype in [
               'Restaurant', 'Store', 'HealthAndBeautyBusiness', 'Hotel', # Add more subtypes
           ]): # Add more specific LocalBusiness subtypes if needed
            features['LocalBusiness'] = True

        # Organization
        if self._check_schema_type('Organization'):
            features['Organization'] = True
        
        # Dataset (if you uncomment it in SERP_FEATURE_NAMES)
        # if 'Dataset' in SERP_FEATURE_NAMES and self._check_schema_type('Dataset'):
        #     features['Dataset'] = True

        # QAPage (if you uncomment it in SERP_FEATURE_NAMES)
        # if 'QAPage' in SERP_FEATURE_NAMES and self._check_schema_type('QAPage'):
        #     features['QAPage'] = True

        return features

    # def get_file_path(self, ext):
    #     return os.path.join(base_dir, 'output', 'articles', f"{self.url_hash}.{ext}")
    
    # def save_file(self, content, ext):
    #     # file_name = f"{self.url_hash}.{ext}"
    #     # output_file = os.path.join(base_dir, 'output', 'articles', file_name)
    #     # print('save text: ', output_file)
    #     output_file = self.get_file_path(ext)
    #     with open(output_file, 'w') as file:
    #         file.write(content)

    # def save_html(self, html):
    #     file_name = f"{self.url_hash}.html"
    #     output_file = os.path.join(base_dir, 'output', 'articles', file_name)
    #     print('save html: ', output_file)
    #     with open(output_file, 'w') as file:
    #         file.write(html)

    def replace_tags(self, html):
        soup = BeautifulSoup(html, "html.parser")

        # Define specific replacements
        tag_replacements = {
            "h1": "\n\n",  # Double newline before and after headers
            "p": "\n",      # Paragraphs get new lines
            "b": " ",       # Bold gets a space
            "i": " ",       # Italic gets a space
            "br": "\n",     # Line breaks get a newline
            "li": "\n• ",   # List items get a bullet point
            "ul": "\n",     # Add newline before list
        }

        # Process all tags in the document
        for tag in soup.find_all():
            replacement = tag_replacements.get(tag.name, " ")  # Default to space if tag is not matched
            tag.insert_before(replacement)  # Insert replacement before the tag
            tag.unwrap()  # Remove the tag but keep its content

        # Extract the final processed text
        return soup.get_text().strip()
    

    def stats(self, keyword):
        if self.article_html:
            self.img_count = len(re.findall(r"<img", self.article_html))
            self.table_count = len(re.findall(r"<table", self.article_html))
        if self.article_content:
            self.word_count = word_count = len(self.article_content.split())
            print('word_count: ', word_count)
            keyword_count = self.article_content.lower().count(keyword.lower())
            print('keyword_count: ', keyword_count)
            self.keyword_density = keyword_count / word_count

    def count_words(self, text):
        words = re.findall(r'\b\w+\b', text)  # Extract words only
        return len(words)

    # Find statistics in the whole articles
    def stats_all(self, keyword):
        domain = urlparse(self.url).netloc
        internal_links = []
        external_links = []
        for tag in self.soup.find_all('a', href=True):
            href = tag.get('href')
            parsed_href = urlparse(href)
            # Link is internal if netloc is empty (relative URL) or matches the current domain
            if not parsed_href.netloc or parsed_href.netloc == domain:
                internal_links.append(href)
            else:
                external_links.append(href)
        self.internal_links = internal_links
        self.external_links = external_links

        self.h2s = []
        self.h3s = []
        for tag in self.soup.find_all(['h2', 'h3']):
            if tag.name == 'h2':
                self.h2s.append(tag.text.strip())
            else:
                self.h3s.append(tag.text.strip())
        
        txt = self.soup.get_text()
        self.word_count = self.count_words(txt)
        self.img_count = len(self.soup.find_all('img'))
        self.table_count = len(self.soup.find_all('table'))
        # self.faq_count = len(self.soup.find_all('div', class_='faq-section'))
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        matches = re.findall(pattern, txt)
        self.keyword_count = len(matches)
        # print('regex keyword_count:', regex_keyword_count)
        self.keyword_density = self.keyword_count / self.word_count if self.word_count > 0 else 0

    # Proxy details


    # Create a Chrome extension to handle the proxy auth
    # def create_proxy_extension(self, host, port, user, password):
    #     manifest_json = """
    #     {
    #         "manifest_version": 3,
    #         "name": "Proxy Extension",
    #         "version": "1.0",
    #         "permissions": [
    #             "proxy",
    #             "declarativeNetRequest",
    #             "storage"
    #         ],
    #         "host_permissions": ["<all_urls>"],
    #         "background": {
    #             "service_worker": "background.js"
    #         }
    #     }
    #     """

    #     background_js = """
    #     var config = {
    #         mode: "fixed_servers",
    #         rules: {
    #             singleProxy: {
    #                 scheme: "http",
    #                 host: "%s",
    #                 port: %s
    #             },
    #             bypassList: []
    #         }
    #     };

    #     chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    #     function callbackFn(details) {
    #         return {
    #             authCredentials: {
    #                 username: "%s",
    #                 password: "%s"
    #             }
    #         };
    #     }

    #     chrome.webRequest.onAuthRequired.addListener(
    #         callbackFn,
    #         {urls: ["<all_urls>"]},
    #         ['blocking']
    #     );
    #     """ % (host, port, user, password)

    #     print("Background_js: ", background_js)

    #     # Create a new directory for the extension
    #     if not os.path.exists("proxy_extension"):
    #         os.makedirs("proxy_extension")
    #     print('extension dir: ', os.path.abspath("proxy_extension"))
    #     # Write the manifest and background files
    #     with open("proxy_extension/manifest.json", "w") as f:
    #         f.write(manifest_json)
    #     with open("proxy_extension/background.js", "w") as f:
    #         f.write(background_js)
        
    #     # Create the extension zip file
    #     with zipfile.ZipFile("proxy_extension.zip", "w") as zp:
    #         zp.write("proxy_extension/manifest.json", "manifest.json")
    #         zp.write("proxy_extension/background.js", "background.js")

    #     print('file path: ', os.path.abspath("proxy_extension.zip"))        
    #     return os.path.abspath("proxy_extension.zip")


    def parse(self, use_selenium=True):
        url = self.url
        print('parse: ', url)
        try:
            if use_selenium:
                print("use_selenium")
                options = Options()
                # options.add_argument("--disable-extensions")
                options.add_argument("--headless")  # Run in headless mode (no UI)
                options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
                # options.add_argument("--no-proxy-server") 
                # Debug print for options
                
                # Create the extension
                # Setup proxy if needed
                # if 'careerlink' in url or 'topcv' in url or 'jobsgo' in url:
                #     print('using proxy')
                #     proxy_host = os.environ.get('PROXY_HOST')
                #     proxy_port = os.environ.get('PROXY_PORT')
                #     proxy_user = os.environ.get('PROXY_USER')
                #     proxy_pass = os.environ.get('PROXY_PASS')
                #     proxy_extension = self.create_proxy_extension(proxy_host, proxy_port, proxy_user, proxy_pass)
                #     options.add_extension(proxy_extension)
                # else:
                #     print('no proxy')

                    # PROXY = os.environ.get('HTTP_PROXY')
                    # if PROXY:
                    #     print('using proxy')
                    #     seleniumwire_options = {
                    #         'proxy': {
                    #             'http': PROXY,
                    #             'https': PROXY,
                    #         }
                    #     }
                    #     print('seleniumwire_options: ', seleniumwire_options)
                        
                        # options.add_argument(f'--proxy-server={PROXY}')
                
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                # print(driver.capabilities.get("proxy", "No proxy settings found"))
                driver.get(url)

                html = driver.page_source
                driver.close()
                driver.quit()

                # Save the whole html

                # soup = BeautifulSoup(html, "html.parser")
            else:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}  # Set a user agent to avoid blocking
                PROXY = os.environ.get('HTTP_PROXY')
                proxies = {'http': PROXY, 'https': PROXY} if PROXY else None
                response = requests.get(url, headers=headers, timeout=10, proxies=proxies, verify=False)
                response.raise_for_status()  # Raise an error for bad responses
                response.encoding = 'utf-8'
                html = response.text
            
            # self.save_html(html)
            self.soup = soup = BeautifulSoup(html, 'html.parser')
        
            title = soup.title.string.strip() if soup.title else None
            meta_desc = None
            h1 = None
            
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"].strip()
            
            h1_tag = soup.find("h1")
            if h1_tag:
                h1 = h1_tag.get_text(strip=True)

            self.title = title
            self.meta_desc = meta_desc
            self.h1 = h1

            # return title, meta_desc, h1
        except requests.RequestException as e:
            print("parse error: ", str(e))

    

    def process_article(self, article_content):
        if self.table_of_contents is None:
            toc = []
            headings = article_content.find_all(['h2', 'h3'])
            for heading in headings:
                level = int(heading.name[1])
                toc.append(f"{'  ' * (level-1)}{heading.text.strip()}")
            self.table_of_contents = '\n'.join(toc)
    
        self.article_html = str(article_content)
        self.article_content = self.replace_tags(self.article_html)
        # self.save_file(self.article_html, 'html')
        # self.save_file(self.article_content, 'txt')
        # self.save_file(self.table_of_contents, 'toc.txt')
