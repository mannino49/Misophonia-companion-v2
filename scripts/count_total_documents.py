#!/usr/bin/env python3

import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
import logging
import argparse
from tqdm import tqdm
import json
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Firebase
def initialize_firebase():
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Initialize with service account
        service_account_path = './service-account.json'
        if not os.path.exists(service_account_path):
            logger.error(f"Service account file not found at {service_account_path}")
            sys.exit(1)
            
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        
    return firestore.client()

def count_total_documents():
    print("\n==================================================")
    print("Misophonia Research Total Document Count")
    print("==================================================\n")
    
    db = initialize_firebase()
    
    # Get all raw chunks to analyze total documents
    try:
        raw_chunks_ref = db.collection('research_chunks_raw')
        raw_chunks = raw_chunks_ref.stream()
        
        # Track unique document IDs
        all_doc_ids = set()
        doc_id_pattern = re.compile(r'^([^_]+)(?:_\d+)?$')
        
        # Process chunks to extract document IDs
        chunk_count = 0
        for chunk in tqdm(raw_chunks, desc="Analyzing raw chunks", unit="chunk"):
            chunk_count += 1
            chunk_data = chunk.to_dict()
            
            # Extract document ID from metadata if available
            if 'metadata' in chunk_data and 'document_id' in chunk_data['metadata']:
                doc_id = chunk_data['metadata']['document_id']
                all_doc_ids.add(doc_id)
            else:
                # Try to extract from chunk ID
                chunk_id = chunk.id
                match = doc_id_pattern.match(chunk_id)
                if match:
                    doc_id = match.group(1)
                    all_doc_ids.add(doc_id)
            
            # Print progress every 1000 chunks
            if chunk_count % 1000 == 0:
                print(f"Processed {chunk_count} chunks, found {len(all_doc_ids)} unique documents so far")
        
        print("\n==================================================")
        print("Results:")
        print("==================================================\n")
        
        print(f"Total raw chunks: {chunk_count}")
        print(f"Total unique documents in collection: {len(all_doc_ids)}")
        
        # Print sample document IDs
        print("\nSample document IDs:")
        sample_ids = list(all_doc_ids)[:10] if len(all_doc_ids) > 10 else list(all_doc_ids)
        for i, doc_id in enumerate(sample_ids, 1):
            print(f"  {i}. {doc_id}")
            
    except Exception as e:
        logger.error(f"Error counting documents: {e}")
        return None

if __name__ == "__main__":
    count_total_documents()
