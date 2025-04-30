#!/usr/bin/env python3

import os
import sys
import argparse
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
import openai
import numpy as np
from tabulate import tabulate
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def initialize_firebase():
    """Initialize Firebase with service account."""
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Initialize with service account
        service_account_path = './service-account.json'
        print(f"Initializing Firebase with service account: {service_account_path}")
        if not os.path.exists(service_account_path):
            logger.error(f"Service account file not found at {service_account_path}")
            sys.exit(1)
            
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        
    return firestore.client()

def generate_embedding(text):
    """Generate embedding for the given text using OpenAI API."""
    try:
        print(f"Generating embedding for query: '{text}'")
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        embedding = response.data[0].embedding
        print(f"Successfully generated query embedding with dimension {len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def semantic_search(query, limit=10):
    """Perform semantic search using embeddings."""
    db = initialize_firebase()
    
    # Generate embedding for the query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []
    
    # Fetch chunks with embeddings
    print("Fetching chunks with embeddings...")
    chunks_ref = db.collection('research_chunks')
    chunks = chunks_ref.limit(1000).stream()  # Limit to 1000 for performance
    
    # Calculate similarity scores
    print("Calculating similarity scores...")
    results = []
    skipped = 0
    processed = 0
    
    for chunk in chunks:
        processed += 1
        chunk_data = chunk.to_dict()
        
        if 'embedding' not in chunk_data:
            skipped += 1
            continue
            
        chunk_embedding = chunk_data['embedding']
        
        # Calculate cosine similarity
        similarity = np.dot(query_embedding, chunk_embedding) / \
                    (np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding))
        
        if similarity > 0.75:  # Threshold for relevance
            results.append({
                'chunk_id': chunk.id,
                'text': chunk_data.get('text', ''),
                'metadata': chunk_data.get('metadata', {}),
                'similarity': similarity,
                'match_type': f"Semantic ({similarity:.4f})"
            })
    
    print(f"Processed {processed} chunks, skipped {skipped} chunks")
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def keyword_search(query, limit=10):
    """Perform keyword-based search on raw chunks."""
    db = initialize_firebase()
    
    print(f"Performing keyword search for: '{query}'")
    
    # Fetch raw chunks
    print("Fetching raw chunks...")
    raw_chunks_ref = db.collection('research_chunks_raw')
    raw_chunks = raw_chunks_ref.limit(1000).stream()  # Limit to 1000 for performance
    raw_chunks_list = [chunk.to_dict() for chunk in raw_chunks]
    print(f"Found {len(raw_chunks_list)} raw chunks")
    
    # Extract search terms from query
    search_terms = query.lower().split()
    print(f"Expanded search terms: {search_terms}")
    
    # Define additional related terms for misophonia topics
    topic_expansions = {
        'treatment': ['therapy', 'intervention', 'approach', 'management', 'technique', 'strategy', 'protocol'],
        'symptom': ['sign', 'manifestation', 'indication', 'characteristic', 'feature'],
        'trigger': ['stimulus', 'sound', 'noise', 'cue', 'provocation', 'elicit'],
        'coping': ['manage', 'deal', 'handle', 'strategy', 'technique', 'skill'],
        'anxiety': ['anxious', 'stress', 'distress', 'fear', 'worry', 'panic'],
        'anger': ['rage', 'irritation', 'frustration', 'annoyance', 'irritability'],
        'brain': ['neural', 'neurological', 'cognitive', 'neuroanatomical', 'neurobiological'],
        'children': ['child', 'adolescent', 'teen', 'youth', 'pediatric', 'young'],
        'comorbid': ['comorbidity', 'coexisting', 'concurrent', 'accompanying', 'associated']
    }
    
    # Expand search terms with related terms
    expanded_terms = search_terms.copy()
    for term in search_terms:
        for topic, related_terms in topic_expansions.items():
            if term in topic or topic in term:
                expanded_terms.extend(related_terms)
    
    # Remove duplicates and very common words
    common_words = ['the', 'and', 'or', 'in', 'of', 'to', 'a', 'is', 'that', 'for', 'on', 'with']
    expanded_terms = [term for term in expanded_terms if term not in common_words]
    expanded_terms = list(set(expanded_terms))
    
    print(f"Expanded search terms: {expanded_terms}")
    
    # Search for matching chunks
    print("Searching for matching chunks...")
    results = []
    
    for chunk in raw_chunks_list:
        if 'text' not in chunk:
            continue
            
        text = chunk['text'].lower()
        metadata = chunk.get('metadata', {})
        
        # Count matches for each term
        match_count = 0
        for term in expanded_terms:
            if term in text:
                match_count += 1
        
        # Calculate a simple relevance score based on match count
        if match_count > 0:
            relevance = match_count / len(expanded_terms)
            
            # Boost score for exact phrase matches
            if query.lower() in text:
                relevance += 0.3
            
            # Only include if relevance is above threshold
            if relevance > 0.2:  # Lower threshold for keyword search
                results.append({
                    'chunk_id': metadata.get('chunk_id', 'unknown'),
                    'text': chunk['text'],
                    'metadata': metadata,
                    'similarity': relevance,
                    'match_type': f"Keyword ({relevance:.4f})"
                })
    
    print(f"Found {len(results)} matching chunks")
    
    # Sort by relevance score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def format_results(results):
    """Format search results for display."""
    if not results:
        return "No relevant results found."
    
    # Prepare table data
    table_data = []
    citations = []
    
    for i, result in enumerate(results, 1):
        metadata = result.get('metadata', {})
        
        # Extract source information
        source = metadata.get('source', 'Unknown')
        if isinstance(source, list):
            source_str = f"[{''.join(source)}]"
        else:
            source_str = f"[{source}]"
            
        year = metadata.get('year', 'None')
        source_with_year = f"{source_str} ({year})"
        
        # Extract title
        title = metadata.get('title', 'Unknown Title')
        
        # Extract section
        section = metadata.get('section', 'Unknown Section')
        if section and section.startswith('Page '):
            section = section
        elif section:
            section = f"Section: {section}"
        else:
            section = 'Unknown Section'
        
        # Format text snippet (truncate if too long)
        text = result.get('text', '')
        if len(text) > 150:
            text = text[:147] + '...'
        
        # Add to table
        table_data.append([
            i,
            source_with_year,
            title,
            section,
            text,
            result.get('match_type', 'Unknown')
        ])
        
        # Add to citations
        citation = f"{source_str} ({year}). {title}."
        if citation not in citations:
            citations.append(citation)
    
    # Create table
    table = tabulate(
        table_data,
        headers=['#', 'Source', 'Title', 'Section', 'Text Snippet', 'Match Type'],
        tablefmt='grid'
    )
    
    # Format citations
    citations_text = "\nCitations:\n" + "\n".join([f"{i+1}. {citation}" for i, citation in enumerate(citations)])
    
    return table + citations_text

def comprehensive_search(query, limit=10):
    """Perform both semantic and keyword search and combine results."""
    print("\n==================================================")
    print(f"Searching for: '{query}'")
    print("==================================================\n")
    
    print("\n--- Semantic Search ---\n")
    semantic_results = semantic_search(query, limit)
    
    print("\n--- Keyword Search ---\n")
    keyword_results = keyword_search(query, limit)
    
    # Combine results, prioritizing semantic matches
    combined_results = []
    seen_chunk_ids = set()
    
    # Add semantic results first
    for result in semantic_results:
        chunk_id = result.get('chunk_id')
        if chunk_id not in seen_chunk_ids:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
    
    # Add keyword results that aren't duplicates
    for result in keyword_results:
        chunk_id = result.get('chunk_id')
        if chunk_id not in seen_chunk_ids:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
    
    # Sort by similarity score
    combined_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Limit to requested number
    final_results = combined_results[:limit]
    
    print("\n--- Combined Results ---\n")
    print(f"\nFound {len(final_results)} results\n")
    
    # Format and return results
    return format_results(final_results)

def generate_rag_response(query, search_results, max_tokens=500):
    """Generate a RAG response using the search results and OpenAI."""
    try:
        # Prepare prompt with search results
        prompt = f"""You are an AI assistant specialized in misophonia, a condition where specific sounds trigger strong emotional reactions.
        
Based on the following research information, please answer this question: "{query}"

Research information:
{search_results}

Provide a comprehensive, evidence-based answer that directly addresses the question. 
Cite specific sources from the research information when making claims.
If the research information doesn't contain relevant details to answer the question, acknowledge the limitations of the available information.
"""
        
        # Generate response
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides evidence-based information about misophonia based on scientific research."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating RAG response: {e}")
        return f"Error generating response: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description='Misophonia RAG Query Interface')
    parser.add_argument('--query', type=str, help='Query to search for')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of results to return')
    parser.add_argument('--raw', action='store_true', help='Show raw search results without generating a response')
    args = parser.parse_args()
    
    if not args.query:
        query = input("Enter your question about misophonia: ")
    else:
        query = args.query
    
    # Perform search
    search_results = comprehensive_search(query, args.limit)
    
    # Print search results
    print(search_results)
    
    # Generate RAG response if not in raw mode
    if not args.raw:
        print("\n--- RAG Response ---\n")
        response = generate_rag_response(query, search_results)
        print(response)

if __name__ == "__main__":
    main()
