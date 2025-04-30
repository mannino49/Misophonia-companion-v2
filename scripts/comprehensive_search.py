#!/usr/bin/env python3

"""
Comprehensive Search Interface

This script provides a unified search interface that combines both raw text search
and semantic search capabilities for the Misophonia Research Vector Database.
"""

import os
import time
import json
import argparse
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from tabulate import tabulate
import openai
import numpy as np
import re

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

# Set OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

def initialize_firebase():
    """
    Initialize Firebase Admin SDK and return Firestore client.
    """
    try:
        # Initialize Firebase Admin SDK
        print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

def generate_embedding(text):
    """
    Generate embedding for text using OpenAI API.
    """
    try:
        # Use OpenAI's text-embedding-ada-002 model with new API format
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        
        # Extract the embedding from the response
        embedding = response.data[0].embedding
        
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def calculate_cosine_similarity(vec1, vec2):
    """
    Calculate cosine similarity between two vectors.
    """
    # Convert to numpy arrays for efficient computation
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    # Calculate dot product
    dot_product = np.dot(vec1, vec2)
    
    # Calculate magnitudes
    mag1 = np.linalg.norm(vec1)
    mag2 = np.linalg.norm(vec2)
    
    if mag1 == 0 or mag2 == 0:
        return 0
    
    return dot_product / (mag1 * mag2)

def perform_semantic_search(db, query, limit=10, similarity_threshold=0.6, filters=None):
    """
    Perform semantic search directly against the Firestore database.
    """
    try:
        print(f"Generating embedding for query: '{query}'")
        query_embedding = generate_embedding(query)
        
        if not query_embedding:
            print("Failed to generate query embedding")
            return []
        
        print(f"Successfully generated query embedding with dimension {len(query_embedding)}")
        
        # Get all chunks with embeddings
        print("Fetching chunks with embeddings...")
        chunks_query = db.collection('research_chunks').limit(1000)
        chunks = chunks_query.get()
        
        print(f"Found {len(chunks)} chunks with embeddings")
        
        # Calculate similarity scores for each chunk
        print("Calculating similarity scores...")
        scored_results = []
        skipped_chunks = 0
        
        for chunk in chunks:
            chunk_data = chunk.to_dict()
            
            # Skip chunks without embeddings
            if 'embedding' not in chunk_data:
                skipped_chunks += 1
                continue
            
            # Check if embedding has the correct dimension
            chunk_embedding = chunk_data['embedding']
            if len(chunk_embedding) != 1536:
                print(f"Warning: Chunk {chunk.id} has embedding dimension {len(chunk_embedding)} instead of 1536")
                skipped_chunks += 1
                continue
            
            # Apply filters if provided
            if filters:
                metadata = chunk_data.get('metadata', {})
                
                # Filter by year
                if 'year' in filters:
                    year_filter = filters['year']
                    chunk_year = metadata.get('year')
                    
                    if isinstance(year_filter, list) and len(year_filter) == 2:
                        # Range filter
                        if not chunk_year or chunk_year < year_filter[0] or chunk_year > year_filter[1]:
                            continue
                    else:
                        # Exact match
                        if not chunk_year or chunk_year != year_filter:
                            continue
                
                # Filter by author
                if 'author' in filters:
                    author_filter = filters['author']
                    chunk_author = metadata.get('primary_author')
                    
                    if not chunk_author or author_filter.lower() not in chunk_author.lower():
                        continue
            
            try:
                # Calculate similarity score
                similarity = calculate_cosine_similarity(query_embedding, chunk_embedding)
                
                # Only include results above the similarity threshold
                if similarity >= similarity_threshold:
                    scored_results.append({
                        'id': chunk.id,
                        'text': chunk_data.get('text', ''),
                        'metadata': chunk_data.get('metadata', {}),
                        'score': similarity,
                        'search_type': 'semantic'
                    })
            except Exception as e:
                print(f"Error calculating similarity for chunk {chunk.id}: {e}")
                skipped_chunks += 1
        
        print(f"Processed {len(chunks) - skipped_chunks} chunks, skipped {skipped_chunks} chunks")
        
        # Sort results by similarity score (descending)
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit results
        top_results = scored_results[:limit]
        
        print(f"Found {len(top_results)} relevant results")
        
        return top_results
    except Exception as e:
        print(f"Error performing semantic search: {e}")
        return []

def perform_keyword_search(db, query, limit=10, filters=None):
    """
    Perform keyword-based search on raw chunks with fuzzy matching.
    """
    try:
        print(f"Performing keyword search for: '{query}'")
        
        # Get raw chunks
        print("Fetching raw chunks...")
        raw_chunks_query = db.collection('research_chunks_raw').limit(1000)
        raw_chunks = raw_chunks_query.get()
        
        print(f"Found {len(raw_chunks)} raw chunks")
        
        # Extract key concepts from the query
        # For misophonia-related searches, add relevant keywords
        search_terms = query.lower().split()
        
        # Add related terms for common misophonia topics
        expanded_terms = list(search_terms)  # Start with original terms
        
        # Topic-specific expansions
        if 'treatment' in search_terms or 'therapy' in search_terms:
            expanded_terms.extend(['treatment', 'therapy', 'intervention', 'management', 'cbt', 'cognitive', 'behavioral'])
        
        if 'symptom' in search_terms:
            expanded_terms.extend(['symptom', 'sign', 'manifestation', 'reaction', 'response', 'trigger'])
        
        if 'anxiety' in search_terms:
            expanded_terms.extend(['anxiety', 'anxious', 'stress', 'distress', 'fear', 'worry', 'panic'])
        
        # Remove duplicates while preserving order
        expanded_terms = list(dict.fromkeys(expanded_terms))
        
        print(f"Expanded search terms: {expanded_terms}")
        
        # Search for chunks containing the search terms
        print("Searching for matching chunks...")
        matching_chunks = []
        
        for chunk in raw_chunks:
            chunk_data = chunk.to_dict()
            chunk_text = chunk_data.get('text', '').lower()
            
            # Apply filters if provided
            if filters:
                metadata = chunk_data.get('metadata', {})
                
                # Filter by year
                if 'year' in filters:
                    year_filter = filters['year']
                    chunk_year = metadata.get('year')
                    
                    if isinstance(year_filter, list) and len(year_filter) == 2:
                        # Range filter
                        if not chunk_year or chunk_year < year_filter[0] or chunk_year > year_filter[1]:
                            continue
                    else:
                        # Exact match
                        if not chunk_year or chunk_year != year_filter:
                            continue
                
                # Filter by author
                if 'author' in filters:
                    author_filter = filters['author']
                    chunk_author = metadata.get('primary_author')
                    
                    if not chunk_author or author_filter.lower() not in chunk_author.lower():
                        continue
            
            # Check if the chunk contains any of the expanded terms
            # For misophonia, we want to be more lenient with matching
            matched_terms = [term for term in expanded_terms if term in chunk_text]
            
            # If the chunk contains 'misophonia' and at least one other search term, consider it a match
            if 'misophonia' in chunk_text and len(matched_terms) > 0:
                # Calculate a relevance score based on matched terms and their frequency
                term_count = sum(chunk_text.count(term) for term in matched_terms)
                relevance_score = (term_count / len(chunk_text.split())) * (len(matched_terms) / len(expanded_terms))
                
                # Boost score if it contains multiple original search terms
                original_term_matches = sum(1 for term in search_terms if term in chunk_text)
                if original_term_matches > 1:
                    relevance_score *= 1.5
            # Or if it contains at least 2 of the expanded terms
            elif len(matched_terms) >= 2:
                # Calculate a relevance score based on matched terms and their frequency
                term_count = sum(chunk_text.count(term) for term in matched_terms)
                relevance_score = (term_count / len(chunk_text.split())) * (len(matched_terms) / len(expanded_terms))
                
                matching_chunks.append({
                    'id': chunk.id,
                    'text': chunk_data.get('text', ''),
                    'metadata': chunk_data.get('metadata', {}),
                    'score': relevance_score,
                    'search_type': 'keyword',
                    'matched_terms': matched_terms
                })
        
        # Sort results by relevance score (descending)
        matching_chunks.sort(key=lambda x: x['score'], reverse=True)
        
        # Limit results
        top_results = matching_chunks[:limit]
        
        print(f"Found {len(top_results)} matching chunks")
        
        return top_results
    except Exception as e:
        print(f"Error performing keyword search: {e}")
        return []

def combine_search_results(semantic_results, keyword_results, limit=10):
    """
    Combine and deduplicate results from semantic and keyword searches.
    """
    # Create a dictionary to track unique results by content
    unique_results = {}
    
    # Process semantic results first (they usually have higher quality)
    for result in semantic_results:
        # Use the first 100 characters of text as a key for deduplication
        text_key = result['text'][:100] if result['text'] else result['id']
        unique_results[text_key] = result
    
    # Add keyword results if they don't duplicate semantic results
    for result in keyword_results:
        text_key = result['text'][:100] if result['text'] else result['id']
        if text_key not in unique_results:
            unique_results[text_key] = result
    
    # Convert back to list and sort by score
    combined_results = list(unique_results.values())
    combined_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Limit to the requested number of results
    return combined_results[:limit]

def format_citation(result):
    """
    Format a citation for a search result in APA style.
    """
    metadata = result.get('metadata', {})
    
    authors = metadata.get('authors', 'Unknown')
    year = metadata.get('year', 'n.d.')
    title = metadata.get('title', 'Untitled')
    
    # Format authors
    if isinstance(authors, list):
        if len(authors) == 1:
            author_text = authors[0]
        elif len(authors) == 2:
            author_text = f"{authors[0]} & {authors[1]}"
        else:
            author_text = f"{authors[0]} et al."
    else:
        author_text = authors
    
    return f"{author_text} ({year}). {title}."

def display_search_results(results):
    """
    Display search results in a readable format.
    """
    if not results:
        print("No results to display")
        return
    
    print(f"\nFound {len(results)} results\n")
    
    table_data = []
    for i, result in enumerate(results):
        # Extract metadata
        metadata = result.get('metadata', {})
        document_id = metadata.get('document_id', 'Unknown')
        title = metadata.get('title', 'Unknown')
        authors = metadata.get('authors', 'Unknown')
        year = metadata.get('year', 'Unknown')
        section = metadata.get('section', 'Unknown')
        
        # Format the text (truncate if too long)
        text = result.get('text', '')
        if len(text) > 200:
            text = text[:197] + '...'
        
        # Format search type and score
        search_type = result.get('search_type', 'unknown')
        score = result.get('score', 0)
        search_info = f"{search_type.capitalize()} ({score:.4f})"
        
        # Add to table data
        table_data.append([
            i + 1,
            f"{authors} ({year})",
            title,
            section,
            text,
            search_info
        ])
    
    # Display the table
    headers = ["#", "Source", "Title", "Section", "Text Snippet", "Match Type"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Display citations
    print("\nCitations:")
    for i, result in enumerate(results):
        citation = format_citation(result)
        print(f"{i + 1}. {citation}")

def main():
    parser = argparse.ArgumentParser(description='Comprehensive search for the Misophonia Research Vector Database')
    parser.add_argument('--query', type=str, help='Search query')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of results to return')
    parser.add_argument('--threshold', type=float, default=0.7, help='Similarity threshold for semantic search (0.0 to 1.0)')
    parser.add_argument('--year', type=str, help='Filter by year (single year or range, e.g., "2020" or "2010-2020")')
    parser.add_argument('--author', type=str, help='Filter by author name')
    parser.add_argument('--semantic-only', action='store_true', help='Only use semantic search')
    parser.add_argument('--keyword-only', action='store_true', help='Only use keyword search')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    # If no query provided, use predefined queries
    queries = []
    if args.query:
        queries = [args.query]
    else:
        queries = [
            "What are the symptoms of misophonia?",
            "How is misophonia treated?",
            "What is the relationship between misophonia and anxiety?",
            "What are the neurological mechanisms of misophonia?"
        ]
    
    # Prepare filters
    filters = {}
    if args.year:
        if '-' in args.year:
            # Range filter
            year_range = args.year.split('-')
            filters['year'] = [int(year_range[0]), int(year_range[1])]
        else:
            # Exact match
            filters['year'] = int(args.year)
    
    if args.author:
        filters['author'] = args.author
    
    # Perform search for each query
    for query in queries:
        print("\n==================================================")
        print(f"Searching for: '{query}'")
        print("==================================================\n")
        
        semantic_results = []
        keyword_results = []
        
        # Perform semantic search if not keyword-only
        if not args.keyword_only:
            print("\n--- Semantic Search ---\n")
            semantic_results = perform_semantic_search(
                db, 
                query, 
                limit=args.limit, 
                similarity_threshold=args.threshold,
                filters=filters
            )
        
        # Perform keyword search if not semantic-only
        if not args.semantic_only:
            print("\n--- Keyword Search ---\n")
            keyword_results = perform_keyword_search(
                db,
                query,
                limit=args.limit,
                filters=filters
            )
        
        # Combine results
        if not args.semantic_only and not args.keyword_only:
            print("\n--- Combined Results ---\n")
            combined_results = combine_search_results(semantic_results, keyword_results, limit=args.limit)
            display_search_results(combined_results)
        elif args.semantic_only:
            display_search_results(semantic_results)
        else:
            display_search_results(keyword_results)
        
        # Wait a bit between queries to avoid rate limiting
        if len(queries) > 1 and query != queries[-1]:
            print("\nWaiting 5 seconds before next query...")
            time.sleep(5)

if __name__ == "__main__":
    main()
