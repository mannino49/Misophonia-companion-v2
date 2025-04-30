#!/usr/bin/env python3

"""
Resilient Check Processed Chunks

This script checks the status of processed chunks in the Misophonia Research Vector Database
using improved Firebase connection handling to avoid the '_UnaryStreamMultiCallable' object
has no attribute '_retry' error.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from collections import Counter

import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Import our fix_firebase_connection module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fix_firebase_connection import (
    initialize_firebase,
    get_processed_chunks_count,
    get_raw_chunks_count
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds
BATCH_SIZE = 1000

def get_document_stats(db, max_retries=MAX_RETRIES):
    """Get document statistics with retry logic"""
    retries = 0
    while retries < max_retries:
        try:
            # Get document statistics
            stats_ref = db.collection('document_stats').document('global')
            stats_doc = stats_ref.get()
            
            if stats_doc.exists:
                return stats_doc.to_dict()
            else:
                logger.warning("Document stats not found")
                return {
                    "total_documents": 0,
                    "unique_authors": 0,
                    "year_range": "N/A"
                }
        except Exception as e:
            retries += 1
            logger.warning(f"Attempt {retries}/{max_retries} failed: {str(e)}")
            if retries < max_retries:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not get document stats.")
                raise

def get_processed_chunks_analysis(db, max_retries=MAX_RETRIES):
    """Get analysis of processed chunks with retry logic"""
    retries = 0
    while retries < max_retries:
        try:
            # Get processed chunks in batches
            chunks_ref = db.collection('research_chunks')
            
            # Initialize analysis variables
            doc_sources = set()
            embedding_dimensions = []
            first_created = None
            last_created = None
            
            # Process in batches
            last_doc = None
            while True:
                query = chunks_ref.limit(BATCH_SIZE)
                if last_doc:
                    query = query.start_after(last_doc)
                    
                docs = query.stream()
                batch_docs = list(docs)
                
                if not batch_docs:
                    break
                    
                for doc in batch_docs:
                    data = doc.to_dict()
                    
                    # Extract document source
                    metadata = data.get('metadata', {})
                    doc_source = metadata.get('source', 'unknown')
                    if isinstance(doc_source, list) and doc_source:
                        doc_source = doc_source[0]
                    doc_sources.add(doc_source)
                    
                    # Check embedding dimension
                    embedding = data.get('embedding', [])
                    if embedding:
                        embedding_dimensions.append(len(embedding))
                    
                    # Track creation timestamps
                    created_at = data.get('created_at')
                    if created_at:
                        if first_created is None or created_at < first_created:
                            first_created = created_at
                        if last_created is None or created_at > last_created:
                            last_created = created_at
                
                if len(batch_docs) < BATCH_SIZE:
                    break
                    
                last_doc = batch_docs[-1]
            
            # Calculate average embedding dimension
            avg_dimension = sum(embedding_dimensions) / len(embedding_dimensions) if embedding_dimensions else 0
            
            return {
                "unique_documents": len(doc_sources),
                "document_sources": list(doc_sources),
                "avg_embedding_dimension": avg_dimension,
                "first_created": first_created,
                "last_created": last_created
            }
        except Exception as e:
            retries += 1
            logger.warning(f"Attempt {retries}/{max_retries} failed: {str(e)}")
            if retries < max_retries:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retries reached. Could not analyze processed chunks.")
                raise

def main():
    print("\n==================================================")
    print("Misophonia Research Vector Database Status Check")
    print("==================================================\n")
    
    # Initialize Firebase
    db = initialize_firebase()
    
    # Get document statistics
    doc_stats = get_document_stats(db)
    print("Document Statistics:")
    print(f"Total documents: {doc_stats.get('total_documents', 'N/A')}")
    print(f"Unique authors: {doc_stats.get('unique_authors', 'N/A')}")
    print(f"Year range: {doc_stats.get('year_range', 'N/A')}\n")
    
    # Get raw and processed chunk counts
    try:
        raw_count = get_raw_chunks_count(db)
        print(f"Found {raw_count} raw chunks")
    except Exception as e:
        print(f"Error getting raw chunks count: {str(e)}")
        raw_count = 0
    
    try:
        processed_count = get_processed_chunks_count(db)
        print(f"Found {processed_count} processed chunks with embeddings")
    except Exception as e:
        print(f"Error getting processed chunks count: {str(e)}")
        processed_count = 0
    
    # Calculate embedding progress
    if raw_count > 0:
        progress = (processed_count / raw_count) * 100
        print(f"Embedding progress: {progress:.2f}%\n")
    else:
        print("Embedding progress: 0.00%\n")
    
    # Get processed chunks analysis
    try:
        analysis = get_processed_chunks_analysis(db)
        
        print("Processed Chunk Analysis:")
        print(f"Unique documents with embeddings: {analysis['unique_documents']}")
        print(f"Average embedding dimension: {analysis['avg_embedding_dimension']}")
        
        if analysis['first_created']:
            first_created = analysis['first_created'].strftime("%Y-%m-%d %H:%M:%S")
            print(f"First embedding created: {first_created}")
        
        if analysis['last_created']:
            last_created = analysis['last_created'].strftime("%Y-%m-%d %H:%M:%S")
            print(f"Last embedding created: {last_created}\n")
        
        # Show sample of documents with embeddings
        doc_sources = analysis['document_sources']
        print("Sample of documents with embeddings:")
        for i, source in enumerate(sorted(doc_sources)[:5], 1):
            print(f"  {i}. {source}")
        
        if len(doc_sources) > 5:
            print(f"  ... and {len(doc_sources) - 5} more\n")
    except Exception as e:
        print(f"Error analyzing processed chunks: {str(e)}\n")
    
    # Save report to file
    report = {
        "timestamp": datetime.now().isoformat(),
        "document_stats": doc_stats,
        "raw_chunks": raw_count,
        "processed_chunks": processed_count,
        "embedding_progress": (processed_count / raw_count) * 100 if raw_count > 0 else 0
    }
    
    if 'analysis' in locals():
        report["analysis"] = {
            "unique_documents": analysis["unique_documents"],
            "avg_embedding_dimension": analysis["avg_embedding_dimension"],
            "first_created": analysis["first_created"].isoformat() if analysis["first_created"] else None,
            "last_created": analysis["last_created"].isoformat() if analysis["last_created"] else None,
            "document_sources": analysis["document_sources"]
        }
    
    with open("vector_database_status_check.json", 'w') as f:
        json.dump(report, f, indent=2)
    
    print("Report saved to vector_database_status_check.json")

if __name__ == "__main__":
    main()
