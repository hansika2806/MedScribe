"""
Hybrid RAG Node - Retrieves relevant clinical guidelines
Implements: α × Cosine + β × BM25 + γ × Metadata Match
"""
import logging
from backend.pipeline.state import PipelineState
from backend.tools.corpus_loader import get_corpus_collection
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import BM25
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("rank-bm25 not available, using cosine similarity only")

# Hybrid scoring weights
ALPHA = 0.4  # Cosine similarity weight
BETA = 0.3   # BM25 weight
GAMMA = 0.3  # Metadata match weight


def build_query(state: PipelineState) -> str:
    """
    Build search query from session context
    
    Returns:
        Query string combining condition, drug_class, and symptoms
    """
    try:
        extracted = state.get("extracted_entities")
        if not extracted:
            logger.warning("No extracted entities for RAG query")
            return ""
        
        # Get population tag
        pop_tag = extracted.population_tag
        condition = pop_tag.condition if pop_tag and pop_tag.condition else "general"
        drug_class = pop_tag.drug_class if pop_tag and pop_tag.drug_class else "general"
        
        # Skip if condition is unknown or none
        if condition in ["unknown", "none", ""]:
            condition = "general"
        if drug_class in ["unknown", "none", ""]:
            drug_class = "general"
        
        # Get symptoms
        symptoms = [s.symptom for s in extracted.symptoms[:5]]  # Top 5 symptoms
        symptoms_str = " ".join(symptoms) if symptoms else ""
        
        # Get medications for additional context
        medications = [m.drug for m in extracted.medications[:3]]  # Top 3 meds
        meds_str = " ".join(medications) if medications else ""
        
        # Build query - use all available info
        query_parts = [condition, drug_class, symptoms_str, meds_str]
        query = " ".join([p for p in query_parts if p and p != "general"]).strip()
        
        # Fallback to general if still empty
        if not query or query == "general general":
            query = "general medical guidelines"
        
        logger.info(f"Built RAG query: '{query}'")
        return query
        
    except Exception as e:
        logger.error(f"Failed to build query: {e}")
        return "general medical guidelines"


def filter_by_metadata(collection: Any, population: str, condition: str) -> List[Dict[str, Any]]:
    """
    Hard filter documents by population and condition metadata
    
    Args:
        collection: ChromaDB collection
        population: Patient population (adult/pediatric)
        condition: Medical condition (can be comma-separated)
        
    Returns:
        List of filtered documents with metadata
    """
    try:
        # Get all documents
        all_docs = collection.get(include=["documents", "metadatas"])
        
        # Parse condition - handle comma-separated conditions
        conditions = [c.strip().lower() for c in condition.split(",")]
        
        filtered = []
        for i, metadata in enumerate(all_docs["metadatas"]):
            # Check population match
            doc_population = metadata.get("population", "adult")
            if doc_population != population:
                continue
            
            # Check condition match (or general)
            doc_condition = metadata.get("condition", "general").lower()
            
            # Match if document condition is "general" or matches any of the patient conditions
            if doc_condition == "general" or any(cond in doc_condition or doc_condition in cond for cond in conditions):
                filtered.append({
                    "id": all_docs["ids"][i],
                    "content": all_docs["documents"][i],
                    "metadata": metadata
                })
        
        logger.info(f"Filtered to {len(filtered)} documents (population={population}, condition={condition})")
        return filtered
        
    except Exception as e:
        logger.error(f"Metadata filtering failed: {e}")
        return []


def compute_cosine_scores(collection: Any, query: str, filtered_ids: List[str]) -> Dict[str, float]:
    """
    Compute cosine similarity scores using ChromaDB
    
    Returns:
        Dict mapping document ID to cosine score
    """
    try:
        if not filtered_ids:
            return {}
        
        # Query ChromaDB for semantic similarity
        results = collection.query(
            query_texts=[query],
            n_results=min(len(filtered_ids), 20),
            include=["distances"]
        )
        
        # Convert distances to similarity scores (ChromaDB returns L2 distances)
        # Normalize to 0-1 range
        scores = {}
        if results["ids"] and results["distances"]:
            ids = results["ids"][0]
            distances = results["distances"][0]
            
            # Convert L2 distance to similarity
            max_dist = max(distances) if distances else 1.0
            for doc_id, dist in zip(ids, distances):
                # Invert and normalize: closer = higher score
                scores[doc_id] = 1.0 - (dist / max_dist) if max_dist > 0 else 1.0
        
        logger.info(f"Computed cosine scores for {len(scores)} documents")
        return scores
        
    except Exception as e:
        logger.error(f"Cosine scoring failed: {e}")
        return {}


def compute_bm25_scores(filtered_docs: List[Dict[str, Any]], query: str) -> Dict[str, float]:
    """
    Compute BM25 scores for filtered documents
    
    Returns:
        Dict mapping document ID to BM25 score (normalized 0-1)
    """
    if not BM25_AVAILABLE or not filtered_docs:
        return {}
    
    try:
        # Tokenize documents
        tokenized_docs = []
        doc_ids = []
        for doc in filtered_docs:
            tokens = doc["content"].lower().split()
            tokenized_docs.append(tokens)
            doc_ids.append(doc["id"])
        
        # Initialize BM25
        bm25 = BM25Okapi(tokenized_docs)
        
        # Tokenize query
        query_tokens = query.lower().split()
        
        # Get scores
        scores = bm25.get_scores(query_tokens)
        
        # Normalize to 0-1
        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0
        normalized_scores = {
            doc_id: float(score / max_score)
            for doc_id, score in zip(doc_ids, scores)
        }
        
        logger.info(f"Computed BM25 scores for {len(normalized_scores)} documents")
        return normalized_scores
        
    except Exception as e:
        logger.error(f"BM25 scoring failed: {e}")
        return {}


def compute_metadata_scores(filtered_docs: List[Dict[str, Any]], population: str, condition: str) -> Dict[str, float]:
    """
    Compute metadata match scores
    
    Returns:
        Dict mapping document ID to metadata score
    """
    scores = {}
    for doc in filtered_docs:
        metadata = doc["metadata"]
        score = 0.0
        
        # Exact population match
        if metadata.get("population") == population:
            score += 0.5
        
        # Exact condition match
        if metadata.get("condition") == condition:
            score += 0.5
        elif metadata.get("condition") == "general":
            score += 0.25  # Partial credit for general guidelines
        
        scores[doc["id"]] = score
    
    return scores


def hybrid_retrieve(
    collection: Any,
    query: str,
    population: str,
    condition: str,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval combining cosine, BM25, and metadata matching
    
    Score = α × Cosine + β × BM25 + γ × Metadata
    
    Returns:
        Top-k documents with scores
    """
    try:
        # Step 1: Hard filter by metadata
        filtered_docs = filter_by_metadata(collection, population, condition)
        if not filtered_docs:
            logger.warning("No documents passed metadata filter")
            return []
        
        filtered_ids = [doc["id"] for doc in filtered_docs]
        
        # Step 2: Compute cosine similarity scores
        cosine_scores = compute_cosine_scores(collection, query, filtered_ids)
        
        # Step 3: Compute BM25 scores
        bm25_scores = compute_bm25_scores(filtered_docs, query)
        
        # Step 4: Compute metadata scores
        metadata_scores = compute_metadata_scores(filtered_docs, population, condition)
        
        # Step 5: Combine scores
        final_scores = {}
        for doc in filtered_docs:
            doc_id = doc["id"]
            
            cosine = cosine_scores.get(doc_id, 0.0)
            bm25 = bm25_scores.get(doc_id, 0.0)
            metadata = metadata_scores.get(doc_id, 0.0)
            
            # Hybrid score
            final_score = (ALPHA * cosine) + (BETA * bm25) + (GAMMA * metadata)
            final_scores[doc_id] = final_score
        
        # Step 6: Sort and return top-k
        sorted_docs = sorted(
            filtered_docs,
            key=lambda d: final_scores.get(d["id"], 0.0),
            reverse=True
        )[:top_k]
        
        # Add scores to results
        results = []
        for doc in sorted_docs:
            doc_id = doc["id"]
            results.append({
                "content": doc["content"],
                "source": doc["metadata"].get("source", "Unknown"),
                "relevance_score": round(final_scores[doc_id], 3),
                "population_match": doc["metadata"].get("population", "unknown"),
                "condition_match": doc["metadata"].get("condition", "unknown"),
                "year": doc["metadata"].get("year", "unknown"),
                "section": doc["metadata"].get("section", "")
            })
        
        logger.info(f"Retrieved {len(results)} guidelines (top-{top_k})")
        return results
        
    except Exception as e:
        logger.error(f"Hybrid retrieval failed: {e}")
        return []


def rag_node(state: PipelineState) -> PipelineState:
    """
    RAG Node: Retrieve relevant clinical guidelines
    
    Input: extracted_entities
    Output: retrieved_guidelines
    """
    logger.info("Node 10: RAG - Retrieving clinical guidelines...")
    
    try:
        # Get corpus collection
        collection = get_corpus_collection()
        if not collection:
            logger.warning("Corpus not available, skipping RAG")
            state["retrieved_guidelines"] = []
            return state
        
        # Build query from context
        query = build_query(state)
        if not query:
            logger.warning("Empty query, skipping RAG")
            state["retrieved_guidelines"] = []
            return state
        
        # Get population and condition
        extracted = state.get("extracted_entities")
        if not extracted:
            logger.warning("No extracted entities, skipping RAG")
            state["retrieved_guidelines"] = []
            return state
        
        pop_tag = extracted.population_tag
        population = pop_tag.age_group if pop_tag else "adult"
        condition = pop_tag.condition if pop_tag else "general"
        
        # Perform hybrid retrieval
        guidelines = hybrid_retrieve(
            collection=collection,
            query=query,
            population=population,
            condition=condition,
            top_k=5
        )
        
        state["retrieved_guidelines"] = guidelines
        logger.info(f"RAG complete: {len(guidelines)} guidelines retrieved")
        
    except Exception as e:
        logger.error(f"RAG node failed: {e}")
        state["retrieved_guidelines"] = []
        state["error"] = f"RAG error: {str(e)}"
    
    return state


# Made with Bob