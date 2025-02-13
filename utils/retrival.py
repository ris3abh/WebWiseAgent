# utils/retrival.pys

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from typing import List, Dict, Tuple

class BM_RAGAM:
    def __init__(self):
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
    def compute_bm25_scores(self, query: str, documents: List[str]) -> np.ndarray:
        """Compute BM25 scores for documents."""
        tokenized_docs = [doc.lower().split() for doc in documents]
        tokenized_query = query.lower().split()
        bm25 = BM25Okapi(tokenized_docs)
        return np.array(bm25.get_scores(tokenized_query))

    def compute_semantic_scores(self, query: str, documents: List[str]) -> np.ndarray:
        """Compute semantic similarity scores using transformer embeddings."""
        query_embedding = self.encoder.encode([query], convert_to_tensor=True)
        doc_embeddings = self.encoder.encode(documents, convert_to_tensor=True)
        
        similarities = cosine_similarity(
            query_embedding.cpu().numpy(),
            doc_embeddings.cpu().numpy()
        )[0]
        return similarities

    def compute_attention_weights(self, bm25_scores: np.ndarray, semantic_scores: np.ndarray) -> Tuple[float, float]:
        """Compute attention weights for BM25 and semantic scores."""
        bm25_max = np.max(bm25_scores) if len(bm25_scores) > 0 else 1
        semantic_max = np.max(semantic_scores) if len(semantic_scores) > 0 else 1
        
        # Normalize scores
        bm25_norm = bm25_scores / bm25_max if bm25_max != 0 else bm25_scores
        semantic_norm = semantic_scores / semantic_max if semantic_max != 0 else semantic_scores
        
        # Compute weights using softmax
        weights = np.exp([np.mean(bm25_norm), np.mean(semantic_norm)])
        weights = weights / np.sum(weights)
        
        return weights[0], weights[1]

    def rank_documents(self, query: str, documents: List[str]) -> List[Tuple[int, float]]:
        """Rank documents using the hybrid approach."""
        bm25_scores = self.compute_bm25_scores(query, documents)
        semantic_scores = self.compute_semantic_scores(query, documents)
        
        # Compute attention weights
        bm25_weight, semantic_weight = self.compute_attention_weights(bm25_scores, semantic_scores)
        
        # Combine scores using attention weights
        final_scores = (bm25_weight * bm25_scores) + (semantic_weight * semantic_scores)
        
        # Return sorted document indices and scores
        ranked_indices = np.argsort(final_scores)[::-1]
        return [(idx, final_scores[idx]) for idx in ranked_indices]

class VectorizedKnowledgeBase:
    def __init__(self):
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.document_vectors = None
        self.documents = []
        self.urls = []

    def add_documents(self, documents: List[str], urls: List[str]):
        """Add documents to the knowledge base."""
        self.documents.extend(documents)
        self.urls.extend(urls)
        new_vectors = self.encoder.encode(documents)
        
        if self.document_vectors is None:
            self.document_vectors = new_vectors
        else:
            self.document_vectors = np.vstack([self.document_vectors, new_vectors])

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """Search for most relevant documents."""
        query_vector = self.encoder.encode([query])[0]
        
        # Compute similarities
        similarities = cosine_similarity([query_vector], self.document_vectors)[0]
        
        # Get top-k results
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        return [(self.urls[i], self.documents[i], similarities[i]) for i in top_indices] 