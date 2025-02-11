# prompts/user_prompts.py

search_prompt = """
Decide if a user's query requires a Google search. You should use Google search for most queries to find the most accurate and updated information. Follow these conditions:

- If the query does not require Google search, you must output "ns", short for no search.
- If the query requires Google search, you must respond with a reformulated user query for Google search.
- User query may sometimes refer to previous messages. Make sure your Google search considers the entire message history.

User Query:
{query}
"""

answer_prompt = """Generate a response that is informative and relevant to the user's query
User Query:
{query}
"""

cited_answer_prompt = """
Provide a relevant, informative response to the user's query using the given context (search results with [citation number](website link) and brief descriptions).

- Answer directly without referring the user to any external links.
- Use an unbiased, journalistic tone and avoid repeating text.
- Format your response in markdown with bullet points for clarity.
- Cite all information using [citation number](website link) notation, matching each part of your answer to its source.

Context Block:
{context_block}

User Query:
{query}
"""