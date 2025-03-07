# utils/temporal_handler.py

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import threading
import time
import schedule

from utils.graph_store import Neo4jGraphStore
from utils.memory_manager import MemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TemporalHandler:
    """
    Manages time-based aspects of memory in the knowledge graph.
    Handles expiration of temporary nodes and periodic review of
    memory classification.
    """
    
    def __init__(self, 
                graph_store: Neo4jGraphStore,
                memory_manager: MemoryManager,
                review_interval_days: int = 7):
        """
        Initialize the temporal handler.
        
        Args:
            graph_store: Neo4j graph store connection
            memory_manager: Memory manager for reclassification
            review_interval_days: Days between memory review cycles
        """
        self.graph_store = graph_store
        self.memory_manager = memory_manager
        self.review_interval_days = review_interval_days
        self.scheduler_thread = None
        self.stop_scheduler = False
        
    def start_scheduler(self):
        """Start the background scheduler for memory management."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            logger.warning("Scheduler already running")
            return
            
        # Schedule daily expiration check
        schedule.every().day.at("03:00").do(self.expire_temporary_memories)
        
        # Schedule periodic memory review
        schedule.every(self.review_interval_days).days.at("04:00").do(self.review_memories)
        
        # Start scheduler in a separate thread
        self.stop_scheduler = False
        self.scheduler_thread = threading.Thread(target=self._run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info(f"Started memory management scheduler (review every {self.review_interval_days} days)")
        
    def stop_scheduler(self):
        """Stop the background scheduler."""
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.stop_scheduler = True
            self.scheduler_thread.join(timeout=5.0)
            logger.info("Stopped memory management scheduler")
        
    def _run_scheduler(self):
        """Run the scheduler in background thread."""
        while not self.stop_scheduler:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
            
    def expire_temporary_memories(self) -> int:
        """
        Check for and remove expired temporary memories.
        
        Returns:
            Number of expired nodes removed
        """
        try:
            deleted_count = self.graph_store.expire_temporary_nodes()
            logger.info(f"Memory expiration check completed: {deleted_count} nodes expired")
            return deleted_count
        except Exception as e:
            logger.error(f"Error during memory expiration: {e}")
            return 0
    
    def review_memories(self) -> Dict[str, int]:
        """
        Review existing memories to potentially reclassify them.
        This may promote temporary memories to permanent or
        adjust relationship weights based on accumulated context.
        
        Returns:
            Statistics about memory modifications
        """
        stats = {
            "reviewed": 0,
            "promoted": 0,
            "demoted": 0,
            "unchanged": 0,
            "errors": 0
        }
        
        try:
            # Get temporary entities approaching expiration
            approaching_expiration = self._get_memories_approaching_expiration()
            stats["reviewed"] = len(approaching_expiration)
            
            if not approaching_expiration:
                logger.info("No memories approaching expiration for review")
                return stats
                
            # Review each entity
            for entity in approaching_expiration:
                try:
                    project_name = self._get_entity_project(entity["id"])
                    if not project_name:
                        logger.warning(f"Could not determine project for entity {entity['id']}")
                        stats["errors"] += 1
                        continue
                        
                    # Get entity's context (relationships and mentions)
                    context = self._get_entity_context(entity["id"])
                    
                    # Make decision about memory promotion/demotion
                    decision = self._evaluate_memory_status(entity, context, project_name)
                    
                    if decision["action"] == "promote":
                        self.graph_store.make_permanent(entity["id"])
                        stats["promoted"] += 1
                        logger.info(f"Promoted entity to permanent memory: {entity['text']} ({entity['id']})")
                    elif decision["action"] == "update_expiration":
                        # Update expiration date
                        self._update_expiration_date(entity["id"], decision["new_expiration_days"])
                        stats["unchanged"] += 1
                    # No explicit demotion logic needed as temporary memories expire naturally
                        
                except Exception as e:
                    logger.error(f"Error reviewing entity {entity.get('id', 'unknown')}: {e}")
                    stats["errors"] += 1
                    
            logger.info(f"Memory review completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error during memory review: {e}")
            stats["errors"] += 1
            return stats
    
    def _get_memories_approaching_expiration(self, days_threshold: int = 7) -> List[Dict]:
        """
        Get temporary memories that are approaching expiration.
        
        Args:
            days_threshold: Number of days before expiration to consider "approaching"
            
        Returns:
            List of entities approaching expiration
        """
        expiration_date = (datetime.now() + timedelta(days=days_threshold)).isoformat()
        
        query = """
        MATCH (e:Entity)
        WHERE e.is_temporary = true 
          AND e.expiration_date <= datetime($expiration_date)
          AND e.expiration_date > datetime()
        RETURN e
        """
        
        result = self.graph_store.query_graph(query, {"expiration_date": expiration_date})
        return [record["e"] for record in result]
    
    def _get_entity_project(self, entity_id: str) -> Optional[str]:
        """Get the project name for an entity."""
        query = """
        MATCH (e {id: $entity_id})-[:BELONGS_TO]->(p:Project)
        RETURN p.name AS project_name
        """
        
        result = self.graph_store.query_graph(query, {"entity_id": entity_id})
        if result and len(result) > 0:
            return result[0].get("project_name")
        return None
    
    def _get_entity_context(self, entity_id: str) -> Dict:
        """
        Get context information for an entity including:
        - Related entities and relationship strengths
        - Number of times mentioned/updated
        - Cross-project references
        
        Returns:
            Dictionary with context information
        """
        # Get relationships
        neighbors = self.graph_store.get_neighbors(entity_id, max_hops=1)
        
        # Get mention history
        query = """
        MATCH (e {id: $entity_id})
        RETURN e.metadata.last_mentioned AS last_mentioned
        """
        
        mention_result = self.graph_store.query_graph(query, {"entity_id": entity_id})
        last_mentioned = None
        if mention_result and len(mention_result) > 0:
            last_mentioned = mention_result[0].get("last_mentioned")
            
        # Get cross-project connections
        query = """
        MATCH (e {id: $entity_id})-[:LINKED_TO]-(other)
        RETURN count(other) AS cross_project_links
        """
        
        links_result = self.graph_store.query_graph(query, {"entity_id": entity_id})
        cross_project_links = 0
        if links_result and len(links_result) > 0:
            cross_project_links = links_result[0].get("cross_project_links", 0)
            
        return {
            "neighbors": neighbors,
            "last_mentioned": last_mentioned,
            "cross_project_links": cross_project_links
        }
    
    def _evaluate_memory_status(self, entity: Dict, context: Dict, project_name: str) -> Dict:
        """
        Evaluate whether a temporary memory should be promoted to permanent.
        
        Args:
            entity: Entity data
            context: Context information from _get_entity_context
            project_name: Name of the project
            
        Returns:
            Decision dictionary with action and metadata
        """
        # Some basic heuristics
        strong_relationships = 0
        for neighbor in context["neighbors"]:
            for rel in neighbor.get("relationships", []):
                # Consider relationships with weight > 0.7 as strong
                if rel.get("weight", 0) > 0.7:
                    strong_relationships += 1
        
        # If entity has strong relationships or cross-project links, promote it
        if strong_relationships >= 2 or context["cross_project_links"] > 0:
            return {
                "action": "promote",
                "reason": f"Entity has {strong_relationships} strong relationships and {context['cross_project_links']} cross-project links"
            }
            
        # For entities with some importance but not enough for promotion,
        # extend their temporary status
        if strong_relationships > 0:
            return {
                "action": "update_expiration",
                "new_expiration_days": 60,  # Extend beyond regular temporary 
                "reason": "Entity has some importance but not enough for promotion"
            }
            
        # Otherwise leave as is
        return {
            "action": "none",
            "reason": "Insufficient importance for promotion or extension"
        }
    
    def _update_expiration_date(self, entity_id: str, days: int) -> bool:
        """Update the expiration date for an entity."""
        expiration_date = (datetime.now() + timedelta(days=days)).isoformat()
        
        query = """
        MATCH (e {id: $entity_id})
        SET e.expiration_date = datetime($expiration_date)
        RETURN e
        """
        
        result = self.graph_store.query_graph(query, {"entity_id": entity_id, "expiration_date": expiration_date})
        return len(result) > 0
        
    def manually_promote_to_permanent(self, entity_id: str) -> bool:
        """
        Manually promote a temporary memory to permanent status.
        
        Args:
            entity_id: ID of the entity to promote
            
        Returns:
            True if promotion was successful
        """
        return self.graph_store.make_permanent(entity_id)