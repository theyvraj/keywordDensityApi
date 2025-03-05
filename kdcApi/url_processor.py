import nltk
from nltk.corpus import stopwords
nltk.download('stopwords')
import requests
from bs4 import BeautifulSoup
from collections import Counter
import re
class takeUrl:
    def __init__(self):
        pass
    stop_words = set(stopwords.words('english'))    
    def clean_html(self, soup):
        body = soup.body
        if body:
            soup = BeautifulSoup(str(body), 'html.parser')
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        
        return soup.get_text()
    def get_keywords(self, text, stop_words):
        words = re.findall(r"\b[a-zA-Z]+'?[a-zA-Z]{1,}\b", text.lower())    
        words = [word for word in words if word not in stop_words]    
        return words  
    def get_phrases(self, words, n):
        return [' '.join(words[i:i+n]) for i in range(len(words)-n+1)]
    def process_url(self, url):
        response = requests.get(url)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        cleaned_text = self.clean_html(soup)
        words = self.get_keywords(cleaned_text, self.stop_words)
        total_words = len(words)
        one_phrase_keywords = Counter(words).most_common(10)
        two_phrase_keywords = Counter(self.get_phrases(words, 2)).most_common(10)
        three_phrase_keywords = Counter(self.get_phrases(words, 3)).most_common(10)
        result = {
            'one_word': {keyword: {'count': count, 'percentage': f"{(count / total_words) * 100:.2f}%"} for keyword, count in one_phrase_keywords},
            'two_word': {keyword: {'count': count, 'percentage': f"{(count / total_words) * 100:.2f}%"} for keyword, count in two_phrase_keywords},
            'three_word': {keyword: {'count': count, 'percentage': f"{(count / total_words) * 100:.2f}%"} for keyword, count in three_phrase_keywords},
        }
        return result