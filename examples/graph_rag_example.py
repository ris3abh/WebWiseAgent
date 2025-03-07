# examples/graph_rag_example.py

import os
import sys
import logging
from datetime import datetime
import openai

# Add parent directory to path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_store import Neo4jGraphStore
from utils.memory_manager import MemoryManager
from utils.temporal_handler import TemporalHandler
from utils.graph_rag import GraphRAG
from utils.retrival import BM_RAGAM
from utils.web_scraper import EnhancedWebScraper
from config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD,
    TEMP_MEMORY_DAYS, PERMANENT_MEMORY_DAYS, MEMORY_REVIEW_INTERVAL,
    OPENAI_API_KEY, LLM_MODEL
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_components():
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
        logger.info("Neo4j connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
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

def process_user_message(components, user_input, project_name="DefaultProject", context=None):
    """
    Process a user message through the graph-based RAG system.
    
    Args:
        components: Dictionary of system components
        user_input: Text input from the user
        project_name: Current project context
        context: Optional previous conversation context
        
    Returns:
        Dictionary with results and graph updates
    """
    memory_manager = components["memory_manager"]
    graph_rag = components["graph_rag"]
    
    # First, process the input to extract entities and relationships
    # and update the knowledge graph
    memory_result = memory_manager.process_user_input(
        user_input=user_input,
        project_name=project_name,
        context=context
    )
    
    # Then, use Graph RAG to retrieve relevant information
    retrieval_result = graph_rag.retrieve(
        query=user_input,
        project_name=project_name,
        cross_project=True
    )
    
    # Add retrieval results to the graph for future reference
    graph_rag.add_retrieval_results_to_graph(
        query=user_input,
        results=retrieval_result["results"],
        project_name=project_name
    )
    
    return {
        "memory_updates": memory_result,
        "retrieval_results": retrieval_result
    }

def simple_demo():
    """Run a simple demonstration of the graph-based RAG system."""
    # Initialize components
    components = initialize_components()
    if not components:
        logger.error("Failed to initialize components")
        return
    
    try:
        # Create a project
        graph_store = components["graph_store"]
        project_id = graph_store.create_project(
            project_name="SampleProject",
            description="A sample project for graph-based RAG demonstration"
        )
        
        # Process a series of user messages
        messages = [
            "I'm working on a Python project that uses RAG for enhanced retrieval",
            "I think Neo4j would be a good choice for storing the knowledge graph",
            "I prefer PyTorch over TensorFlow for machine learning tasks",
            "I'm having trouble with the shutil module in my project"
        ]
        
        context = []
        for msg in messages:
            print(f"\nProcessing message: '{msg}'")
            result = process_user_message(
                components=components,
                user_input=msg,
                project_name="SampleProject",
                context=context
            )
            
            # Update context
            context.append({"role": "user", "content": msg})
            
            # Display results
            print("\nEntities extracted:")
            for entity in result["memory_updates"].get("entities", []):
                print(f"  - {entity['text']}")
                
            print("\nRelationships identified:")
            for rel in result["memory_updates"].get("relationships", []):
                print(f"  - {rel['source']} --[{rel['type']}]--> {rel['target']} (weight: {rel['current_weight']})")
                
            print("\nRetrieved information:")
            for item in result["retrieval_results"].get("results", []):
                print(f"  - {item['content']} (score: {item['score']})")
                
            if result["memory_updates"].get("cross_project_links"):
                print("\nCross-project links created:")
                for link in result["memory_updates"]["cross_project_links"]:
                    print(f"  - {link['entity']} linked between {link['project1']} and {link['project2']}")
            
            print("\n" + "-" * 50)
        
        # Now try a query that should leverage the graph connections
        query = "What issues am I having with my Python project?"
        print(f"\nProcessing query: '{query}'")
        
        result = process_user_message(
            components=components,
            user_input=query,
            project_name="SampleProject",
            context=context
        )
        
        print("\nRetrieved information:")
        for item in result["retrieval_results"].get("results", []):
            print(f"  - {item['content']} (score: {item['score']})")
            if item.get("connected_to"):
                print(f"    Connected to: {item['connected_to']} via {item['relationships']}")
        
    finally:
        # Clean up
        if "temporal_handler" in components:
            components["temporal_handler"].stop_scheduler()
        if "graph_store" in components:
            components["graph_store"].close()
        
        logger.info("Demo completed and resources cleaned up")

if __name__ == "__main__":
    simple_demo()