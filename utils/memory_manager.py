# utils/memory_manager.py

import os
import logging
import json
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime, timedelta
import openai
import re

from utils.graph_store import Neo4jGraphStore

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MemoryManager:
    """
    LLM-based memory classification and management system.
    Handles entity extraction, relationship identification, and 
    temporary/permanent memory decisions.
    """
    
    def __init__(self, 
                graph_store: Neo4jGraphStore, 
                openai_client, 
                temp_memory_days: int = 30,
                permanent_memory_days: int = 90,
                llm_model: str = "gpt-4o"):
        """
        Initialize the memory manager.
        
        Args:
            graph_store: Neo4j graph store connection
            openai_client: OpenAI client for LLM access
            temp_memory_days: Days to retain temporary memories
            permanent_memory_days: Days to retain permanent memories
            llm_model: LLM model to use for memory decisions
        """
        self.graph_store = graph_store
        self.openai_client = openai_client
        self.temp_memory_days = temp_memory_days
        self.permanent_memory_days = permanent_memory_days
        self.llm_model = llm_model
        
    def process_user_input(self, 
                         user_input: str, 
                         project_name: str,
                         context: Optional[List[Dict]] = None) -> Dict:
        """
        Process user input to extract entities and relationships
        and update the knowledge graph.
        
        Args:
            user_input: Text input from the user
            project_name: Current project context
            context: Optional previous conversation context
            
        Returns:
            Dictionary with extracted information and graph updates
        """
        # First, ensure the project exists
        project_id = self.graph_store.create_project(project_name)
        if not project_id:
            logger.error(f"Failed to create/find project: {project_name}")
            return {"error": f"Failed to process project: {project_name}"}
            
        # Extract entities and relationships
        entities, relationships = self._extract_entities_and_relationships(user_input, context)
        
        # Decide memory classification for each entity and relationship
        classified_entities = self._classify_memory_importance(entities, user_input, project_name)
        
        # Add entities to the graph
        entity_ids = {}
        for entity in classified_entities:
            entity_id = self.graph_store.add_entity(
                entity_text=entity["text"],
                entity_type=entity["type"],
                project_name=project_name,
                metadata=entity.get("metadata", {}),
                is_temporary=entity["is_temporary"],
                expiration_days=entity["expiration_days"]
            )
            if entity_id:
                entity_ids[entity["text"]] = entity_id
        
        # Process relationships between entities
        relationship_results = []
        for rel in relationships:
            source_text = rel["source"]
            target_text = rel["target"]
            
            # Skip if source or target entity wasn't successfully added
            if source_text not in entity_ids or target_text not in entity_ids:
                logger.warning(f"Skipping relationship {source_text} -> {target_text}: Entity not found")
                continue
                
            # Determine if this is a new relationship or update to existing one
            is_new = self._is_new_relationship(entity_ids[source_text], entity_ids[target_text], rel["type"])
            
            # If updating, get previous weight to compare
            previous_weight = None
            if not is_new:
                previous_weight = self._get_relationship_weight(
                    entity_ids[source_text], entity_ids[target_text], rel["type"]
                )
            
            # Add/update the relationship
            relationship_id = self.graph_store.create_relationship(
                source_id=entity_ids[source_text],
                target_id=entity_ids[target_text],
                relation_type=rel["type"],
                weight=rel["weight"],
                metadata=rel.get("metadata", {}),
                is_temporary=rel["is_temporary"],
                expiration_days=rel["expiration_days"]
            )
            
            if relationship_id:
                relationship_results.append({
                    "id": relationship_id,
                    "source": source_text,
                    "target": target_text,
                    "type": rel["type"],
                    "is_new": is_new,
                    "previous_weight": previous_weight,
                    "current_weight": rel["weight"]
                })
        
        # Check for cross-project linkages
        cross_project_links = self._find_cross_project_links(classified_entities)
        
        return {
            "project_id": project_id,
            "entities": [{"text": e["text"], "id": entity_ids.get(e["text"])} for e in classified_entities],
            "relationships": relationship_results,
            "cross_project_links": cross_project_links
        }
    
    def _extract_entities_and_relationships(self, 
                                         text: str, 
                                         context: Optional[List[Dict]] = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Use LLM to extract entities and relationships from text.
        
        Args:
            text: Input text to analyze
            context: Optional conversation context
            
        Returns:
            Tuple of (entities, relationships)
        """
        # Build prompt for entity and relationship extraction
        system_prompt = """
        You are an AI assistant specialized in knowledge graph construction.
        Extract entities and relationships from the user's text.
        
        For each entity, identify:
        1. The entity text (exact text from input)
        2. The entity type (Person, Organization, Concept, Technology, etc.)
        
        For each relationship, identify:
        1. The source entity (must be one of the extracted entities)
        2. The target entity (must be one of the extracted entities) 
        3. The relationship type (e.g., LIKES, DISLIKES, USES, WORKS_AT)
        4. A weight (0.0 to 1.0) indicating strength of the relationship
        
        Return your answer as a JSON object with two lists: "entities" and "relationships".
        """
        
        context_text = ""
        if context:
            # Format the context for the prompt
            context_messages = []
            for msg in context[-5:]:  # Only use last 5 messages for context
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context_messages.append(f"{role}: {content}")
            
            context_text = "Previous conversation context:\n" + "\n".join(context_messages) + "\n\n"
        
        user_prompt = f"{context_text}Extract entities and relationships from this text: {text}"
        
        # Call OpenAI API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.openai_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        
        # Extract JSON from response
        try:
            # First try to parse the entire response as JSON
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON using regex
            json_match = re.search(r'```json\n(.*?)\n```', result_text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON from LLM response: {result_text}")
                    return [], []
            else:
                logger.error(f"Failed to extract JSON from LLM response: {result_text}")
                return [], []
        
        # Extract entities and relationships
        entities = result.get("entities", [])
        relationships = result.get("relationships", [])
        
        return entities, relationships
    
    def _is_new_relationship(self, source_id: str, target_id: str, relation_type: str) -> bool:
        """Check if a relationship between two entities already exists."""
        query = f"""
        MATCH (source {{id: $source_id}})-[r:{relation_type}]->(target {{id: $target_id}})
        RETURN r
        """
        
        result = self.graph_store.query_graph(query, {"source_id": source_id, "target_id": target_id})
        return len(result) == 0
    
    def _get_relationship_weight(self, source_id: str, target_id: str, relation_type: str) -> Optional[float]:
        """Get the current weight of a relationship if it exists."""
        query = f"""
        MATCH (source {{id: $source_id}})-[r:{relation_type}]->(target {{id: $target_id}})
        RETURN r.weight AS weight
        """
        
        result = self.graph_store.query_graph(query, {"source_id": source_id, "target_id": target_id})
        if result and len(result) > 0:
            return result[0].get("weight")
        return None
    
    def _find_cross_project_links(self, entities: List[Dict]) -> List[Dict]:
        """Find potential links between entities across different projects."""
        cross_project_links = []
        
        for entity in entities:
            try:
                # For each entity, check if it exists in other projects
                entity_links = self.graph_store.get_entity_links_across_projects(entity["text"])
                
                if len(entity_links) > 1:  # Entity exists in multiple projects
                    for i in range(len(entity_links)):
                        for j in range(i + 1, len(entity_links)):
                            try:
                                # Create link between entity instances in different projects
                                entity1 = entity_links[i]["entity"]
                                entity2 = entity_links[j]["entity"]
                                project1 = entity_links[i]["project"]
                                project2 = entity_links[j]["project"]
                                
                                link_id = self.graph_store.create_cross_project_link(
                                    entity1_id=entity1["id"],
                                    entity2_id=entity2["id"]
                                )
                                
                                if link_id:
                                    cross_project_links.append({
                                        "link_id": link_id,
                                        "entity": entity["text"],
                                        "project1": project1,
                                        "project2": project2
                                    })
                            except Exception as e:
                                logger.error(f"Error creating cross-project link: {e}")
            except Exception as e:
                logger.error(f"Error processing entity for cross-project links: {e}")
        
        return cross_project_links
    
    def _classify_memory_importance(self, 
                                  entities: List[Dict], 
                                  context: str,
                                  project_name: str) -> List[Dict]:
        """
        Use LLM to classify entities as temporary or permanent memory.
        
        Args:
            entities: List of extracted entities
            context: Text context where entities were mentioned
            project_name: Current project context
            
        Returns:
            Entities with memory classification added
        """
        if not entities:
            return []
            
        # Build prompt for memory classification
        system_prompt = f"""
        You are an AI assistant specialized in knowledge management.
        For each entity, determine if it should be stored as temporary memory (expires in {self.temp_memory_days} days)
        or permanent memory (expires in {self.permanent_memory_days} days).
        
        Consider:
        1. Importance to the user based on context
        2. Significance within project "{project_name}"
        3. Likely future relevance
        
        Return your answer as a JSON object with a list of entities, each with:
        1. text: The original entity text
        2. type: The entity type
        3. is_temporary: Boolean indicating if this is temporary (true) or permanent (false)
        4. expiration_days: Number of days until expiration ({self.temp_memory_days} or {self.permanent_memory_days})
        5. confidence: Value from 0.0 to 1.0 indicating confidence in this memory classification
        6. reasoning: Brief explanation of why this classification was chosen
        """
        
        # Create JSON representation of entities
        entities_json = json.dumps(entities, indent=2)
        
        user_prompt = f"""
        Context in which entities were mentioned:
        "{context}"
        
        Project name: {project_name}
        
        Entities to classify:
        {entities_json}
        
        Classify each entity as temporary or permanent memory.
        """
        
        # Call OpenAI API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.openai_client.chat.completions.create(
            model=self.llm_model,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        result_text = response.choices[0].message.content
        
        # Extract JSON from response
        try:
            result = json.loads(result_text)
            classified_entities = result.get("entities", [])
            
            # Ensure each entity has the required fields
            for entity in classified_entities:
                if "is_temporary" not in entity:
                    entity["is_temporary"] = True
                if "expiration_days" not in entity:
                    entity["expiration_days"] = self.temp_memory_days if entity["is_temporary"] else self.permanent_memory_days
                
                # Create metadata from additional information
                entity["metadata"] = {
                    "confidence": entity.get("confidence", 0.7),
                    "reasoning": entity.get("reasoning", ""),
                    "last_mentioned": datetime.now().isoformat()
                }
            
            return classified_entities
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse memory classification result: {e}")
            
            # Fallback: Just use default temporary classification
            for entity in entities:
                entity["is_temporary"] = True
                entity["expiration_days"] = self.temp_memory_days
                entity["metadata"] = {
                    "confidence": 0.5,
                    "reasoning": "Default temporary classification due to processing error",
                    "last_mentioned": datetime.now().isoformat()
                }
            
            return entities