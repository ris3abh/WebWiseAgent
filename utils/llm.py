# utils/llm.py

import os
import re
import backoff
import openai
import sys

# Ensure the NLTK resource is available
import nltk
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    print("Downloading NLTK punkt_tab resource...")
    nltk.download('punkt_tab')

from nltk.tokenize import sent_tokenize

print(sys.path)

from config import OPENAI_API_KEY, LLM_MODEL, NUM_SEARCH, SEARCH_TIME_LIMIT, MAX_CONTENT, MAX_TOKENS
from utils.web_scraper import EnhancedWebScraper
from prompts.system_prompts import system_prompt_search, system_prompt_answer, system_prompt_cited_answer
from prompts.user_prompts import search_prompt, answer_prompt, cited_answer_prompt
from utils.file_handler import save_markdown

client = openai.OpenAI(api_key=OPENAI_API_KEY)

@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def llm_check_search(query, file_path, msg_history=None):
    """
    Checks if the query requires a web search. If yes, uses the enhanced web scraper
    (which applies BM-RAGAM ranking and advanced filtering) to retrieve relevant URLs and content.
    """
    prompt = search_prompt.format(query=query)
    msg_history = msg_history or []
    new_msg_history = msg_history + [{"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system_prompt_search}, *new_msg_history],
        max_tokens=30
    ).choices[0].message.content

    cleaned_response = response.lower().strip()
    if re.fullmatch(r"\bns\b", cleaned_response):
        print("No Google search required.")
        return None
    else:
        print(f"Performing enhanced Google search: {cleaned_response}")
        scraper = EnhancedWebScraper()
        search_dic = scraper.parse_google_results(cleaned_response)
        if search_dic:
            search_result_md = "\n".join([f"{number+1}. {link}" for number, link in enumerate(search_dic.keys())])
            save_markdown(f"## Sources\n{search_result_md}\n\n", file_path)
        else:
            print("No valid search results were found.")
        return search_dic

def chunk_content(content, max_chars=1000):
    """
    Splits the content into chunks of up to `max_chars` while preserving sentence boundaries.
    """
    sentences = sent_tokenize(content)
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        if current_length + len(sentence) > max_chars and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_length = len(sentence)
        else:
            current_chunk.append(sentence)
            current_length += len(sentence)
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks

@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def llm_answer(query, file_path, msg_history=None, search_dic=None):
    """
    Generates an answer using the language model. If external context (search_dic) is provided,
    it chunks the retrieved content and builds a context block with citations before sending
    it to the LLM.
    """
    if search_dic:
        context_blocks = []
        for i, (url, content) in enumerate(search_dic.items()):
            # Ensure we have valid content
            if content:
                chunks = chunk_content(content)
                for chunk in chunks:
                    context_blocks.append(f"[{i+1}]({url}): {chunk}")
        
        context_block = "\n\n".join(context_blocks)
        prompt = cited_answer_prompt.format(context_block=context_block, query=query)
        system_prompt = system_prompt_cited_answer
    else:
        prompt = answer_prompt.format(query=query)
        system_prompt = system_prompt_answer

    msg_history = msg_history or []
    new_msg_history = msg_history + [{"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system_prompt}, *new_msg_history],
        max_tokens=MAX_TOKENS,
        stream=True
    )

    print("\n" + "*" * 20 + " LLM START " + "*" * 20)
    save_markdown(f"## Answer\n", file_path)
    content_list = []
    for chunk in response:
        delta_content = chunk.choices[0].delta.content
        if delta_content:
            content_list.append(delta_content)
            print(delta_content, end="")
            save_markdown(delta_content, file_path)
    
    print("\n" + "*" * 21 + " LLM END " + "*" * 21 + "\n")
    new_msg_history.append({"role": "assistant", "content": ''.join(content_list)})
    
    return new_msg_history
