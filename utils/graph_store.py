# utils/graph_store.py

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set

from neo4j.exceptions import Neo4jError
from neo4j import GraphDatabase, Driver, Session, TRUST_SYSTEM_CA_SIGNED_CERTIFICATES


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Neo4jGraphStore:
    """Interface for storing and retrieving knowledge graph data in Neo4j."""
    

    def __init__(self, uri: str, username: str, password: str):
        """Initialize Neo4j connection."""
        # Handle different connection protocols
        if uri.startswith("neo4j+s://"):
            self.driver = GraphDatabase.driver(
                uri, 
                auth=(username, password),
                encrypted=True,
                trust=TRUST_SYSTEM_CA_SIGNED_CERTIFICATES
            )
        else:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
        
        self._verify_connection()
        self._setup_constraints()
        logger.info("Neo4j connection established successfully")
        
    def _verify_connection(self):
        """Verify that we can connect to Neo4j."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            logger.info("Neo4j connection verified")
        except Neo4jError as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
            
    def _setup_constraints(self):
        """Set up necessary constraints in Neo4j."""
        queries = [
            # Ensure nodes have unique IDs
            "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Node) REQUIRE n.id IS UNIQUE",
            # Ensure projects have unique names
            "CREATE CONSTRAINT project_name IF NOT EXISTS FOR (p:Project) REQUIRE p.name IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for query in queries:
                try:
                    session.run(query)
                except Neo4jError as e:
                    # If constraint already exists or other error
                    logger.warning(f"Constraint setup warning: {e}")
    
    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()
        logger.info("Neo4j connection closed")
        
    def create_project(self, project_name: str, description: Optional[str] = None) -> str:
        """
        Create a new project node in the graph.
        
        Args:
            project_name: Unique name for the project
            description: Optional description of the project
            
        Returns:
            project_id: Unique identifier for the created project
        """
        query = """
        MERGE (p:Project {name: $name})
        ON CREATE SET 
            p.id = randomUUID(),
            p.description = $description,
            p.created_at = datetime(),
            p.updated_at = datetime()
        ON MATCH SET 
            p.updated_at = datetime(),
            p.description = CASE WHEN $description IS NOT NULL THEN $description ELSE p.description END
        RETURN p.id as project_id
        """
        
        with self.driver.session() as session:
            result = session.run(query, name=project_name, description=description)
            record = result.single()
            if record:
                return record["project_id"]
            else:
                logger.error(f"Failed to create project: {project_name}")
                return None
    
    def add_entity(self, 
                  entity_text: str, 
                  entity_type: str, 
                  project_name: str,
                  metadata: Optional[Dict[str, Any]] = None,
                  is_temporary: bool = True,
                  expiration_days: int = 30) -> str:
        """
        Add an entity node to the graph.
        
        Args:
            entity_text: The text content of the entity
            entity_type: Type of the entity (Person, Organization, Concept, etc.)
            project_name: Name of the project this entity belongs to
            metadata: Additional metadata about the entity
            is_temporary: Whether this is temporary memory
            expiration_days: Days until this entity expires (if temporary)
            
        Returns:
            entity_id: Unique identifier for the created entity
        """
        # Calculate expiration date if temporary
        expiration_date = None
        if is_temporary:
            expiration_date = (datetime.now() + timedelta(days=expiration_days)).isoformat()
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
        
        query = """
        MATCH (p:Project {name: $project_name})
        MERGE (e:Entity {text: $entity_text, type: $entity_type})
        ON CREATE SET 
            e.id = randomUUID(),
            e.created_at = datetime(),
            e.updated_at = datetime(),
            e.metadata = $metadata,
            e.is_temporary = $is_temporary,
            e.expiration_date = $expiration_date
        ON MATCH SET 
            e.updated_at = datetime(),
            e.metadata = CASE WHEN $metadata = {} THEN e.metadata ELSE $metadata END,
            e.is_temporary = $is_temporary,
            e.expiration_date = $expiration_date
        
        MERGE (e)-[:BELONGS_TO]->(p)
        
        RETURN e.id as entity_id
        """
        
        with self.driver.session() as session:
            result = session.run(
                query, 
                entity_text=entity_text,
                entity_type=entity_type,
                project_name=project_name,
                metadata=metadata,
                is_temporary=is_temporary,
                expiration_date=expiration_date
            )
            record = result.single()
            if record:
                return record["entity_id"]
            else:
                logger.error(f"Failed to add entity: {entity_text}")
                return None
    
    def create_relationship(self,
                           source_id: str,
                           target_id: str,
                           relation_type: str,
                           weight: float = 1.0,
                           metadata: Optional[Dict[str, Any]] = None,
                           is_temporary: bool = True,
                           expiration_days: int = 30) -> str:
        """
        Create a relationship between two nodes.
        
        Args:
            source_id: ID of the source node
            target_id: ID of the target node
            relation_type: Type of relationship (e.g., KNOWS, LIKES, CREATED)
            weight: Strength of relationship (0.0 to 1.0)
            metadata: Additional metadata about the relationship
            is_temporary: Whether this is temporary memory
            expiration_days: Days until this relationship expires (if temporary)
            
        Returns:
            relationship_id: Unique identifier for the created relationship
        """
        # Calculate expiration date if temporary
        expiration_date = None
        if is_temporary:
            expiration_date = (datetime.now() + timedelta(days=expiration_days)).isoformat()
        
        # Prepare metadata
        if metadata is None:
            metadata = {}
            
        # Uppercase and format the relation type for Neo4j
        relation_type = relation_type.upper().replace(" ", "_")
        
        query = f"""
        MATCH (source {{id: $source_id}})
        MATCH (target {{id: $target_id}})
        MERGE (source)-[r:{relation_type}]->(target)
        ON CREATE SET 
            r.id = randomUUID(),
            r.created_at = datetime(),
            r.updated_at = datetime(),
            r.weight = $weight,
            r.metadata = $metadata,
            r.is_temporary = $is_temporary,
            r.expiration_date = $expiration_date
        ON MATCH SET 
            r.updated_at = datetime(),
            r.weight = $weight,
            r.metadata = CASE WHEN $metadata = {{}} THEN r.metadata ELSE $metadata END,
            r.is_temporary = $is_temporary,
            r.expiration_date = $expiration_date
        RETURN r.id as relationship_id
        """
        
        with self.driver.session() as session:
            result = session.run(
                query, 
                source_id=source_id,
                target_id=target_id,
                weight=weight,
                metadata=metadata,
                is_temporary=is_temporary,
                expiration_date=expiration_date
            )
            record = result.single()
            if record:
                return record["relationship_id"]
            else:
                logger.error(f"Failed to create relationship between {source_id} and {target_id}")
                return None
    
    def find_entities_by_text(self, text: str, project_name: Optional[str] = None) -> List[Dict]:
        """
        Find entities by matching text.
        
        Args:
            text: Text to search for
            project_name: Optional project name to limit search scope
            
        Returns:
            List of matching entity dictionaries
        """
        if project_name:
            query = """
            MATCH (e:Entity)-[:BELONGS_TO]->(p:Project {name: $project_name})
            WHERE e.text CONTAINS $text
            RETURN e
            """
            params = {"text": text, "project_name": project_name}
        else:
            query = """
            MATCH (e:Entity)
            WHERE e.text CONTAINS $text
            RETURN e
            """
            params = {"text": text}
            
        with self.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record["e"]) for record in result]
    
    def get_entity_by_id(self, entity_id: str) -> Dict:
        """Get entity by ID."""
        query = """
        MATCH (e {id: $id})
        RETURN e
        """
        
        with self.driver.session() as session:
            result = session.run(query, id=entity_id)
            record = result.single()
            if record:
                return dict(record["e"])
            else:
                return None
    
    def query_graph(self, cypher_query: str, params: Dict = None) -> List[Dict]:
        """
        Execute a custom Cypher query.
        
        Args:
            cypher_query: Cypher query string
            params: Query parameters
            
        Returns:
            Query results as a list of dictionaries
        """
        if params is None:
            params = {}
            
        with self.driver.session() as session:
            result = session.run(cypher_query, **params)
            return [record.data() for record in result]
    
    def get_neighbors(self, entity_id: str, relation_types: Optional[List[str]] = None, 
                    direction: str = "both", max_hops: int = 1) -> List[Dict]:
        """
        Get neighboring nodes of an entity.
        
        Args:
            entity_id: ID of the entity
            relation_types: Optional list of relationship types to filter by
            direction: Direction of relationship ("outgoing", "incoming", or "both")
            max_hops: Maximum number of hops to traverse
            
        Returns:
            List of neighboring nodes with their relationships
        """
        # Prepare relationship type filter
        rel_filter = ""
        if relation_types:
            formatted_types = [f":{rel_type}" for rel_type in relation_types]
            rel_filter = "|".join(formatted_types)
            rel_filter = f"[{rel_filter}]"
        
        # Prepare direction
        if direction == "outgoing":
            pattern = f"(n)-[r{rel_filter}*1..{max_hops}]->(m)"
        elif direction == "incoming":
            pattern = f"(n)<-[r{rel_filter}*1..{max_hops}]-(m)"
        else:  # both
            pattern = f"(n)-[r{rel_filter}*1..{max_hops}]-(m)"
        
        query = f"""
        MATCH (n {{id: $entity_id}})
        MATCH {pattern}
        RETURN m as neighbor, r as relationships
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity_id=entity_id)
            neighbors = []
            for record in result:
                neighbor = dict(record["neighbor"])
                relationships = [dict(rel) for rel in record["relationships"]]
                neighbors.append({
                    "node": neighbor,
                    "relationships": relationships
                })
            return neighbors
    
    def expire_temporary_nodes(self):
        """Remove temporary nodes that have expired."""
        query = """
        MATCH (n)
        WHERE n.is_temporary = true 
          AND n.expiration_date < datetime()
        DETACH DELETE n
        RETURN count(n) as deleted_count
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            record = result.single()
            if record:
                logger.info(f"Expired and deleted {record['deleted_count']} temporary nodes")
                return record["deleted_count"]
            return 0
            
    def make_permanent(self, entity_id: str) -> bool:
        """Convert a temporary node to permanent."""
        query = """
        MATCH (n {id: $entity_id})
        SET n.is_temporary = false, n.expiration_date = null
        RETURN n
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity_id=entity_id)
            return result.single() is not None

    def get_project_entities(self, project_name: str) -> List[Dict]:
        """Get all entities for a specific project."""
        query = """
        MATCH (e:Entity)-[:BELONGS_TO]->(p:Project {name: $project_name})
        RETURN e
        """
        
        with self.driver.session() as session:
            result = session.run(query, project_name=project_name)
            return [dict(record["e"]) for record in result]
            
    def get_entity_links_across_projects(self, entity_text: str) -> List[Dict]:
        """Find connections of an entity across different projects."""
        query = """
        MATCH (e:Entity {text: $entity_text})-[:BELONGS_TO]->(p:Project)
        RETURN e, p.name as project_name
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity_text=entity_text)
            return [{"entity": dict(record["e"]), "project": record["project_name"]} 
                   for record in result]
                   
    def suggest_cross_project_links(self, threshold: float = 0.7) -> List[Dict]:
        """
        Suggest entities that appear in multiple projects that should be linked.
        Uses text similarity to identify candidates.
        
        Args:
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            List of entity pairs that could be linked
        """
        # This is a simplistic implementation - a more sophisticated version
        # would use embedding similarity or other NLP techniques
        query = """
        MATCH (e1:Entity)-[:BELONGS_TO]->(p1:Project)
        MATCH (e2:Entity)-[:BELONGS_TO]->(p2:Project)
        WHERE p1.name <> p2.name
        AND e1.text = e2.text
        AND NOT (e1)-[:LINKED_TO]-(e2)
        RETURN e1, e2, p1.name as project1, p2.name as project2
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            return [{
                "entity1": dict(record["e1"]),
                "entity2": dict(record["e2"]),
                "project1": record["project1"],
                "project2": record["project2"]
            } for record in result]
            
    def create_cross_project_link(self, entity1_id: str, entity2_id: str, 
                               link_type: str = "LINKED_TO") -> str:
        """Create a link between entities across different projects."""
        query = f"""
        MATCH (e1 {{id: $entity1_id}})
        MATCH (e2 {{id: $entity2_id}})
        MERGE (e1)-[r:{link_type}]->(e2)
        ON CREATE SET 
            r.id = randomUUID(),
            r.created_at = datetime()
        RETURN r.id as link_id
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity1_id=entity1_id, entity2_id=entity2_id)
            record = result.single()
            if record:
                return record["link_id"]
            else:
                logger.error(f"Failed to create cross-project link between {entity1_id} and {entity2_id}")
                return None