from bs4 import BeautifulSoup
import requests
import hashlib
import os
# from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from .base_parser import BaseParser
# from .parsers import ColorMeParser, AdvertisingVietnamParser

class SeleniumParser(BaseParser):
    def parse(self, use_selenium=False):
        return super().parse(True)
    
    
class TopCVParser(BaseParser):
    def parse(self):
        print('TopCVParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup
        
        # Extract main article content
        article_content = soup.find('div', class_='article-content')
        
        # Extract table of contents
        # table_of_contents = soup.find('div', id='article-table-contents')

        if article_content:
            self.process_article(article_content)
          

class CareerVietParser(BaseParser):
    def parse(self):
        print('CareerVietParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', {'id': 'article_detail'})

        # Extract table of contents by finding all h2 headings
        toc = []
        if article_content:
            self.process_article(article_content)

class VNWParser(BaseParser):
    def parse(self):
        print('VNWParser')
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='entry-content content-hl')
        table_of_contents = soup.find('div', id='ez-toc-container')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
                    # Remove login block and ads if present
            login_block = article_content.find('div', class_='login-block')
            if login_block:
                login_block.decompose()
            ads = article_content.find('div', class_='ads3')
            if ads:
                ads.decompose()
            self.article_html = str(article_content)
            self.article_content = self.replace_tags(self.article_html)
            
        # self.article_html = str(article_content) if article_content else None
        # self.article_content = article_content.get_text() if article_content else None
        if table_of_contents:
            self.table_of_contents = self.replace_tags(str(table_of_contents))


# class Vieclam24hParser(BaseParser):
#     def parse(self):
#         print('CareerVietParser')
#         # soup = BeautifulSoup(html, 'html.parser')
#         super().parse(True)
#         soup = self.soup

#         # Extract main article content
#         article_content = soup.find('article')

#         # Extract table of contents by finding all h2 headings
#         if article_content:
#             self.process_article(article_content)

class GlintsParser(BaseParser):
    def parse(self):
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='singlecontent')
        table_of_contents = soup.find('div', id='ez-toc-container')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.article_html = str(article_content)
            self.article_content = self.replace_tags(self.article_html)
            
        # self.article_html = str(article_content) if article_content else None
        # self.article_content = article_content.get_text() if article_content else None
        if table_of_contents:
            self.table_of_contents = self.replace_tags(str(table_of_contents))


# class CareerLinkParser(BaseParser):
#     def parse(self):
#         print('CareerLinkParser')
#         # soup = BeautifulSoup(html, 'html.parser')
#         super().parse(True)
#         soup = self.soup

#         # Extract main article content
#         article_content = soup.find('div', class_='entry-content')
#         try:
#             article_content.find('div', id='toc_container').decompose()
#         except:
#             print("CareerLink TOC not found!")
        
#         # Extract table of contents by finding all h2 headings
#         if article_content:
#             self.process_article(article_content)

class NetTopParser(BaseParser):
    def parse(self):
        print('CareerLinkParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='dynamic-entry-content')
        try:
            article_content.find('div', id='ez-toc-container').decompose()
        except:
            print("TOC not found!")
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)
        

class NavigosParser(BaseParser):
    def parse(self):
        print('NavigosParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='fullcontent')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class PaceParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='blog-content')
        table_of_contents = soup.find('div', id='tocDiv')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.article_html = str(article_content)
            self.article_content = self.replace_tags(self.article_html)
            
        # self.article_html = str(article_content) if article_content else None
        # self.article_content = article_content.get_text() if article_content else None
        if table_of_contents:
            self.table_of_contents = self.replace_tags(str(table_of_contents))

class TraCuuThanSoHocParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', id='ftwp-postcontent')
        table_of_contents = article_content.find('nav', id='ftwp-contents')

        # self.article_html = str(article_content) if article_content else None
        # self.article_content = article_content.get_text() if article_content else None
        if table_of_contents:
            print('found toc for tracuuthansohoc')
            self.table_of_contents = self.replace_tags(str(table_of_contents))
            
            table_of_contents.decompose()
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.article_html = str(article_content)
            self.article_content = self.replace_tags(self.article_html)

class TuoiTreParser(BaseParser):
    def parse(self):
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='detail__main')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class ArticleParser(BaseParser):
    def parse(self):
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('article')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class ColorMeParser(BaseParser):
    def parse(self):
        print('ColorMeParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='editor-view')
        
        if article_content:
            self.process_article(article_content)
           

class AdvertisingVietnamParser(BaseParser):
    def parse(self):
        print('AdvertisingVietnamParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='main-content')
        
        if article_content:
            self.process_article(article_content)

class HrChannelsParser(BaseParser):
    def parse(self):
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='single-post-detail')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)
           
class FastworkParser(BaseParser):
    def parse(self):
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', {'class': 'post-content'})
        
        if article_content:
            self.process_article(article_content)

class UmtEduParser(BaseParser):
    def parse(self):
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', {'class': 'newsdetail__description'})
        
        if article_content:
            self.process_article(article_content)

class HotCoursesParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

                # Extract main article content
        article_content = soup.find('article', {'itemprop': 'articleBody'})
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class VTIAcademyParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='description_detail_block')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class TopDevParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', {'id': 'ftwp-postcontent'})
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class AcabizParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', {'id': 'detail-blog'})
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)
            
# class TGDDParser(BaseParser):
#     def parse(self):
#         print('TGDDParser')
#         # soup = BeautifulSoup(html, 'html.parser')
#         super().parse(True)
#         soup = self.soup

#         # Extract main article content
#         article_content = soup.find('div', class_='news-content')
        
#         if article_content:
#             self.process_article(article_content)
#         else:
#             print('main content not found!')

class FPTShopParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', {'id': 'article-detail'})
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class VcCorpParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='blog_detail_body_content_ckeditor')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)   

class HocmaiParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='hm-panel-body')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)  

class GpoParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='content-job-dt')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content) 

class SunUniParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='article-inner')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content) 

class LOfficielParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('section', class_='article-layout__main')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class UnetiParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('section', class_='news-detail')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)
           
class TVPLParser(BaseParser):
    def parse(self):
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('section', id='news-content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class SaigonOfficeParser(BaseParser):
    def parse(self):
        print('SaigonOfficeParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', id='showText')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class KFCParser(BaseParser):
    def parse(self):
        print('KFCParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='full-content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class UngDungMoiParser(BaseParser):
    def parse(self):
        print('UngDungMoiParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='td-post-content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class DivPostContentParser(BaseParser):
    def parse(self):
        print('DivPostContentParser')
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='post-content')

        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)


class DivEntryContentParser(BaseParser):
    def parse(self):
        print('DivEntryContentParser')
        super().parse()
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='entry-content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class UelParser(BaseParser):
    def parse(self):
        print('UelParser')
        super().parse(False)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', id='content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class DNSEParser(BaseParser):
    def parse(self):
        print('DNSEParser')
        super().parse(False)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', id='wordpress-content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class TimViec365Parser(BaseParser):
    def parse(self):
        print('TimViec365Parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='blog_detail')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class PMSParser(BaseParser):
    def parse(self):
        print('UelParser')
        super().parse(False)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='article-inner')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)


class NEUParser(BaseParser):
    def parse(self):
        print('NEUParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='content-tintuc')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class PhucAnhParser(BaseParser):
    def parse(self):
        print('PhucAnhParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='article-col-main')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class JobokoParser(BaseParser):
    def parse(self):
        print('JobokoParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='ns-body')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class HLBankParser(BaseParser):
    def parse(self):
        print('HLBankParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='full-content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class EBHParser(BaseParser):
    def parse(self):
        print('EBHParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='blog')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class EuroRackParser(BaseParser):
    def parse(self):
        print('EBHParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='the_content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class UTTParser(BaseParser):
    def parse(self):
        print('UTTParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='single_post_content')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class IchiVietnamParser(BaseParser):
    def parse(self):
        print('IchiVietnamParser')
        # soup = BeautifulSoup(html, 'html.parser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='content-detail')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class HscParser(BaseParser):
    def parse(self):
        print('HscParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='main-entry')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class IdesignParser(BaseParser):
    def parse(self):
        print('IdesignParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='editor')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class HotelJobParser(BaseParser):
    def parse(self):
        print('IdesignParser')
        super().parse(True)
        soup = self.soup

        # Extract main article content
        article_content = soup.find('div', class_='main-content-inner')
        
        # Extract table of contents by finding all h2 headings
        if article_content:
            self.process_article(article_content)

class GenericParser(BaseParser):
    def parse(self):
        print('GenericParser')
        # Use Selenium
        super().parse(True)
        soup = self.soup

        # Extract the whole document body as the article content
        article_content = soup.find('body')
        
        # Process the entire body content
        if article_content:
            self.process_article(article_content)
        else:
            print("Warning: Could not find body element in the HTML")
            # Fallback to the entire HTML if no body found
            self.process_article(soup)
            
PARSERS = {
    "blog.topcv.vn": ArticleParser,
    "topcv.vn": TopCVParser,
    "careerviet.vn": CareerVietParser,
    "vieclam24h.vn": ArticleParser,
    "chefjob.vn": ArticleParser,
    "atomisystems": ArticleParser,
    'oes.vn': ArticleParser,
    # "thegioididong.com": TGDDParser,
    "jobsgo.vn": DivPostContentParser,
    "pace.edu.vn": PaceParser,
    "hotcourses.vn": HotCoursesParser,
    "vccorp": VcCorpParser,
    "hrchannels.com": HrChannelsParser,
    "glints.com": GlintsParser,
    "thuvienphapluat.vn": TVPLParser,
    "vietnamworks.com": VNWParser,
    "tracuuthansohoc.vn": TraCuuThanSoHocParser,
    "colorme": ColorMeParser,
    "advertisingvietnam": AdvertisingVietnamParser,
    "careerlink": DivEntryContentParser,
    'fastwork': FastworkParser,
    'umt.edu': UmtEduParser, 
    'vtiacademy': VTIAcademyParser,
    "vti-solutions.vn": DivEntryContentParser,
    'topdev': TopDevParser,
    'fptshop': FPTShopParser,
    'hocmai': HocmaiParser,
    'nettop': NetTopParser,
    'gpo.vn': GpoParser,
    'sununi.edu.vn': SunUniParser,
    'meinvoice': ArticleParser,
    "saigonoffice": SaigonOfficeParser,
    "lofficielvietnam": LOfficielParser,
    "navigossearch": NavigosParser,
    "kfcvietnam": KFCParser,
    "ungdungmoi": UngDungMoiParser,
    "viet-thanh.vn": DivEntryContentParser,
    "duhoctrawise": DivEntryContentParser,
    "timviec365.vn": TimViec365Parser,
    "uel.edu.vn": UelParser,
    "vienthuongmaikinhtequocte.neu": NEUParser,
    "mikotech.vn": ArticleParser,
    "businesswiki.codx.vn": ArticleParser,
    "mychair.vn": ArticleParser,
    "linkpower.vn": ArticleParser,
    "vieclam-khoacntt.uneti": UnetiParser, 
    "tuoitre.vn": TuoiTreParser,
    "misa.vn": ArticleParser,
    "phucanh.vn": PhucAnhParser,
    "quasoft.vn": ArticleParser,
    "pms.edu.vn": PMSParser, 
    "joboko.com": JobokoParser,
    "www.sunlife.com.vn": ArticleParser,
    "dnse.com.vn": DNSEParser,
    "hlbank": HLBankParser, 
    "ebh.vn": EBHParser, 
    "tanca.io": ArticleParser,
    "eurorack.vn": EuroRackParser,
    "utt.edu.vn": UTTParser,
    "ichivietnam": IchiVietnamParser,
    "hsc.com.vn": HscParser,
    "idesign.vn":IdesignParser,
    "talentbold.com": HrChannelsParser, 
    "hoteljob.vn": HotelJobParser,
    "cet.edu.vn": DivEntryContentParser,
    "acabiz": AcabizParser, 
    "vietda.com.vn": ArticleParser,
}

# from webdriver_manager.chrome import ChromeDriverManager
def create_parser(url):
    for key, parser_cls in PARSERS.items():
        if key in url:
            return parser_cls(url)
    # Use a generic parser
    return GenericParser(url)