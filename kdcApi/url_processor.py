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

class OptimizedUrlProcessor:
    def __init__(self, language: str = 'english', max_workers: int = 4):
        self._stop_words = None
        self.language = language
        self.max_workers = max_workers        
        self.word_pattern = re.compile(r"\b[a-zA-Z]+'?[a-zA-Z]{1,}\b")        
        self.session = requests.Session()
        self._ensure_nltk_data()

    def _ensure_nltk_data(self):
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab', quiet=True)            
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
            print(f"Error fetching {url}: {e}")
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

    def process_url(self, url: str) -> Dict[str, Any]:
        html = self.fetch_url_content(url)        
        if not html:
            return {}
        cleaned_text = self.clean_html(html)
        words = self.extract_keywords(cleaned_text)
        
        total_words = len(words)
        if total_words == 0:
            return {}
        result = {
            'one_word': self._get_keyword_stats(words, 1, total_words),
            'two_word': self._get_keyword_stats(self.get_phrases(words, 2), 2, total_words),
            'three_word': self._get_keyword_stats(self.get_phrases(words, 3), 3, total_words)
        }        
        return result

    def _get_keyword_stats(self, items: List[str], n: int, total_words: int) -> List[Dict[str, Any]]:
        return [
            {
                'keyword': keyword,
                'count': count,
                'percentage': f"{(count / total_words) * 100:.2f}%"
            }
            for keyword, count in Counter(items).most_common(10)
        ]

    def process_multiple_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
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
                except Exception as e:
                    print(f"Error processing {url}: {e}")        
        return results