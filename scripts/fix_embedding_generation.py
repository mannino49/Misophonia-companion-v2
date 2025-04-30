#!/usr/bin/env python3

"""
Fix Embedding Generation

This script addresses issues with embedding generation by:
1. Checking for chunks without embeddings
2. Manually generating embeddings for a sample of chunks
3. Updating the database with the generated embeddings
"""

import os
import time
import json
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from tabulate import tabulate
import argparse
import openai
from tqdm import tqdm

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

def get_raw_chunks_without_embeddings(db, limit=100):
    """
    Get raw chunks that don't have corresponding processed chunks with embeddings.
    """
    try:
        # Get all processed chunk IDs
        processed_chunks_query = db.collection('research_chunks').limit(10000)
        processed_chunks = processed_chunks_query.get()
        processed_chunk_ids = set()
        
        for chunk in processed_chunks:
            processed_chunk_ids.add(chunk.id)
        
        print(f"Found {len(processed_chunk_ids)} processed chunks with embeddings")
        
        # Get raw chunks that don't have corresponding processed chunks
        raw_chunks_query = db.collection('research_chunks_raw').limit(limit)
        raw_chunks = raw_chunks_query.get()
        
        unprocessed_chunks = []
        for chunk in raw_chunks:
            if chunk.id not in processed_chunk_ids:
                unprocessed_chunks.append(chunk)
        
        print(f"Found {len(unprocessed_chunks)} raw chunks without embeddings (out of {len(raw_chunks)} checked)")
        
        return unprocessed_chunks
    except Exception as e:
        print(f"Error getting unprocessed chunks: {e}")
        return []

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

def manually_process_chunks(db, chunks, batch_size=5):
    """
    Manually process chunks by generating embeddings and storing them in Firestore.
    """
    success_count = 0
    error_count = 0
    
    # Process chunks in batches to avoid rate limiting
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}...")
        
        for chunk in tqdm(batch):
            try:
                # Get chunk data
                chunk_data = chunk.to_dict()
                chunk_text = chunk_data.get('text', '')
                
                if not chunk_text:
                    print(f"Warning: Empty text for chunk {chunk.id}")
                    error_count += 1
                    continue
                
                # Generate embedding
                embedding = generate_embedding(chunk_text)
                
                if not embedding:
                    print(f"Error: Failed to generate embedding for chunk {chunk.id}")
                    error_count += 1
                    continue
                
                # Store the chunk with embedding in the research_chunks collection
                db.collection('research_chunks').document(chunk.id).set({
                    'text': chunk_text,
                    'embedding': embedding,
                    'metadata': chunk_data.get('metadata', {}),
                    'raw_chunk_id': chunk.id,
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    'manually_processed': True
                })
                
                success_count += 1
                print(f"Successfully processed chunk {chunk.id} with embedding dimension {len(embedding)}")
            except Exception as e:
                print(f"Error processing chunk {chunk.id}: {e}")
                error_count += 1
        
        # Wait between batches to avoid rate limiting
        if i + batch_size < len(chunks):
            print(f"Waiting 5 seconds before next batch...")
            time.sleep(5)
    
    return success_count, error_count

def main():
    parser = argparse.ArgumentParser(description='Fix embedding generation issues')
    parser.add_argument('--sample-size', type=int, default=20, help='Number of chunks to manually process')
    parser.add_argument('--batch-size', type=int, default=5, help='Number of chunks to process in each batch')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    print("\n==================================================")
    print("Fixing Embedding Generation Issues")
    print("==================================================\n")
    
    # Get unprocessed chunks
    print("Checking for unprocessed chunks...")
    unprocessed_chunks = get_raw_chunks_without_embeddings(db, limit=1000)
    
    if not unprocessed_chunks:
        print("No unprocessed chunks found. Exiting.")
        return
    
    # Select a random sample of unprocessed chunks
    sample_size = min(args.sample_size, len(unprocessed_chunks))
    sample = random.sample(unprocessed_chunks, sample_size)
    
    print(f"\nSelected {sample_size} chunks for manual processing")
    
    # Manually process chunks
    print("\nManually processing chunks...")
    success_count, error_count = manually_process_chunks(db, sample, batch_size=args.batch_size)
    
    print("\n==================================================")
    print("Processing Results:")
    print("==================================================\n")
    print(f"Successfully processed: {success_count} chunks")
    print(f"Failed to process: {error_count} chunks")
    print(f"Success rate: {success_count / sample_size * 100:.2f}%")
    
    # Check for newly processed chunks
    print("\nChecking for newly processed chunks...")
    processed_chunks_query = db.collection('research_chunks').where('manually_processed', '==', True).get()
    print(f"Found {len(processed_chunks_query)} manually processed chunks")

if __name__ == "__main__":
    main()
