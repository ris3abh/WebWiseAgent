import shutil
import openai
import os

from utils.llm import llm_check_search, llm_answer
from utils.file_handler import save_markdown
from prompts.system_prompts import system_prompt_search, system_prompt_answer, system_prompt_cited_answer
from prompts.user_prompts import search_prompt, answer_prompt, cited_answer_prompt
from utils.web_scraper import EnhancedWebScraper

# Import new graph RAG components
from utils.graph_store import Neo4jGraphStore
from utils.memory_manager import MemoryManager
from utils.temporal_handler import TemporalHandler
from utils.graph_rag import GraphRAG
from utils.retrival import BM_RAGAM

from config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
    TEMP_MEMORY_DAYS, PERMANENT_MEMORY_DAYS, MEMORY_REVIEW_INTERVAL,
    OPENAI_API_KEY, LLM_MODEL
)

def initialize_graph_rag():
    """Initialize all components of the graph-based RAG system."""
    # Initialize OpenAI client
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    # Initialize Neo4j connection
    try:
        graph_store = Neo4jGraphStore(
            uri=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
        print("Neo4j connection established")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return None
    
    # Initialize other components
    memory_manager = MemoryManager(
        graph_store=graph_store,
        openai_client=openai_client,
        temp_memory_days=TEMP_MEMORY_DAYS,
        permanent_memory_days=PERMANENT_MEMORY_DAYS,
        llm_model=LLM_MODEL
    )
    
    temporal_handler = TemporalHandler(
        graph_store=graph_store,
        memory_manager=memory_manager,
        review_interval_days=MEMORY_REVIEW_INTERVAL
    )
    
    bm_ragam = BM_RAGAM()
    
    graph_rag = GraphRAG(
        graph_store=graph_store,
        bm_ragam=bm_ragam
    )
    
    # Start background scheduler for temporal processing
    temporal_handler.start_scheduler()
    
    return {
        "graph_store": graph_store,
        "memory_manager": memory_manager,
        "temporal_handler": temporal_handler,
        "graph_rag": graph_rag,
        "openai_client": openai_client
    }

def main():
    msg_history = None
    file_path = "playground.md"
    save_path = None
    scraper = EnhancedWebScraper()

    # Initialize graph RAG components
    graph_rag_components = initialize_graph_rag()
    if not graph_rag_components:
        print("Warning: Graph RAG initialization failed. Running without graph memory.")
    
    # Current project context
    current_project = os.getenv("CURRENT_PROJECT", "WebWiseAgent")
    
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
        elif query.startswith("project:"):
            # Change current project context
            current_project = query.split(":", 1)[1].strip()
            print(f"Project context changed to: {current_project}")
            continue
        else:
            save_markdown(f"# {query}\n\n", file_path)
            
            # Update knowledge graph with the query
            if graph_rag_components:
                print(f"Processing query with graph memory in project: {current_project}")
                memory_manager = graph_rag_components["memory_manager"]
                memory_result = memory_manager.process_user_input(
                    user_input=query,
                    project_name=current_project,
                    context=msg_history
                )
            
            # Traditional search flow
            search_dic = llm_check_search(query, file_path, msg_history)
            
            # If graph RAG is available, enhance results with graph knowledge
            if graph_rag_components and search_dic:
                graph_rag = graph_rag_components["graph_rag"]
                graph_results = graph_rag.retrieve(
                    query=query,
                    project_name=current_project,
                    cross_project=True
                )
                
                # Add retrieved information from graph to the search results
                for result in graph_results.get("results", []):
                    if result.get("type") == "graph_node" and result.get("content"):
                        # Create a dummy URL for the graph node
                        node_url = f"graph://{current_project}/{result.get('source', 'entity')}"
                        search_dic[node_url] = result.get("content")
            
            # If no search was performed, ensure search_dic is initialized
            search_dic = search_dic or scraper.parse_google_results(query)
            
            # Generate the answer
            msg_history = llm_answer(query, file_path, msg_history, search_dic)
            
            # Store the results in the graph if available
            if graph_rag_components and search_dic:
                graph_rag = graph_rag_components["graph_rag"]
                
                # Convert search_dic to result format expected by add_retrieval_results_to_graph
                results = []
                for url, content in search_dic.items():
                    results.append({
                        "content": content[:500] if content else "",  # Limit content length
                        "source": url,
                        "type": "external" if not url.startswith("graph://") else "graph_node",
                        "score": 0.7  # Default score
                    })
                
                graph_rag.add_retrieval_results_to_graph(
                    query=query,
                    results=results,
                    project_name=current_project
                )
            
            save_path = save_path or f"results/{query}.md"
            print(f"AI response recorded into {file_path}")
        print("-" * 51)
        print("Enter a key for [s]ave or [q]uit")

    # Clean up resources
    if graph_rag_components:
        if "temporal_handler" in graph_rag_components:
            graph_rag_components["temporal_handler"].stop_scheduler()
        if "graph_store" in graph_rag_components:
            graph_rag_components["graph_store"].close()
        print("Graph RAG resources cleaned up")

if __name__ == "__main__":
    main()