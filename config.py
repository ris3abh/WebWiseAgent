# config.py

import os

# Default configuration and Prompts
NUM_SEARCH = 10  # Number of links to parse from Google
SEARCH_TIME_LIMIT = 3  # Max seconds to request website sources before skipping to the next URL
TOTAL_TIMEOUT = 6  # Overall timeout for all operations
MAX_CONTENT = 500  # Number of words to add to LLM context for each search result
MAX_TOKENS = 1000  # Maximum number of tokens LLM generates
LLM_MODEL = 'gpt-4o-mini'  # 'gpt-3.5-turbo' #'gpt-4o'

# Neo4j Configuration
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'password')

# Memory Settings
TEMP_MEMORY_DAYS = 30  # Default expiration for temporary memories
PERMANENT_MEMORY_DAYS = 90  # Default expiration for permanent memories
MEMORY_REVIEW_INTERVAL = 7  # Days between reviewing temporary memories

# Graph RAG Settings
ENABLE_CROSS_PROJECT = True  # Whether to enable cross-project connections
MAX_GRAPH_HOPS = 2  # Maximum hops for graph traversal
TOP_K_RESULTS = 5  # Number of top results to return from retrieval

# OpenAI API key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")