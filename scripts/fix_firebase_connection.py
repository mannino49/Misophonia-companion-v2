#!/usr/bin/env python3

"""
Fix Firebase Connection Issues

This script resolves the '_UnaryStreamMultiCallable' object has no attribute '_retry' error
by implementing a more resilient connection handling approach for Firestore operations.
"""

import os
import time
import firebase_admin
from firebase_admin import credentials, firestore
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds

def initialize_firebase():
    """Initialize Firebase with proper error handling"""
    try:
        # Check if already initialized
        if not firebase_admin._apps:
            cred = credentials.Certificate('./service-account.json')
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        logger.info("Firebase connection initialized successfully")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
        raise

def get_processed_chunks_count(db, max_retries=MAX_RETRIES):
    """Get processed chunks count with retry logic"""
    retries = 0
    while retries < max_retries:
        try:
            # Use a smaller limit to avoid timeout issues
            chunks_ref = db.collection('research_chunks')
            # Count documents in smaller batches
            total_count = 0
            batch_size = 1000
            last_doc = None
            
            while True:
                query = chunks_ref.limit(batch_size)
                if last_doc:
                    query = query.start_after(last_doc)
                    
                docs = query.stream()
                batch_docs = list(docs)
                batch_count = len(batch_docs)
                
                if batch_count == 0:
                    break
                    
                total_count += batch_count
                if batch_count < batch_size:
                    break
                    
                last_doc = batch_docs[-1]
            
            logger.info(f"Successfully counted {total_count} processed chunks")
            return total_count
        except Exception as e:
            retries += 1
            logger.warning(f"Attempt {retries}/{max_retries} failed: {str(e)}")
            if retries < max_retries:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not get processed chunks count.")
                raise

def get_raw_chunks_count(db, max_retries=MAX_RETRIES):
    """Get raw chunks count with retry logic"""
    retries = 0
    while retries < max_retries:
        try:
            # Use a smaller limit to avoid timeout issues
            chunks_ref = db.collection('research_chunks_raw')
            # Count documents in smaller batches
            total_count = 0
            batch_size = 1000
            last_doc = None
            
            while True:
                query = chunks_ref.limit(batch_size)
                if last_doc:
                    query = query.start_after(last_doc)
                    
                docs = query.stream()
                batch_docs = list(docs)
                batch_count = len(batch_docs)
                
                if batch_count == 0:
                    break
                    
                total_count += batch_count
                if batch_count < batch_size:
                    break
                    
                last_doc = batch_docs[-1]
            
            logger.info(f"Successfully counted {total_count} raw chunks")
            return total_count
        except Exception as e:
            retries += 1
            logger.warning(f"Attempt {retries}/{max_retries} failed: {str(e)}")
            if retries < max_retries:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not get raw chunks count.")
                raise

def get_unprocessed_chunks(db, skip=0, limit=50, max_retries=MAX_RETRIES):
    """Get unprocessed chunks with retry logic"""
    processed_ids = set()
    unprocessed_chunks = []
    
    # Get processed chunk IDs with retry
    retries = 0
    while retries < max_retries:
        try:
            # Get processed chunk IDs in batches to avoid timeout
            chunks_ref = db.collection('research_chunks')
            batch_size = 1000
            last_doc = None
            
            while True:
                query = chunks_ref.limit(batch_size)
                if last_doc:
                    query = query.start_after(last_doc)
                    
                docs = query.stream()
                batch_docs = list(docs)
                
                if not batch_docs:
                    break
                    
                for doc in batch_docs:
                    processed_ids.add(doc.id)
                    
                if len(batch_docs) < batch_size:
                    break
                    
                last_doc = batch_docs[-1]
            
            logger.info(f"Retrieved {len(processed_ids)} processed chunk IDs")
            break
        except Exception as e:
            retries += 1
            logger.warning(f"Attempt {retries}/{max_retries} to get processed IDs failed: {str(e)}")
            if retries < max_retries:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not get processed chunk IDs.")
                raise
    
    # Get raw chunks with retry
    retries = 0
    while retries < max_retries:
        try:
            # Get raw chunks in smaller batches
            raw_ref = db.collection('research_chunks_raw')
            
            # We need to implement skip manually to avoid large offset issues
            if skip > 0:
                # Get chunks in batches until we reach the skip point
                remaining_skip = skip
                batch_size = min(1000, remaining_skip)
                last_doc = None
                
                while remaining_skip > 0:
                    query = raw_ref.limit(batch_size)
                    if last_doc:
                        query = query.start_after(last_doc)
                        
                    docs = query.stream()
                    batch_docs = list(docs)
                    
                    if not batch_docs:
                        logger.warning(f"Not enough documents to skip {skip}")
                        return []
                        
                    batch_count = len(batch_docs)
                    remaining_skip -= batch_count
                    
                    if remaining_skip <= 0:
                        # We've reached our skip point
                        if remaining_skip < 0:
                            # We need to use the last few docs from this batch
                            start_idx = batch_count + remaining_skip
                            last_doc = batch_docs[start_idx - 1]
                        else:
                            last_doc = batch_docs[-1]
                    else:
                        last_doc = batch_docs[-1]
                        
                    if batch_count < batch_size:
                        if remaining_skip > 0:
                            logger.warning(f"Not enough documents to skip {skip}")
                            return []
                        break
            else:
                last_doc = None
            
            # Now get the actual chunks we want
            query = raw_ref.limit(limit)
            if last_doc:
                query = query.start_after(last_doc)
                
            docs = query.stream()
            raw_chunks = list(docs)
            
            # Filter out processed chunks
            for doc in raw_chunks:
                if doc.id not in processed_ids:
                    unprocessed_chunks.append(doc)
                    if len(unprocessed_chunks) >= limit:
                        break
            
            logger.info(f"Found {len(unprocessed_chunks)} unprocessed chunks")
            return unprocessed_chunks
        except Exception as e:
            retries += 1
            logger.warning(f"Attempt {retries}/{max_retries} to get raw chunks failed: {str(e)}")
            if retries < max_retries:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not get raw chunks.")
                raise

def test_connection():
    """Test the Firebase connection with the new resilient methods"""
    print("\n==================================================")
    print("Testing Firebase Connection")
    print("==================================================\n")
    
    db = initialize_firebase()
    
    # Test getting processed chunks count
    try:
        processed_count = get_processed_chunks_count(db)
        print(f"Processed chunks count: {processed_count}")
    except Exception as e:
        print(f"Error getting processed chunks count: {str(e)}")
    
    # Test getting raw chunks count
    try:
        raw_count = get_raw_chunks_count(db)
        print(f"Raw chunks count: {raw_count}")
    except Exception as e:
        print(f"Error getting raw chunks count: {str(e)}")
    
    # Test getting unprocessed chunks
    try:
        unprocessed = get_unprocessed_chunks(db, skip=7800, limit=10)
        print(f"Retrieved {len(unprocessed)} unprocessed chunks")
        if unprocessed:
            print(f"First unprocessed chunk ID: {unprocessed[0].id}")
    except Exception as e:
        print(f"Error getting unprocessed chunks: {str(e)}")
    
    print("\nConnection test complete!")

if __name__ == "__main__":
    test_connection()
