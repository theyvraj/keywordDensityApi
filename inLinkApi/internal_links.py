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
    """Fetch all internal links from a given URL, filtering out unwanted links."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)  # Increased timeout to 10 seconds
        if response.status_code != 200:
            print(f"Skipping {url} (Status Code: {response.status_code})")
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        
        for a_tag in soup.find_all('a', href=True):
            link = urljoin(url, a_tag['href'])
            parsed_link = urlparse(link)
            
            # Filter out links with fragments (#)
            if parsed_link.fragment:
                continue
            
            # Only consider links that match the base domain
            if parsed_link.netloc == domain:
                # Normalize the URL
                normalized_link = normalize_url(link)
                links.add(normalized_link)
        
        print(f"Found {len(links)} links on {url}")
        return links
    
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

def worker(queue, domain, visited, sitemap, lock):
    """Worker function to fetch links from a URL."""
    while True:
        url = queue.get()
        if url is None:  # Sentinel value to exit the thread
            break
        
        if url in visited:
            queue.task_done()
            continue
        
        with lock:
            visited.add(url)
        
        links = get_links(url, domain)
        
        with lock:
            sitemap.update(links)
            for link in links:
                if link not in visited:
                    queue.put(link)
        
        queue.task_done()

def crawl_website(start_url, num_threads=10):
    """Crawl the website and generate a sitemap using threading."""
    domain = urlparse(start_url).netloc
    visited = set()
    sitemap = set()
    queue = Queue()
    queue.put(start_url)
    lock = threading.Lock()

    # Create and start threads
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker, args=(queue, domain, visited, sitemap, lock))
        thread.start()
        threads.append(thread)

    # Wait for the queue to be empty
    queue.join()

    # Stop the threads by sending sentinel values
    for _ in range(num_threads):
        queue.put(None)
    
    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    return sitemap

def save_sitemap(sitemap, filename="sitemap.txt"):
    """Save the generated sitemap to a file."""
    with open(filename, "w") as file:
        for url in sorted(sitemap):
            file.write(url + "\n")
    print(f"Sitemap saved to {filename}")

if __name__ == "__main__":
    website_url = input("Enter website URL: ")
    start_time = time.time()
    sitemap = crawl_website(website_url)
    