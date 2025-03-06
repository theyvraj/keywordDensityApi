import re
import requests
from typing import Dict, List, Any
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from collections import Counter
from pytrends.request import TrendReq
import time
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedUrlProcessor:
    def __init__(self, language: str = 'english', max_workers: int = 4):
        self._stop_words = None
        self.language = language
        self.max_workers = max_workers        
        self.word_pattern = re.compile(r"\b[a-zA-Z]+'?[a-zA-Z]{1,}\b")        
        self.session = requests.Session()
        self._ensure_nltk_data()
        
        # Initialize Pytrends with custom configuration
        self.pytrends = self._initialize_pytrends()
        
        # Rate limiting parameters
        self.request_interval = 5  # Minimum seconds between requests
        self.last_request_time = 0
        
    def _initialize_pytrends(self):
        """Initialize PyTrends with a workaround for the method_whitelist/allowed_methods issue"""
        try:
            # Try with default initialization first
            return TrendReq(hl='en-US', tz=360)
        except TypeError as e:
            logger.warning(f"Default PyTrends initialization failed: {e}. Trying custom initialization.")
            
            # Monkey patch the TrendReq class to handle both old and new versions of requests
            original_init = TrendReq.__init__
            
            def patched_init(self_trend, *args, **kwargs):
                try:
                    return original_init(self_trend, *args, **kwargs)
                except TypeError as e:
                    if 'method_whitelist' in str(e):
                        # We need to modify the TrendReq._get_data method
                        logger.info("Applying monkey patch for method_whitelist issue")
                        
                        original_get_data = TrendReq._get_data
                        
                        def patched_get_data(self_inner, url, method=TrendReq.GET_METHOD, trim_chars=0, **kwargs):
                            """Custom _get_data method to handle newer requests versions"""
                            s = requests.Session()
                            # We don't use the retry logic from TrendReq, we'll implement our own
                            return original_get_data(self_inner, url, method, trim_chars, **kwargs)
                        
                        TrendReq._get_data = patched_get_data
                        return original_init(self_trend, *args, **kwargs)
                    else:
                        raise
            
            # Apply the patch temporarly
            TrendReq.__init__ = patched_init
            
            # Try again with the patch applied
            try:
                return TrendReq(hl='en-US', tz=360)
            finally:
                # Restore original method
                TrendReq.__init__ = original_init

    def _ensure_nltk_data(self):
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)            
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)

    @property
    def stop_words(self):
        if self._stop_words is None:
            self._stop_words = set(stopwords.words(self.language))
        return self._stop_words

    @lru_cache(maxsize=128)
    def fetch_url_content(self, url: str, timeout: int = 10) -> str:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Error fetching {url}: {e}")
            return ""

    def clean_html(self, html: str) -> str:
        soup = BeautifulSoup(html, 'lxml')
        for script_or_style in soup(['script', 'style', 'head', 'meta', 'nav']):
            script_or_style.decompose()        
        return soup.get_text(separator=' ', strip=True)

    def extract_keywords(self, text: str) -> List[str]:
        words = word_tokenize(text.lower())
        words = [
            word for word in words 
            if self.word_pattern.match(word) and word not in self.stop_words
        ]        
        return words

    def get_phrases(self, words: List[str], n: int = 2) -> List[str]:
        return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
    
    def get_interest(self, keyword: str) -> Dict[str, Any]:
        """Get interest with rate limiting and retry mechanism"""
        # Apply rate limiting
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_interval:
            sleep_time = self.request_interval - elapsed + random.uniform(0.5, 1.5)
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f}s before querying '{keyword}'")
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()
        
        # Implement our own retry logic
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching interest data for '{keyword}' (attempt {attempt+1}/{max_retries})")
                self.pytrends.build_payload([keyword], cat=0, timeframe='today 12-m', geo='', gprop='')
                interest_over_time_df = self.pytrends.interest_over_time()
                
                if not interest_over_time_df.empty:
                    interest_over_time = interest_over_time_df[keyword].to_dict()
                    return interest_over_time
                else:
                    logger.info(f"No interest data found for '{keyword}'")
                    return {}
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for keyword '{keyword}': {e}")
                if "429" in str(e):
                    logger.warning(f"Rate limit exceeded (429). Backing off before retrying.")
                    # Force a longer cooldown on 429 errors
                    retry_delay = 60 + random.uniform(5, 15)
                
                if attempt < max_retries - 1:
                    # Exponential backoff
                    sleep_time = retry_delay * (2 ** attempt) + random.uniform(1, 5)
                    logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to get interest data after {max_retries} attempts")
                    return {}
                    
            except Exception as e:
                logger.error(f"Error fetching interest for keyword '{keyword}': {e}")
                return {}

    def process_url(self, url: str) -> Dict[str, Any]:
        html = self.fetch_url_content(url)        
        if not html:
            return {}
        cleaned_text = self.clean_html(html)
        words = self.extract_keywords(cleaned_text)
        
        total_words = len(words)
        if total_words == 0:
            return {}
            
        # Get most common terms first without interest data
        one_word_terms = Counter(words).most_common(10)
        two_word_terms = Counter(self.get_phrases(words, 2)).most_common(10)
        three_word_terms = Counter(self.get_phrases(words, 3)).most_common(10)
        
        result = {
            'one_word': self._get_keyword_stats(one_word_terms, total_words),
            'two_word': self._get_keyword_stats(two_word_terms, total_words),
            'three_word': self._get_keyword_stats(three_word_terms, total_words)
        }        
        return result

    def _get_keyword_stats(self, items: List[tuple], total_words: int) -> List[Dict[str, Any]]:
        """Process keyword statistics with proper rate limiting"""
        keyword_stats = []
        
        for keyword, count in items:
            # Add interest data with rate limiting handled in get_interest
            interest_over_time = self.get_interest(keyword)
            
            keyword_stats.append({
                'keyword': keyword,
                'count': count,
                'percentage': f"{(count / total_words) * 100:.2f}%",
                'interest_over_time': interest_over_time
            })
            
        return keyword_stats

    def process_multiple_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        results = []
        # Limit concurrent workers to reduce load
        actual_workers = min(self.max_workers, 2)  # Limit to at most 2 workers
        
        logger.info(f"Processing {len(urls)} URLs with {actual_workers} workers")
        
        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            future_to_url = {
                executor.submit(self.process_url, url): url 
                for url in urls
            }
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append({
                        'url': url,
                        'data': result
                    })
                    logger.info(f"Successfully processed URL: {url}")
                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")
                    results.append({
                        'url': url,
                        'data': {},
                        'error': str(e)
                    })
        return results