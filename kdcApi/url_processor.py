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
import pandas as pd
import time
class OptimizedUrlProcessor:
    def __init__(self, language: str = 'english', max_workers: int = 4):
        self._stop_words = None
        self.language = language
        self.max_workers = max_workers        
        self.word_pattern = re.compile(r"\b[a-zA-Z]+'?[a-zA-Z]{1,}\b")        
        self.session = requests.Session()
        self._ensure_nltk_data()
        self.pytrends = TrendReq(hl='en-US', tz=360, retries=2, backoff_factor=0.1)
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
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            response = self.session.get(url, headers=headers, timeout=timeout)
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

    def get_interest_over_time(self, keywords: List[str], max_keywords: int = 5) -> Dict[str, float]:
        if not keywords:
            return {}        
        keywords = keywords[:max_keywords]
        result = {}        
        try:
            self.pytrends.build_payload(kw_list=keywords, timeframe='today 3-m', geo='US')
            data = self.pytrends.interest_over_time()            
            if data.empty:
                return {keyword: 0.0 for keyword in keywords}                
            if 'isPartial' in data.columns:
                data = data.drop('isPartial', axis=1)                
            averages = data.mean()            
            for keyword in keywords:
                if keyword in averages:
                    result[keyword] = float(averages[keyword])
                else:
                    result[keyword] = 0.0                    
        except Exception as e:
            print(f"Error getting trends data: {e}")
            result = {keyword: 0.0 for keyword in keywords}            
        return result
    def get_phrases(self, words: List[str], n: int = 2) -> List[str]:
        return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]

    def process_url(self, url: str) -> Dict[str, Any]:
        html = self.fetch_url_content(url)
        if not html:
            return {"error": f"Failed to fetch content from {url}"}
        
        text = self.clean_html(html)
        words = self.extract_keywords(text)
        
        total_words = len(words)
        if total_words == 0:
            return {"error": "No valid words found in the content"}
        one_word_counter = Counter(words)
        one_word_stats = [
            {
                "keyword": word,
                "count": count,
                "percentage": f"{(count / total_words) * 100:.2f}%"
            }
            for word, count in one_word_counter.most_common(20)
        ]
        
        two_word_phrases = self.get_phrases(words, 2)
        two_word_counter = Counter(two_word_phrases)
        two_word_stats = [
            {
                "keyword": phrase,
                "count": count,
                "percentage": f"{(count / len(two_word_phrases) if two_word_phrases else 0) * 100:.2f}%"
            }
            for phrase, count in two_word_counter.most_common(20)
        ]
        
        three_word_phrases = self.get_phrases(words, 3)
        three_word_counter = Counter(three_word_phrases)
        three_word_stats = [
            {
                "keyword": phrase,
                "count": count,
                "percentage": f"{(count / len(three_word_phrases) if three_word_phrases else 0) * 100:.2f}%"
            }
            for phrase, count in three_word_counter.most_common(20)
        ]        
        one_word_keywords = [item['keyword'] for item in one_word_stats[:5]]
        two_word_keywords = [item['keyword'] for item in two_word_stats[:5]]
        three_word_keywords = [item['keyword'] for item in three_word_stats[:5]]        
        one_word_interest = self.get_interest_over_time(one_word_keywords)
        time.sleep(1) 
        two_word_interest = self.get_interest_over_time(two_word_keywords)
        time.sleep(1)  
        three_word_interest = self.get_interest_over_time(three_word_keywords)
        for item in one_word_stats:
            keyword = item['keyword']
            if keyword in one_word_interest:
                item['interest_over_time'] = one_word_interest[keyword]
            else:
                item['interest_over_time'] = 0.0
                
        for item in two_word_stats:
            keyword = item['keyword']
            if keyword in two_word_interest:
                item['interest_over_time'] = two_word_interest[keyword]
            else:
                item['interest_over_time'] = 0.0
                
        for item in three_word_stats:
            keyword = item['keyword']
            if keyword in three_word_interest:
                item['interest_over_time'] = three_word_interest[keyword]
            else:
                item['interest_over_time'] = 0.0
        
        return {
            "url": url,
            "total_words": total_words,
            "one_word": one_word_stats,
            "two_word": two_word_stats,
            "three_word": three_word_stats
        }

    def process_urls(self, urls: List[str]) -> Dict[str, Any]:
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.process_url, url): url for url in urls}
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception as e:
                    results[url] = {"error": str(e)}
        return results