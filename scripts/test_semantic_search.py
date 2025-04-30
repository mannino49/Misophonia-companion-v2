#!/usr/bin/env python3

"""
Script to test semantic search functionality

This script tests the semantic search Cloud Function by generating
embeddings for a query and performing a vector search in Firestore.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
import json
import os
import time

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Sample test queries
TEST_QUERIES = [
    "What are the symptoms of misophonia?",
    "How is misophonia related to anxiety disorders?",
    "What treatments are effective for misophonia?",
    "Is misophonia more common in certain age groups?",
    "What triggers misophonia reactions?"
]

def generate_embedding(text):
    """Generate embedding for text using OpenAI API"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Truncate text if it's too long (OpenAI has token limits)
    truncated_text = text[:8000] if len(text) > 8000 else text
    
    # Make API call to OpenAI embeddings endpoint
    response = requests.post(
        'https://api.openai.com/v1/embeddings',
        headers={
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'input': truncated_text,
            'model': 'text-embedding-3-small'  # Using OpenAI's latest embedding model
        }
    )
    
    if response.status_code != 200:
        raise ValueError(f"Error from OpenAI API: {response.text}")
    
    # Extract the embedding from the response
    embedding = response.json()['data'][0]['embedding']
    print(f"Generated embedding with dimension: {len(embedding)}")
    return embedding

def manual_vector_search(db, query_embedding, limit=5):
    """Perform a manual vector search using cosine similarity"""
    # Get all documents from research_chunks collection
    docs = db.collection('research_chunks').get()
    
    # Calculate cosine similarity for each document
    results = []
    for doc in docs:
        doc_data = doc.to_dict()
        if 'embedding' not in doc_data:
            continue
        
        # Calculate cosine similarity
        doc_embedding = doc_data['embedding']
        similarity = cosine_similarity(query_embedding, doc_embedding)
        
        results.append({
            'id': doc.id,
            'text': doc_data.get('text', ''),
            'metadata': doc_data.get('metadata', {}),
            'similarity': similarity
        })
    
    # Sort by similarity (highest first)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5
    if magnitude1 * magnitude2 == 0:
        return 0
    return dot_product / (magnitude1 * magnitude2)

def main():
    # Check if OpenAI API Key is set
    if not OPENAI_API_KEY:
        print("\n⚠️ OPENAI_API_KEY environment variable not set!")
        print("Please set the environment variable before running this script:")
        print("export OPENAI_API_KEY=your_api_key_here")
        return
    
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
        print("Firebase initialized successfully\n")
        
        # Check if we have documents in research_chunks collection
        chunks = db.collection('research_chunks').get()
        chunk_list = list(chunks)
        print(f"Found {len(chunk_list)} documents in research_chunks collection")
        
        if len(chunk_list) == 0:
            print("\n⚠️ No documents found in research_chunks collection!")
            print("Please make sure the embedding generation process has completed.")
            
            # Create sample documents with embeddings for testing
            print("\nCreating sample documents with embeddings for testing...")
            
            # Sample texts for testing
            sample_texts = [
                "Misophonia is a condition characterized by strong negative emotional reactions to specific sounds, particularly those made by humans such as chewing, breathing, or repetitive tapping.",
                "Symptoms of misophonia include intense anger, disgust, or anxiety when exposed to trigger sounds. Some individuals report physical sensations such as pressure in the chest.",
                "The prevalence of misophonia is not well established, but studies suggest it may affect between 15-20% of the general population to some degree.",
                "Current treatment approaches for misophonia include cognitive-behavioral therapy (CBT), sound therapy, mindfulness-based interventions, and in some cases, medication for comorbid conditions.",
                "Neuroimaging studies have identified abnormal functional connectivity between the anterior insular cortex and other regions involved in emotional processing and regulation in individuals with misophonia."
            ]
            
            for i, text in enumerate(sample_texts):
                # Generate embedding for the text
                print(f"\nGenerating embedding for sample text {i+1}...")
                embedding = generate_embedding(text)
                
                # Create document in research_chunks collection
                doc_id = f"test_sample_{i+1}"
                db.collection('research_chunks').document(doc_id).set({
                    'text': text,
                    'embedding': embedding,
                    'metadata': {
                        'title': f"Test Sample {i+1}",
                        'authors': ["Test Author"],
                        'year': 2024,
                        'section': f"Test Section {i+1}",
                        'test_sample': True
                    },
                    'createdAt': firestore.SERVER_TIMESTAMP
                })
                print(f"Created test document with ID: {doc_id}")
            
            print("\nSample documents created successfully!")
            time.sleep(2)  # Wait for Firestore to update
            
            # Refresh the chunk list
            chunks = db.collection('research_chunks').get()
            chunk_list = list(chunks)
            print(f"Now found {len(chunk_list)} documents in research_chunks collection")
        
        # Perform semantic search for each test query
        print("\n" + "-"*50)
        print("TESTING SEMANTIC SEARCH")
        print("-"*50)
        
        for i, query in enumerate(TEST_QUERIES):
            print(f"\nQuery {i+1}: '{query}'")
            
            # Generate embedding for the query
            print("Generating embedding for query...")
            query_embedding = generate_embedding(query)
            
            # Perform manual vector search
            print("Performing vector search...")
            results = manual_vector_search(db, query_embedding, limit=3)
            
            # Display results
            print(f"\nTop {len(results)} results:")
            for j, result in enumerate(results):
                print(f"\nResult {j+1} (similarity: {result['similarity']:.4f})")
                print(f"ID: {result['id']}")
                print(f"Text: {result['text'][:200]}..." if len(result['text']) > 200 else f"Text: {result['text']}")
                if 'metadata' in result and result['metadata']:
                    print(f"Metadata: {json.dumps(result['metadata'], indent=2)}")
            
            print("\n" + "-"*50)
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
