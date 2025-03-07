# utils/graph_rag.py

import logging
import json
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np
from datetime import datetime

from utils.graph_store import Neo4jGraphStore
from utils.retrival import BM_RAGAM, VectorizedKnowledgeBase

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphRAG:
    """
    Graph-based Retrieval Augmented Generation system.
    Integrates traditional BM_RAGAM retrieval with knowledge graph traversal
    for enhanced context understanding.
    """
    
    def __init__(self, graph_store: Neo4jGraphStore, bm_ragam: BM_RAGAM = None):
        """
        Initialize the Graph RAG system.
        
        Args:
            graph_store: Neo4j graph store connection
            bm_ragam: Optional existing BM_RAGAM instance
        """
        self.graph_store = graph_store
        self.bm_ragam = bm_ragam or BM_RAGAM()
        
    def retrieve(self, 
                query: str, 
                project_name: Optional[str] = None,
                cross_project: bool = True,
                top_k: int = 5,
                hop_limit: int = 2) -> Dict:
        """
        Retrieve relevant information using both BM_RAGAM and graph traversal.
        
        Args:
            query: User query
            project_name: Optional project name for context
            cross_project: Whether to consider cross-project connections
            top_k: Number of top results to return
            hop_limit: Maximum number of hops for graph traversal
            
        Returns:
            Dictionary with retrieved information
        """
        # Step 1: Extract key entities from the query
        query_entities = self._extract_query_entities(query)
        
        # Step 2: Find relevant entities in the graph
        entity_matches = self._find_matching_entities(query_entities, project_name)
        
        # Step 3: Use BM_RAGAM to rank external sources and documents
        bm_ragam_results = self._rank_external_sources(query)
        
        # Step 4: Traverse graph to find related information
        graph_results = self._traverse_graph(entity_matches, hop_limit)
        
        # Step 5: If cross-project is enabled, expand to related projects
        if cross_project and project_name:
            cross_project_results = self._find_cross_project_information(entity_matches)
        else:
            cross_project_results = []
            
        # Step 6: Combine and rank all results
        combined_results = self._combine_and_rank_results(
            query,
            bm_ragam_results,
            graph_results,
            cross_project_results,
            top_k
        )
        
        return {
            "query": query,
            "project": project_name,
            "results": combined_results,
            "metadata": {
                "external_sources": len(bm_ragam_results),
                "graph_entities": len(entity_matches),
                "graph_traversal_results": len(graph_results),
                "cross_project_results": len(cross_project_results),
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _extract_query_entities(self, query: str) -> List[str]:
        """
        Extract potential entity terms from the query.
        This is a simplified implementation - a production system
        would use NER or other ML techniques.
        
        Args:
            query: The user query
            
        Returns:
            List of potential entity terms
        """
        # Simple approach: split by common separators and filter by length
        tokens = query.replace('.', ' ').replace(',', ' ').replace('?', ' ').split()
        
        # Filter tokens that might be entities (e.g., capitalized or longer words)
        potential_entities = []
        
        # Single tokens
        for token in tokens:
            if len(token) > 3 or token[0].isupper():
                potential_entities.append(token)
                
        # Also consider bigrams for multi-word entities
        if len(tokens) > 1:
            for i in range(len(tokens) - 1):
                bigram = f"{tokens[i]} {tokens[i+1]}"
                if len(bigram) > 5:  # Longer bigrams are more likely to be entities
                    potential_entities.append(bigram)
                    
        return potential_entities
    
    def _find_matching_entities(self, 
                              query_entities: List[str], 
                              project_name: Optional[str] = None) -> List[Dict]:
        """
        Find entities in the graph that match the query entities.
        
        Args:
            query_entities: List of entity terms from the query
            project_name: Optional project to search within
            
        Returns:
            List of matching entity nodes
        """
        matching_entities = []
        
        for entity_text in query_entities:
            # Find entities with similar text
            entities = self.graph_store.find_entities_by_text(entity_text, project_name)
            matching_entities.extend(entities)
            
        # Remove duplicates based on entity ID
        unique_entities = {}
        for entity in matching_entities:
            entity_id = entity.get("id")
            if entity_id:
                unique_entities[entity_id] = entity
                
        return list(unique_entities.values())
    
    def _rank_external_sources(self, query: str) -> List[Dict]:
        """
        Use BM_RAGAM to rank external sources relevant to the query.
        This integrates with the existing retrieval functionality.
        
        Args:
            query: User query
            
        Returns:
            List of ranked external documents/sources
        """
        # This is a placeholder for integration with your existing BM_RAGAM
        # In a full implementation, this would call into your web scraper and retrieval system
        
        # For now, return an empty list as we're focusing on graph-based retrieval
        return []
    
    def _traverse_graph(self, 
                       seed_entities: List[Dict], 
                       max_hops: int = 2) -> List[Dict]:
        """
        Traverse the graph starting from seed entities to find relevant information.
        
        Args:
            seed_entities: Starting entity nodes
            max_hops: Maximum traversal depth
            
        Returns:
            List of related nodes with relationship context
        """
        if not seed_entities:
            return []
            
        traversal_results = []
        
        for entity in seed_entities:
            entity_id = entity.get("id")
            if not entity_id:
                continue
                
            # Get neighbors within hop limit
            neighbors = self.graph_store.get_neighbors(
                entity_id=entity_id, 
                max_hops=max_hops
            )
            
            # Add traversal path information
            for neighbor in neighbors:
                neighbor["source_entity"] = entity
                traversal_results.append(neighbor)
                
        return traversal_results
    
    def _find_cross_project_information(self, entity_matches: List[Dict]) -> List[Dict]:
        """
        Find information from other projects related to the matching entities.
        
        Args:
            entity_matches: Entities matched in the current context
            
        Returns:
            List of related information from other projects
        """
        cross_project_results = []
        
        for entity in entity_matches:
            entity_text = entity.get("text")
            if not entity_text:
                continue
                
            # Find same entity in other projects
            cross_links = self.graph_store.get_entity_links_across_projects(entity_text)
            
            for link in cross_links:
                # Skip if this is the original entity
                if link["entity"].get("id") == entity.get("id"):
                    continue
                    
                # Add to cross-project results
                cross_project_results.append({
                    "source_entity": entity,
                    "linked_entity": link["entity"],
                    "project": link["project"],
                    "relationship_type": "CROSS_PROJECT"
                })
                
        return cross_project_results
    
    def _combine_and_rank_results(self,
                                query: str,
                                bm_ragam_results: List[Dict],
                                graph_results: List[Dict],
                                cross_project_results: List[Dict],
                                top_k: int = 5) -> List[Dict]:
        """
        Combine and rank results from different retrieval methods.
        
        Args:
            query: Original user query
            bm_ragam_results: Results from traditional BM_RAGAM
            graph_results: Results from graph traversal
            cross_project_results: Results from cross-project links
            top_k: Number of top results to return
            
        Returns:
            List of ranked results
        """
        # Combine all results
        all_results = []
        
        # Add BM_RAGAM results
        for i, result in enumerate(bm_ragam_results):
            all_results.append({
                "content": result.get("content", ""),
                "source": result.get("url", "Unknown"),
                "type": "external",
                "score": result.get("score", 0.5),
                "rank": i + 1
            })
            
        # Add graph traversal results
        for i, result in enumerate(graph_results):
            node = result.get("node", {})
            source_entity = result.get("source_entity", {})
            relationships = result.get("relationships", [])
            
            # Calculate a relevance score based on relationship weights
            rel_weights = [r.get("weight", 0.5) for r in relationships]
            avg_weight = sum(rel_weights) / len(rel_weights) if rel_weights else 0.5
            
            all_results.append({
                "content": node.get("text", ""),
                "source": f"Entity: {node.get('type', 'Unknown')}",
                "type": "graph_node",
                "score": avg_weight,
                "connected_to": source_entity.get("text", ""),
                "relationships": [r.get("type", "RELATED") for r in relationships],
                "rank": i + 1
            })
            
        # Add cross-project results
        for i, result in enumerate(cross_project_results):
            linked_entity = result.get("linked_entity", {})
            source_entity = result.get("source_entity", {})
            project = result.get("project", "Unknown")
            
            all_results.append({
                "content": linked_entity.get("text", ""),
                "source": f"Project: {project}",
                "type": "cross_project",
                "score": 0.8,  # Cross-project links are highly relevant
                "connected_to": source_entity.get("text", ""),
                "relationships": ["CROSS_PROJECT"],
                "rank": i + 1
            })
            
        # Sort by score (descending)
        sorted_results = sorted(all_results, key=lambda x: x.get("score", 0), reverse=True)
        
        # Take top k results
        return sorted_results[:top_k]
    
    def add_retrieval_results_to_graph(self, 
                                     query: str,
                                     results: List[Dict],
                                     project_name: str) -> Dict:
        """
        Add retrieval results to the knowledge graph for future reference.
        
        Args:
            query: The original query
            results: Retrieved results to add to the graph
            project_name: Project context
            
        Returns:
            Dictionary with operation statistics
        """
        stats = {
            "entities_added": 0,
            "relationships_added": 0,
            "errors": 0
        }
        
        try:
            # Create a query entity
            query_id = self.graph_store.add_entity(
                entity_text=query,
                entity_type="Query",
                project_name=project_name,
                is_temporary=True,
                expiration_days=30
            )
            
            if query_id:
                stats["entities_added"] += 1
                
                # Add each result as an entity and link to the query
                for result in results:
                    content = result.get("content", "")
                    source = result.get("source", "Unknown")
                    result_type = result.get("type", "unknown")
                    
                    # Skip if no content
                    if not content:
                        continue
                        
                    # Add result as entity
                    result_id = self.graph_store.add_entity(
                        entity_text=content[:100],  # Limit to first 100 chars
                        entity_type=f"Result_{result_type}",
                        project_name=project_name,
                        metadata={
                            "source": source,
                            "full_content": content,
                            "result_type": result_type
                        },
                        is_temporary=True,
                        expiration_days=15  # Results expire faster than queries
                    )
                    
                    if result_id:
                        stats["entities_added"] += 1
                        
                        # Link result to query
                        rel_id = self.graph_store.create_relationship(
                            source_id=query_id,
                            target_id=result_id,
                            relation_type="HAS_RESULT",
                            weight=result.get("score", 0.5),
                            is_temporary=True,
                            expiration_days=15
                        )
                        
                        if rel_id:
                            stats["relationships_added"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        stats["errors"] += 1
            else:
                stats["errors"] += 1
                
            return stats
                
        except Exception as e:
            logger.error(f"Error adding retrieval results to graph: {e}")
            stats["errors"] += 1
            return stats