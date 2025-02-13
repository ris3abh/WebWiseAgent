# utils/web_scraper.py

import os
import requests
from bs4 import BeautifulSoup
import time
import sys
from googlesearch import search
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import NUM_SEARCH, SEARCH_TIME_LIMIT, MAX_CONTENT, MAX_TOKENS, TOTAL_TIMEOUT
from utils.retrival import BM_RAGAM, VectorizedKnowledgeBase  # ensure the file name is correct
from typing import Tuple, Dict

def extract_main_content(soup):
    """
    Extracts the main textual content from a BeautifulSoup object by removing
    navigation, headers, footers, scripts, and styles.
    """
    # Remove unwanted elements
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
        element.decompose()
    
    # Try different strategies to locate the main content
    content = soup.find('article')
    if not content:
        content = soup.find('main')
    if not content:
        content = soup.find('div', class_=['content', 'main', 'article'])
    
    if content:
        paragraphs = content.find_all('p')
    else:
        paragraphs = soup.find_all('p')
    
    return ' '.join([para.get_text().strip() for para in paragraphs])

class EnhancedWebScraper:
    """
    EnhancedWebScraper integrates advanced retrieval mechanisms including:
    
    - **BM-RAGAM:** A hybrid retrieval approach that combines BM25-based keyword 
      matching and transformer-based semantic similarity with attention weighting.
    - **BM25 Filtering:** Ensures that only content with sufficient keyword 
      relevance is passed on.
    - **Vectorized Knowledge Base:** Stores document embeddings to support rapid 
      similarity search and structured document retrieval.
      
    This class performs a Google search for a query, fetches the content of the 
    returned URLs concurrently, and then ranks and filters the results based on 
    relevance to the query.
    """
    
    def __init__(self):
        # Initialize the BM_RAGAM retriever and the vectorized knowledge base
        self.ragam = BM_RAGAM()
        self.knowledge_base = VectorizedKnowledgeBase()
        
    def fetch_and_process_content(self, url: str, timeout: int) -> Tuple[str, str]:
        """
        Fetches the webpage at `url` within the specified `timeout`, parses the HTML 
        with BeautifulSoup, and extracts the main content using `extract_main_content()`.
        
        Returns:
            A tuple (url, content). If the content is too short or an error occurs,
            content will be None.
        """
        try:
            response = requests.get(url, timeout=timeout)
            soup = BeautifulSoup(response.text, 'lxml')
            content = extract_main_content(soup)
            # Basic filtering: only accept content that is longer than 50 characters.
            if content and len(content) > 50:
                return url, content
            else:
                return url, None
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return url, None

    def parse_google_results(self, query: str, num_search: int = NUM_SEARCH) -> Dict[str, str]:
        """
        Performs an enhanced Google search using the query and returns a dictionary 
        mapping each URL to its extracted content. The process involves:
        
        1. Using the `googlesearch` library to obtain initial URLs.
        2. Fetching each URL concurrently with `fetch_and_process_content()`.
        3. Adding the successfully fetched documents to a vectorized knowledge base.
        4. Ranking the documents using BM_RAGAM (hybrid BM25 and semantic similarity).
        5. Filtering out documents that do not meet a relevance threshold.
        
        Returns:
            A dictionary with URLs as keys and their corresponding content as values.
        """
        # Step 1: Get initial URLs from Google
        urls = list(search(query, num_results=num_search))
        
        # Step 2: Fetch webpage content concurrently
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(self.fetch_and_process_content, url, SEARCH_TIME_LIMIT): url 
                for url in urls
            }
            for future in as_completed(future_to_url):
                try:
                    url, content = future.result()
                    if content:
                        results.append((url, content))
                except Exception as e:
                    print(f"Error processing {future_to_url[future]}: {e}")
        if not results:
            return {}
        
        # Unpack URLs and contents from the results
        urls_list, contents = zip(*results)
        
        # Step 3: Add the fetched documents to the vectorized knowledge base.
        self.knowledge_base.add_documents(list(contents), list(urls_list))
        
        # Step 4: Rank the documents using BM_RAGAM (a hybrid of BM25 and semantic scoring)
        ranked_results = self.ragam.rank_documents(query, list(contents))
        
        # Step 5: Filter results based on a relevance threshold.
        relevance_threshold = 0.3  # You can adjust this threshold as needed.
        filtered_results = {}
        for idx, score in ranked_results:
            if score > relevance_threshold:
                filtered_results[urls_list[idx]] = contents[idx]
                
        return filtered_results
