#!/usr/bin/env python3

"""
Direct Semantic Search

This script performs semantic search directly against the Firestore database
without using the Cloud Function, which is experiencing timeout issues.
"""

import os
import time
import json
import numpy as np
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from tabulate import tabulate
import argparse
import openai

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
                        'score': similarity
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
        
        # Add to table data
        table_data.append([
            i + 1,
            f"{authors} ({year})",
            title,
            section,
            text,
            f"{result.get('score', 0):.4f}"
        ])
    
    # Display the table
    headers = ["#", "Source", "Title", "Section", "Text Snippet", "Score"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def main():
    parser = argparse.ArgumentParser(description='Perform direct semantic search')
    parser.add_argument('--query', type=str, help='Search query')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of results to return')
    parser.add_argument('--threshold', type=float, default=0.6, help='Similarity threshold (0.0 to 1.0)')
    parser.add_argument('--year', type=str, help='Filter by year (single year or range, e.g., "2020" or "2010-2020")')
    parser.add_argument('--author', type=str, help='Filter by author name')
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
        
        results = perform_semantic_search(
            db, 
            query, 
            limit=args.limit, 
            similarity_threshold=args.threshold,
            filters=filters
        )
        
        display_search_results(results)
        
        # Wait a bit between queries to avoid rate limiting
        if len(queries) > 1 and query != queries[-1]:
            print("\nWaiting 5 seconds before next query...")
            time.sleep(5)

if __name__ == "__main__":
    main()
