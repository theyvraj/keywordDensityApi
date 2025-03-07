import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import threading
import time
from queue import Queue
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
def normalize_url(url):
    if url.endswith('/'):
        url = url[:-1]
    return url

def get_links(url, domain):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Skipping {url} (Status Code: {response.status_code})")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        
        for a_tag in soup.find_all('a', href=True):
            link = urljoin(url, a_tag['href'])
            parsed_link = urlparse(link)
            if parsed_link.fragment:
                continue
            if parsed_link.netloc == domain:
                normalized_link = normalize_url(link)
                links.add(normalized_link)        
        print(f"Found {len(links)} links on {url}")
        return links    
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []
def worker(queue, domain, visited, internal_links, lock):
    while True:
        url = queue.get()
        if url is None:
            break        
        if url in visited:
            queue.task_done()
            continue        
        with lock:
            visited.add(url)        
        links = get_links(url, domain)        
        with lock:
            internal_links.update(links)
            for link in links:
                if link not in visited:
                    queue.put(link)        
        queue.task_done()

def crawl_website(start_url, num_threads=10):
    domain = urlparse(start_url).netloc
    visited = set()
    internal_links = set()
    queue = Queue()
    queue.put(start_url)
    lock = threading.Lock()
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker, args=(queue, domain, visited, internal_links, lock))
        thread.start()
        threads.append(thread)
    queue.join()
    for _ in range(num_threads):
        queue.put(None)
    for thread in threads:
        thread.join()
    return internal_links
if __name__ == "__main__":
    start_url = input("Enter website URL: ")
    sitemap = crawl_website(start_url)