#!/usr/bin/env python3

"""
Count Unique Documents in Firestore

This script counts the number of unique documents that have chunks with embeddings
in the Misophonia Research Vector Database.
"""

import os
import sys
import logging
from collections import Counter

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Import our fix_firebase_connection module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fix_firebase_connection import initialize_firebase

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def count_unique_documents(db, batch_size=100):
    """
    Count the number of unique documents that have chunks with embeddings
    by directly examining the document_id field in each chunk.
    """
    print("Counting unique documents with embeddings...")
    
    # Get processed chunks in batches
    chunks_ref = db.collection('research_chunks')
    
    # Track unique documents
    unique_docs = set()
    processed_count = 0
    
    # Process in batches
    last_doc = None
    while True:
        query = chunks_ref.limit(batch_size)
        if last_doc:
            query = query.start_after(last_doc)
            
        docs = list(query.stream())
        
        if not docs:
            break
            
        for doc in docs:
            processed_count += 1
            data = doc.to_dict()
            
            # Extract document ID from chunk ID or metadata
            chunk_id = doc.id
            metadata = data.get('metadata', {})
            
            # Try to get document ID from metadata
            doc_id = metadata.get('document_id')
            
            # If not in metadata, try to extract from chunk_id
            if not doc_id and '_' in chunk_id:
                # Assuming format like doc_1_1_AuthorName_Year_...
                parts = chunk_id.split('_')
                if len(parts) >= 5:
                    doc_id = '_'.join(parts[:5])  # Use first 5 parts as doc ID
            
            # If we found a document ID, add it to our set
            if doc_id:
                unique_docs.add(doc_id)
            
            # Also check for source field which might contain document title
            source = metadata.get('source')
            if source:
                if isinstance(source, list) and source:
                    source = source[0]
                if source and source != 'unknown':
                    unique_docs.add(source)
        
        print(f"Processed {processed_count} chunks, found {len(unique_docs)} unique documents so far")
        
        if len(docs) < batch_size:
            break
            
        last_doc = docs[-1]
    
    # Count document sources
    doc_sources = Counter()
    for doc_id in unique_docs:
        if isinstance(doc_id, str):
            # Extract author name if possible
            if '_' in doc_id:
                parts = doc_id.split('_')
                if len(parts) >= 4:
                    author = parts[3]  # Assuming format with author at index 3
                    doc_sources[author] += 1
    
    return {
        "total_chunks_processed": processed_count,
        "unique_documents": len(unique_docs),
        "unique_document_ids": list(unique_docs)[:10],  # Show first 10 for sample
        "top_authors": doc_sources.most_common(5)
    }

def main():
    print("\n==================================================")
    print("Misophonia Research Document Count")
    print("==================================================\n")
    
    # Initialize Firebase
    db = initialize_firebase()
    
    # Count unique documents
    results = count_unique_documents(db)
    
    print("\n==================================================")
    print("Results:")
    print("==================================================\n")
    print(f"Total chunks processed: {results['total_chunks_processed']}")
    print(f"Unique documents with embeddings: {results['unique_documents']}")
    
    if results['unique_document_ids']:
        print("\nSample document IDs:")
        for i, doc_id in enumerate(results['unique_document_ids'], 1):
            print(f"  {i}. {doc_id}")
    
    if results['top_authors']:
        print("\nTop authors:")
        for author, count in results['top_authors']:
            print(f"  {author}: {count} documents")

if __name__ == "__main__":
    main()
