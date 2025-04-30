#!/usr/bin/env python3

"""
Diagnose and Fix Vector Database Issues

This script diagnoses and attempts to fix issues with the vector database:
1. Checks for stalled embedding generation
2. Verifies Cloud Function health
3. Attempts to manually trigger embedding generation for a sample of chunks
"""

import os
import time
import json
import random
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from tabulate import tabulate
import argparse

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

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
            chunk_data = chunk.to_dict()
            if 'raw_chunk_id' in chunk_data:
                processed_chunk_ids.add(chunk_data['raw_chunk_id'])
        
        print(f"Found {len(processed_chunk_ids)} processed chunk IDs")
        
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

def check_cloud_function_health(db):
    """
    Check if Cloud Functions are healthy by looking at recent embedding generation.
    """
    try:
        # Get most recent processed chunks
        chunks_query = db.collection('research_chunks').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(5)
        chunks = chunks_query.get()
        
        if not chunks:
            print("No processed chunks found. Cloud Functions may not be working.")
            return False
        
        # Check creation times
        now = datetime.now()
        for chunk in chunks:
            chunk_data = chunk.to_dict()
            if 'createdAt' in chunk_data:
                created_at = chunk_data['createdAt']
                if isinstance(created_at, datetime):
                    time_diff = now - created_at
                    print(f"Most recent embedding was created {time_diff.total_seconds() / 3600:.2f} hours ago")
                    
                    # If the most recent embedding was created within the last 24 hours, consider functions healthy
                    if time_diff < timedelta(hours=24):
                        print("Cloud Functions appear to be working (recent embeddings found)")
                        return True
        
        print("No recent embeddings found. Cloud Functions may be stalled.")
        return False
    except Exception as e:
        print(f"Error checking Cloud Function health: {e}")
        return False

def manually_trigger_embedding_generation(db, chunk, update_timestamp=True):
    """
    Manually trigger embedding generation for a chunk by updating it.
    """
    try:
        chunk_ref = db.collection('research_chunks_raw').document(chunk.id)
        chunk_data = chunk.to_dict()
        
        if update_timestamp:
            # Update the timestamp to trigger the Cloud Function
            chunk_data['updatedAt'] = firestore.SERVER_TIMESTAMP
        
        # Add a flag to indicate manual triggering
        chunk_data['manually_triggered'] = True
        
        # Update the document
        chunk_ref.set(chunk_data, merge=True)
        
        print(f"Manually triggered embedding generation for chunk {chunk.id}")
        return True
    except Exception as e:
        print(f"Error triggering embedding generation for chunk {chunk.id}: {e}")
        return False

def check_for_duplicate_chunks(db):
    """
    Check for duplicate chunks in the raw chunks collection.
    """
    try:
        # Get all raw chunks
        raw_chunks_query = db.collection('research_chunks_raw').limit(1000)
        raw_chunks = raw_chunks_query.get()
        
        # Check for duplicates based on content hash or text
        content_hashes = {}
        duplicates = []
        
        for chunk in raw_chunks:
            chunk_data = chunk.to_dict()
            content_hash = chunk_data.get('content_hash')
            text = chunk_data.get('text')
            
            if content_hash and content_hash in content_hashes:
                duplicates.append((chunk.id, content_hash, 'content_hash'))
            elif text and text in content_hashes:
                duplicates.append((chunk.id, text[:50], 'text'))
            
            if content_hash:
                content_hashes[content_hash] = chunk.id
            if text:
                content_hashes[text] = chunk.id
        
        if duplicates:
            print(f"Found {len(duplicates)} duplicate chunks")
            for chunk_id, match_value, match_type in duplicates[:5]:
                print(f"  - {chunk_id} (duplicate {match_type}: {match_value}...)")
            if len(duplicates) > 5:
                print(f"  ... and {len(duplicates) - 5} more")
        else:
            print("No duplicate chunks found")
        
        return duplicates
    except Exception as e:
        print(f"Error checking for duplicate chunks: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Diagnose and fix vector database issues')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix issues by manually triggering embedding generation')
    parser.add_argument('--sample-size', type=int, default=10, help='Number of chunks to manually trigger')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    print("\n==================================================")
    print("Misophonia Research Vector Database Diagnostics")
    print("==================================================\n")
    
    # Check Cloud Function health
    print("Checking Cloud Function health...")
    cloud_functions_healthy = check_cloud_function_health(db)
    print()
    
    # Check for duplicate chunks
    print("Checking for duplicate chunks...")
    duplicates = check_for_duplicate_chunks(db)
    print()
    
    # Get unprocessed chunks
    print("Checking for unprocessed chunks...")
    unprocessed_chunks = get_raw_chunks_without_embeddings(db, limit=1000)
    print()
    
    # If requested, attempt to fix issues
    if args.fix and unprocessed_chunks:
        print(f"Attempting to manually trigger embedding generation for {args.sample_size} chunks...")
        
        # Select a random sample of unprocessed chunks
        sample_size = min(args.sample_size, len(unprocessed_chunks))
        sample = random.sample(unprocessed_chunks, sample_size)
        
        # Manually trigger embedding generation
        success_count = 0
        for chunk in sample:
            if manually_trigger_embedding_generation(db, chunk):
                success_count += 1
        
        print(f"Successfully triggered embedding generation for {success_count} out of {sample_size} chunks")
        print("Wait a few minutes and then check if new embeddings are being generated")
    
    # Provide recommendations
    print("\n==================================================")
    print("Recommendations:")
    print("==================================================\n")
    
    if not cloud_functions_healthy:
        print("1. Check Cloud Function logs for errors")
        print("2. Verify that the OpenAI API key is valid and has sufficient quota")
        print("3. Consider redeploying the Cloud Functions")
    
    if duplicates:
        print("4. Consider removing duplicate chunks to reduce processing overhead")
    
    if unprocessed_chunks:
        print("5. Run this script with --fix to manually trigger embedding generation")
        print("6. Consider increasing the memory allocation for the generateEmbeddings function")
    
    print("7. For the semanticSearch function, increase memory beyond 1GB (e.g., to 2GB or 4GB)")
    print("8. Consider implementing pagination or limiting the number of chunks processed in each search")

if __name__ == "__main__":
    main()
