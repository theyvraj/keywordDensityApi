import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import os
import json
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_url(url):
    if url.endswith('/'):
        url = url[:-1]
    return url

def check_url(start_url, current_url):
    start_netloc = urllib.parse.urlparse(start_url).netloc
    current_netloc = urllib.parse.urlparse(current_url).netloc
    return start_netloc == current_netloc

def get_link_data(soup, domain, url):
    internal_links = set()
    external_links = set()
    broken_links = set()
    links_in_page = set()
    link_queue = Queue()
    results = {
        "internal": set(),
        "external": set(),
        "broken": set(),
        "in_page": set()
    }
    
    # Add all links to the queue
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if '#' in href:
            continue            
        link_queue.put((href, link))
    
    # Worker function to process links
    def process_link():
        while not link_queue.empty():
            try:
                href, link = link_queue.get(block=False)
                anchor_text = link.get_text().strip() or "N/A"
                full_url = urllib.parse.urljoin(domain, href)
                full_url = normalize_url(full_url)
                
                try:
                    head_response = requests.head(full_url, timeout=5)
                    if head_response.status_code >= 400:
                        with threading.Lock():
                            results["broken"].add((full_url, anchor_text, url))
                    else:
                        # Only add to internal/external if not broken
                        if domain in full_url:
                            with threading.Lock():
                                results["internal"].add((full_url, anchor_text, url))
                                results["in_page"].add(full_url)
                        else:
                            with threading.Lock():
                                results["external"].add((full_url, anchor_text, url))
                except requests.RequestException:
                    with threading.Lock():
                        results["broken"].add((full_url, anchor_text, url))
            except Exception as e:
                logger.error(f"Error processing link: {e}")
            finally:
                link_queue.task_done()
    
    # Use threads to process links in parallel
    threads = []
    for _ in range(min(10, link_queue.qsize())):  # Use up to 10 threads
        thread = threading.Thread(target=process_link)
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    return results["internal"], results["external"], results["broken"], results["in_page"]


def get_page_data(url, domain):
    url = normalize_url(url)
    internal_links = set()
    external_links = set()
    broken_links = set()
    status_code = 'Error'
    links_in_page = set()  
    try:
        logger.info(f"Fetching data from: {url}")
        response = requests.get(url, timeout=8)
        status_code = response.status_code
        soup = BeautifulSoup(response.text, 'html.parser')        
        internal_links, external_links, broken_links, links_in_page = get_link_data(soup, domain, url)              
        logger.info(f"[{url}] Found {len(internal_links)} internal links and {len(external_links)} external links")
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")    
    return [
        status_code, internal_links, external_links, broken_links, 
         links_in_page
    ]

def process_url(current_link, start_url, link_details, visited_pages_lock, visited_links, all_internal_links, all_external_links, all_broken_links, links_to_visit, links_to_visit_lock):
    current_link = normalize_url(current_link)
    if not check_url(start_url, current_link):
        logger.info(f"Skipping external link: {current_link}")
        return
    
    try:
        # First check if the link is accessible before attempting to crawl
        try:
            head_response = requests.head(current_link, timeout=5)
            if head_response.status_code >= 400:
                logger.warning(f"Skipping broken link: {current_link} (Status: {head_response.status_code})")
                with visited_pages_lock:
                    all_broken_links.add((current_link, link_details.get(current_link, ("[No Text]", "Unknown"))[0], link_details.get(current_link, ("[No Text]", "Unknown"))[1]))
                return
        except requests.RequestException as e:
            logger.warning(f"Skipping broken link: {current_link} (Error: {e})")
            with visited_pages_lock:
                all_broken_links.add((current_link, link_details.get(current_link, ("[No Text]", "Unknown"))[0], link_details.get(current_link, ("[No Text]", "Unknown"))[1]))
            return
            
        link_data = get_page_data(current_link, start_url)
        (page_status_code, internal_links, external_links, broken_links, links_in_page) = link_data    
        
        default_link_info = ("[No Text]", "Unknown")
        link_info = link_details.get(current_link, default_link_info)
        
        # Add current link to all_internal_links
        with visited_pages_lock:
            all_internal_links.add(current_link)
            
            # Add new internal links to the queue
            with links_to_visit_lock:
                for link_url, anchor_text, source_url in internal_links:
                    normalized_link_url = normalize_url(link_url)
                    
                    # Check if we've already visited this link or have it in our queue
                    already_visited = normalized_link_url in all_internal_links
                    
                    if not already_visited and normalized_link_url not in link_details:
                        link_details[normalized_link_url] = (anchor_text, source_url)
                        links_to_visit.add(normalized_link_url)
                        
            # Update our collections of external and broken links
            all_external_links.update(external_links)
            all_broken_links.update(broken_links)
            visited_links.append(current_link)
                
    except requests.RequestException as e:
        logger.error(f"Request failed for {current_link}: {e}")
        with visited_pages_lock:
            all_broken_links.add((current_link, link_details.get(current_link, ("[No Text]", "Unknown"))[0], link_details.get(current_link, ("[No Text]", "Unknown"))[1]))

def crawl_internal_links(start_url, max_links=100, max_threads=10):
    start_url = normalize_url(start_url)
    logger.info(f"Starting crawl from: {start_url}")
    domain = urllib.parse.urlparse(start_url).netloc
    status_code = 200
    
    try:
        response = requests.get(start_url, timeout=8)
        status_code = response.status_code
        
        # Check if the start URL is accessible
        if status_code >= 400:
            logger.error(f"Start URL returns error status code: {status_code}")
            return []
            
    except requests.RequestException as e:
        logger.error(f"Request failed for start URL {start_url}: {e}")
        return []
    
    # Thread-safe collections
    visited_links = []  # Simple list of visited URLs
    links_to_visit = set()  # Set of links to visit
    link_details = {}  # Dictionary of link details
    all_internal_links = set()  # Set of all internal links
    all_external_links = set()  # Set of all external links
    all_broken_links = set()  # Set of all broken links
    
    # Locks for shared resources
    visited_pages_lock = threading.Lock()
    links_to_visit_lock = threading.Lock()
    
    links_to_visit.add(start_url)
    link_details[start_url] = ("[Start Page]", "")
    all_internal_links.add(start_url)
    
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        while links_to_visit and len(visited_links) < max_links:
            # Get the next batch of URLs to process
            with links_to_visit_lock:
                batch_size = min(max_threads, len(links_to_visit), max_links - len(visited_links))
                if batch_size <= 0:
                    break
                    
                current_batch = []
                for _ in range(batch_size):
                    if not links_to_visit:
                        break
                    current_link = links_to_visit.pop()
                    current_batch.append(current_link)
            
            # Process the batch in parallel
            futures = []
            for link in current_batch:
                future = executor.submit(
                    process_url, 
                    link, 
                    start_url, 
                    link_details, 
                    visited_pages_lock, 
                    visited_links, 
                    all_internal_links,
                    all_external_links, 
                    all_broken_links, 
                    links_to_visit, 
                    links_to_visit_lock
                )
                futures.append(future)
            
            # Wait for all URLs in this batch to be processed
            for future in futures:
                future.result()
                
            # Rate limiting
            time.sleep(0.5)  # Reduced from 2 seconds since we're processing in parallel
    
    logger.info(f"Crawl completed. Processed {len(visited_links)} links.")
    return list(all_internal_links)

if __name__ == "__main__":
    start_url = str(input('Enter the URL to you want to scrape: '))
    start_url = normalize_url(start_url)
    

    max_links = 100 
    max_threads = 5 
    
    try:
        internal_links = crawl_internal_links(
            start_url, 
            max_links=max_links, 
            max_threads=max_threads
        )
    except Exception as e:
        logger.error(f"An error occurred during execution: {e}")

    