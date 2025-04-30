#!/usr/bin/env python3

"""
Test script for vector search functionality

This script tests the semantic search capabilities of our vector database
by performing sample queries and displaying the results.
"""

import os
import sys
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
import time

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# Sample queries to test
SAMPLE_QUERIES = [
    "What are the symptoms of misophonia?",
    "How prevalent is misophonia in university students?",
    "What is the relationship between misophonia and hyperacusis?",
    "What treatments are effective for misophonia?",
    "How does misophonia affect quality of life?"
]

def generate_embedding(text, api_key):
    """
    Generate embedding for text using OpenAI API
    """
    try:
        # Truncate text if it's too long (OpenAI has token limits)
        truncated_text = text[:8000] if len(text) > 8000 else text
        
        # Make API call to OpenAI embeddings endpoint
        response = requests.post(
            'https://api.openai.com/v1/embeddings',
            json={
                'input': truncated_text,
                'model': 'text-embedding-3-small'  # Using OpenAI's latest embedding model
            },
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
        )
        
        response.raise_for_status()  # Raise exception for HTTP errors
        
        # Extract the embedding from the response
        embedding = response.json()['data'][0]['embedding']
        print(f"Generated embedding with dimension: {len(embedding)}")
        return embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return None

def perform_vector_search(db, query_embedding, limit=5):
    """
    Perform vector search in Firestore using the query embedding
    """
    try:
        # Get all documents from research_chunks collection
        chunks_ref = db.collection('research_chunks')
        chunks = chunks_ref.limit(100).get()  # Limit to 100 for testing
        
        # Calculate cosine similarity for each document
        results = []
        for chunk in chunks:
            chunk_data = chunk.to_dict()
            if 'embedding' in chunk_data and chunk_data['embedding']:
                # Calculate cosine similarity (dot product for normalized vectors)
                similarity = calculate_cosine_similarity(query_embedding, chunk_data['embedding'])
                
                results.append({
                    'id': chunk.id,
                    'text': chunk_data.get('text', ''),
                    'metadata': chunk_data.get('metadata', {}),
                    'similarity': similarity
                })
        
        # Sort by similarity (highest first) and take top k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:limit]
    except Exception as e:
        print(f"Error performing vector search: {e}")
        return []

def calculate_cosine_similarity(vec1, vec2):
    """
    Calculate cosine similarity between two vectors
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    
    if magnitude1 * magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

def main():
    # Check if OpenAI API key is provided
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it using: export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Initialize Firebase with service account
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Test database connection
        print("Testing database connection...")
        collections = [collection.id for collection in db.collections()]
        print(f"Available collections: {collections}")
        print("Firebase initialized successfully")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        sys.exit(1)
    
    # Check if we have documents with embeddings
    chunks_ref = db.collection('research_chunks')
    chunks = chunks_ref.limit(5).get()
    
    if not chunks:
        print("No documents found in research_chunks collection")
        print("Make sure the embedding generation process has completed")
        sys.exit(1)
    
    # Test each query
    for i, query in enumerate(SAMPLE_QUERIES):
        print(f"\n\nQuery {i+1}: {query}")
        
        # Generate embedding for query
        query_embedding = generate_embedding(query, api_key)
        if not query_embedding:
            print("Failed to generate embedding for query, skipping...")
            continue
        
        # Perform vector search
        print("Performing vector search...")
        results = perform_vector_search(db, query_embedding)
        
        # Display results
        print(f"\nTop {len(results)} results:")
        for j, result in enumerate(results):
            print(f"\nResult {j+1} (Similarity: {result['similarity']:.4f})")
            metadata = result['metadata']
            print(f"Document: {metadata.get('title', 'Unknown')} ({metadata.get('year', 'Unknown')})")
            print(f"Authors: {', '.join(metadata.get('authors', ['Unknown']))}")
            print(f"Section: {metadata.get('section', 'Unknown')}")
            print(f"Text: {result['text'][:300]}...")
        
        # Add a delay between queries
        if i < len(SAMPLE_QUERIES) - 1:
            print("\nWaiting before next query...")
            time.sleep(2)

if __name__ == "__main__":
    main()
