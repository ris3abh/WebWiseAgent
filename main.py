# main.py

from utils.llm import llm_check_search, llm_answer
from utils.file_handler import save_markdown
from prompts.system_prompts import system_prompt_search, system_prompt_answer, system_prompt_cited_answer
from prompts.user_prompts import search_prompt, answer_prompt, cited_answer_prompt

def main():
    msg_history = None
    file_path = "playground.md"
    save_path = None

    # Start with an empty file
    with open(file_path, 'w') as file:
        pass

    while True:
        query = input("Enter your question: ")
        if query == "q":
            break
        elif query == "s":
            if save_path:
                shutil.copy(file_path, save_path)
                print(f"AI response saved into {save_path}")
                save_path = None
                with open(file_path, 'w') as file:
                    pass
            else:
                print("No content is saved")
                continue
        else:
            save_markdown(f"# {query}\n\n", file_path)
            search_dic = llm_check_search(query, file_path, msg_history)
            msg_history = llm_answer(query, file_path, msg_history, search_dic)
            save_path = save_path or f"{query}.md"
            print(f"AI response recorded into {file_path}")
        print("-" * 51)
        print("Enter a key for [s]ave or [q]uit")

if __name__ == "__main__":
    main()