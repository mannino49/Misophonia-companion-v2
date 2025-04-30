#!/usr/bin/env python3

"""
Resilient Batch Embedding Generator

This script generates embeddings for batches of document chunks with improved
Firebase connection handling to avoid the '_UnaryStreamMultiCallable' object
has no attribute '_retry' error.
"""

import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import firebase_admin
from firebase_admin import credentials, firestore
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

# Import our fix_firebase_connection module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fix_firebase_connection import (
    initialize_firebase,
    get_processed_chunks_count,
    get_raw_chunks_count,
    get_unprocessed_chunks
)

# Load environment variables
load_dotenv()

# Configure OpenAI API
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds
EMBEDDING_MODEL = "text-embedding-ada-002"
BATCH_COMMIT_SIZE = 20

def generate_embedding(text):
    """Generate an embedding for the given text using OpenAI API"""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text
            )
            embedding = response.data[0].embedding
            return embedding
        except Exception as e:
            retries += 1
            logger.warning(f"Embedding generation attempt {retries}/{MAX_RETRIES} failed: {str(e)}")
            if retries < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not generate embedding.")
                raise

def process_chunk(chunk_doc):
    """Process a single chunk document to generate its embedding"""
    try:
        chunk_data = chunk_doc.to_dict()
        chunk_id = chunk_doc.id
        chunk_text = chunk_data.get('text', '')
        
        if not chunk_text:
            logger.warning(f"Chunk {chunk_id} has no text content")
            return None
        
        # Generate embedding
        embedding = generate_embedding(chunk_text)
        
        # Prepare processed chunk data
        processed_chunk = {
            'id': chunk_id,
            'text': chunk_text,
            'embedding': embedding,
            'metadata': chunk_data.get('metadata', {}),
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        return processed_chunk
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_doc.id}: {str(e)}")
        return None

def store_processed_chunks(db, processed_chunks):
    """Store processed chunks in Firestore with retry logic"""
    if not processed_chunks:
        logger.warning("No processed chunks to store")
        return 0
    
    # Split into batches for committing
    batches = [processed_chunks[i:i + BATCH_COMMIT_SIZE] 
               for i in range(0, len(processed_chunks), BATCH_COMMIT_SIZE)]
    
    total_stored = 0
    for batch_idx, batch in enumerate(batches):
        retries = 0
        while retries < MAX_RETRIES:
            try:
                # Create a batch
                batch_write = db.batch()
                
                # Add each document to the batch
                for chunk in batch:
                    doc_ref = db.collection('research_chunks').document(chunk['id'])
                    batch_write.set(doc_ref, chunk)
                
                # Commit the batch
                batch_write.commit()
                logger.info(f"Committed batch {batch_idx + 1}/{len(batches)} of {len(batch)} chunks")
                total_stored += len(batch)
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Batch commit attempt {retries}/{MAX_RETRIES} failed: {str(e)}")
                if retries < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Max retries reached. Could not commit batch {batch_idx + 1}.")
                    raise
    
    return total_stored

def main():
    parser = argparse.ArgumentParser(description='Generate embeddings for document chunks in batches')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of chunks to process in a batch')
    parser.add_argument('--workers', type=int, default=5, help='Number of worker threads')
    parser.add_argument('--skip', type=int, default=0, help='Number of chunks to skip')
    args = parser.parse_args()
    
    print("\n==================================================")
    print("Resilient Batch Embedding Generator")
    print("==================================================\n")
    
    # Initialize Firebase
    print("Initializing Firebase with service account: ./service-account.json")
    db = initialize_firebase()
    
    # Get processed chunks count
    print("\nFetching processed chunk IDs...")
    processed_count = get_processed_chunks_count(db)
    print(f"Found {processed_count} processed chunks with embeddings")
    
    # Get raw chunks with pagination
    print(f"Fetching raw chunks (limit: {args.batch_size}, skip: {args.skip})...")
    unprocessed_chunks = get_unprocessed_chunks(db, skip=args.skip, limit=args.batch_size)
    print(f"Found {len(unprocessed_chunks)} unprocessed chunks (out of {args.batch_size} fetched)")
    
    if not unprocessed_chunks:
        print("No unprocessed chunks found. Exiting.")
        return
    
    # Process chunks
    print(f"\nProcessing {len(unprocessed_chunks)} chunks with {args.workers} workers...")
    processed_chunks = []
    failed_chunks = []
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(process_chunk, chunk) for chunk in unprocessed_chunks]
        
        # Show progress bar
        for future in tqdm(futures, desc="Processing chunks", unit="chunk"):
            result = future.result()
            if result:
                processed_chunks.append(result)
            else:
                failed_chunks.append(result)
    
    print(f"\nProcessing complete: {len(processed_chunks)} successes, {len(failed_chunks)} failures\n")
    
    # Store processed chunks
    print("Storing processed chunks in Firestore...")
    stored_count = store_processed_chunks(db, processed_chunks)
    print(f"Storage complete: {stored_count} stored, {len(processed_chunks) - stored_count} errors\n")
    
    # Generate report
    print("==================================================")
    print("Batch Processing Results:")
    print("==================================================\n")
    print(f"Batch size: {args.batch_size}")
    print(f"Skip: {args.skip}")
    print(f"Workers: {args.workers}")
    print(f"Processed: {len(processed_chunks)}")
    print(f"Success rate: {(len(processed_chunks) / len(unprocessed_chunks) * 100):.2f}%\n")
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"batch_embedding_report_{timestamp}.json"
    report = {
        "timestamp": timestamp,
        "batch_size": args.batch_size,
        "skip": args.skip,
        "workers": args.workers,
        "processed_count": len(processed_chunks),
        "failed_count": len(failed_chunks),
        "success_rate": len(processed_chunks) / len(unprocessed_chunks) if unprocessed_chunks else 0,
        "total_processed_chunks": processed_count + len(processed_chunks)
    }
    
    with open(report_filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"Report saved to {report_filename}")

if __name__ == "__main__":
    main()
