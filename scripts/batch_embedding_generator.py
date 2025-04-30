#!/usr/bin/env python3

"""
Batch Embedding Generator

This script generates embeddings for large batches of chunks in the research_chunks_raw collection.
It uses parallel processing and rate limiting to efficiently generate embeddings at scale.
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
from tqdm import tqdm
import argparse
import openai
import concurrent.futures
import numpy as np

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

def get_unprocessed_chunks(db, limit=1000, skip=0):
    """
    Get chunks from research_chunks_raw that don't have corresponding processed chunks.
    """
    try:
        # Get all processed chunk IDs
        print("Fetching processed chunk IDs...")
        processed_chunks_query = db.collection('research_chunks').limit(10000)
        processed_chunks = processed_chunks_query.get()
        processed_chunk_ids = set()
        
        for chunk in processed_chunks:
            processed_chunk_ids.add(chunk.id)
        
        print(f"Found {len(processed_chunk_ids)} processed chunks with embeddings")
        
        # Get raw chunks that don't have corresponding processed chunks
        print(f"Fetching raw chunks (limit: {limit}, skip: {skip})...")
        raw_chunks_query = db.collection('research_chunks_raw').limit(limit).offset(skip)
        raw_chunks = raw_chunks_query.get()
        
        unprocessed_chunks = []
        for chunk in raw_chunks:
            if chunk.id not in processed_chunk_ids:
                unprocessed_chunks.append(chunk)
        
        print(f"Found {len(unprocessed_chunks)} unprocessed chunks (out of {len(raw_chunks)} fetched)")
        
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

def process_chunk(chunk):
    """
    Process a single chunk by generating an embedding and preparing data for storage.
    This function is designed to be used with concurrent.futures for parallel processing.
    """
    try:
        # Get chunk data
        chunk_id = chunk.id
        chunk_data = chunk.to_dict()
        chunk_text = chunk_data.get('text', '')
        
        if not chunk_text:
            return {
                'success': False,
                'chunk_id': chunk_id,
                'error': 'Empty text',
                'data': None
            }
        
        # Generate embedding
        embedding = generate_embedding(chunk_text)
        
        if not embedding:
            return {
                'success': False,
                'chunk_id': chunk_id,
                'error': 'Failed to generate embedding',
                'data': None
            }
        
        # Prepare data for storage
        processed_data = {
            'text': chunk_text,
            'embedding': embedding,
            'metadata': chunk_data.get('metadata', {}),
            'raw_chunk_id': chunk_id,
            'createdAt': firestore.SERVER_TIMESTAMP,
            'manually_processed': True
        }
        
        return {
            'success': True,
            'chunk_id': chunk_id,
            'error': None,
            'data': processed_data
        }
    except Exception as e:
        return {
            'success': False,
            'chunk_id': chunk_id if 'chunk_id' in locals() else 'unknown',
            'error': str(e),
            'data': None
        }

def store_processed_chunks(db, results):
    """
    Store processed chunks in Firestore.
    """
    success_count = 0
    error_count = 0
    
    # Use a batch write for efficiency
    batch = db.batch()
    batch_count = 0
    batch_size = 20  # Smaller batch size to avoid deadline exceeded errors
    
    for result in tqdm(results, desc="Storing chunks"):
        if result['success']:
            # Add to batch
            chunk_ref = db.collection('research_chunks').document(result['chunk_id'])
            batch.set(chunk_ref, result['data'])
            batch_count += 1
            success_count += 1
            
            # Commit batch if it reaches the maximum size
            if batch_count >= batch_size:
                batch.commit()
                print(f"Committed batch of {batch_count} chunks")
                batch = db.batch()
                batch_count = 0
        else:
            error_count += 1
            print(f"Error with chunk {result['chunk_id']}: {result['error']}")
    
    # Commit any remaining chunks in the batch
    if batch_count > 0:
        batch.commit()
        print(f"Committed final batch of {batch_count} chunks")
    
    return success_count, error_count

def process_chunks_in_parallel(chunks, max_workers=5):
    """
    Process chunks in parallel using ThreadPoolExecutor.
    """
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_chunk = {executor.submit(process_chunk, chunk): chunk for chunk in chunks}
        
        # Process results as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_chunk), total=len(chunks), desc="Processing chunks"):
            chunk = future_to_chunk[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'chunk_id': chunk.id,
                    'error': str(e),
                    'data': None
                })
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for chunks in batch')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of chunks to process in each batch')
    parser.add_argument('--skip', type=int, default=0, help='Number of chunks to skip')
    parser.add_argument('--workers', type=int, default=5, help='Number of parallel workers')
    parser.add_argument('--dry-run', action='store_true', help='Process chunks but do not store results')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    print("\n==================================================")
    print("Batch Embedding Generator")
    print("==================================================\n")
    
    # Get unprocessed chunks
    unprocessed_chunks = get_unprocessed_chunks(db, limit=args.batch_size, skip=args.skip)
    
    if not unprocessed_chunks:
        print("No unprocessed chunks found. Exiting.")
        return
    
    # Process chunks in parallel
    print(f"\nProcessing {len(unprocessed_chunks)} chunks with {args.workers} workers...")
    results = process_chunks_in_parallel(unprocessed_chunks, max_workers=args.workers)
    
    # Count successes and failures
    success_count = sum(1 for result in results if result['success'])
    error_count = len(results) - success_count
    
    print(f"\nProcessing complete: {success_count} successes, {error_count} failures")
    
    # Store processed chunks if not a dry run
    if not args.dry_run:
        print("\nStoring processed chunks in Firestore...")
        store_success, store_error = store_processed_chunks(db, results)
        print(f"Storage complete: {store_success} stored, {store_error} errors")
    else:
        print("\nDry run - skipping storage step")
    
    # Print final statistics
    print("\n==================================================")
    print("Batch Processing Results:")
    print("==================================================\n")
    print(f"Batch size: {args.batch_size}")
    print(f"Skip: {args.skip}")
    print(f"Workers: {args.workers}")
    print(f"Processed: {len(results)}")
    print(f"Success rate: {success_count / len(results) * 100:.2f}%")
    
    # Save report to file
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'batch_size': args.batch_size,
        'skip': args.skip,
        'workers': args.workers,
        'processed': len(results),
        'success_count': success_count,
        'error_count': error_count,
        'success_rate': success_count / len(results) if results else 0,
    }
    
    report_filename = f"batch_embedding_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {report_filename}")

if __name__ == "__main__":
    main()
