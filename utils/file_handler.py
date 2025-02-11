# utils/file_handler.py

def save_markdown(content, file_path):
    with open(file_path, 'a') as file:
        file.write(content)