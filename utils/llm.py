# utils/llm.py

import os
import re
import backoff
import openai

import sys
print(sys.path)

from config import OPENAI_API_KEY, LLM_MODEL, NUM_SEARCH, SEARCH_TIME_LIMIT, MAX_CONTENT, MAX_TOKENS
from utils.web_scraper import parse_google_results
from prompts.system_prompts import system_prompt_search, system_prompt_answer, system_prompt_cited_answer
from prompts.user_prompts import search_prompt, answer_prompt, cited_answer_prompt
from utils.file_handler import save_markdown

client = openai.OpenAI(api_key=OPENAI_API_KEY)

@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def llm_check_search(query, file_path, msg_history=None):
    """Check if query requires search and execute Google search."""
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
        print(f"Performing Google search: {cleaned_response}")
        search_dic = parse_google_results(cleaned_response)
        search_result_md = "\n".join([f"{number+1}. {link}" for number, link in enumerate(search_dic.keys())])
        save_markdown(f"## Sources\n{search_result_md}\n\n", file_path)
        return search_dic

@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def llm_answer(query, file_path, msg_history=None, search_dic=None):
    """Build the prompt for the language model including the search results context."""
    if search_dic:
        context_block = "\n".join([f"[{i+1}]({url}): {content[:MAX_CONTENT]}" for i, (url, content) in enumerate(search_dic.items())])
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
    content = []
    for chunk in response:
        chunk_content = chunk.choices[0].delta.content
        if chunk_content:
            content.append(chunk_content)
            print(chunk_content, end="")
            save_markdown(chunk_content, file_path)
    
    print("\n" + "*" * 21 + " LLM END " + "*" * 21 + "\n")
    new_msg_history = new_msg_history + [{"role": "assistant", "content": ''.join(content)}]

    return new_msg_history