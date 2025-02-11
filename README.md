## Project Overview
This project aims to create an intelligent personal assistant capable of handling various tasks typically performed on a laptop. It leverages the power of AI, specifically utilizing a customizable agent similar to Perplexity, to provide users with a seamless and efficient experience. The agent can perform tasks such as document reading and writing, and it can be extended with advanced features like Retrieval-Augmented Generation (RAG) to enhance its capabilities.

## Features
- **Google Search Integration**: The agent can decide whether a user's query requires a Google search and perform the search if necessary.
- **Customizable Responses**: The agent is designed to provide informative and relevant responses based on user queries.
- **Document Handling**: The agent can read and write documents, making it a versatile tool for various tasks.
- **Retrieval-Augmented Generation (RAG)**: The agent can be extended with RAG to enhance its response generation capabilities by combining information retrieval and language generation.

## Getting Started

### Prerequisites
- Python 3.12 or higher
- OpenAI API key
- Required libraries (install using `pip install -r requirements.txt`)

### Installation
1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/WebWiseAgent.git
   cd WebWiseAgent
   ```

2. Create a virtual environment (optional but recommended):

    ```bash
    python3.12 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

4. Set the OpenAI API key:

    ```bash
    export OPENAI_API_KEY=your_openai_api_key  # On Windows use `set OPENAI_API_KEY=your_openai_api_key`
    ```

### Running the Project

To run the project, execute the following command:

    ```bash
    python main.py
    ```

## Future Scope

### 1. Agentic Workflow
The ultimate goal is to create an agentic workflow that can handle a wide range of tasks, such as task management, document handling, writing code and more. This workflow will be orchestrated using tools like LangGraph, LangChain, smol agents and others enabling the agent to interact seamlessly with various systems and provide a unified user experience.
### 2. RAG Implementation
To enhance the agent's capabilities, RAG will be implemented to combine information retrieval with language generation. This will allow the agent to provide more accurate and contextually relevant responses by leveraging a combination of retrieved information and generative AI.
### 3. Document Reading and Writing
The agent will be extended to read and write documents, making it a versatile tool for various tasks. This feature will be particularly useful for tasks such as summarizing documents, extracting key information, and generating reports.

### 4. Customizability
The agent will be highly customizable, allowing users to tailor its behavior and capabilities to their specific needs. This includes the ability to add custom tools, integrate with other systems, and configure the agent's responses.

## Conclusion
This project represents the first step towards creating a highly customizable and intelligent personal assistant. By leveraging advanced AI techniques and tools, the agent will be capable of handling a wide range of tasks and providing a seamless user experience. Future work will focus on enhancing the agent's capabilities through features like RAG implementation and document handling, ultimately leading to a more powerful and versatile personal assistant.