# config.py

import os

# Default configuration and Prompts
NUM_SEARCH = 10  # Number of links to parse from Google
SEARCH_TIME_LIMIT = 3  # Max seconds to request website sources before skipping to the next URL
TOTAL_TIMEOUT = 6  # Overall timeout for all operations
MAX_CONTENT = 500  # Number of words to add to LLM context for each search result
MAX_TOKENS = 1000  # Maximum number of tokens LLM generates
LLM_MODEL = 'gpt-4o-mini'  # 'gpt-3.5-turbo' #'gpt-4o'

# OpenAI API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")