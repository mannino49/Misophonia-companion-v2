#!/usr/bin/env python3

"""
Check Processed Chunks Script

This script checks the actual number of processed chunks in the Firestore database
and provides detailed information about the embedding generation progress.
"""

import os
import time
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from tabulate import tabulate

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
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

def get_all_processed_chunks(db, limit=10000):
    """
    Get all processed chunks from the research_chunks collection.
    """
    try:
        # Get processed chunks
        chunks_query = db.collection('research_chunks').limit(limit)
        chunks = chunks_query.get()
        
        print(f"Found {len(chunks)} processed chunks with embeddings")
        
        return chunks
    except Exception as e:
        print(f"Error getting processed chunks: {e}")
        return []

def get_all_raw_chunks(db, limit=10000):
    """
    Get all raw chunks from the research_chunks_raw collection.
    """
    try:
        # Get raw chunks
        chunks_query = db.collection('research_chunks_raw').limit(limit)
        chunks = chunks_query.get()
        
        print(f"Found {len(chunks)} raw chunks")
        
        return chunks
    except Exception as e:
        print(f"Error getting raw chunks: {e}")
        return []

def analyze_processed_chunks(processed_chunks):
    """
    Analyze processed chunks to extract useful information.
    """
    if not processed_chunks:
        return {}
    
    # Extract document IDs
    document_ids = set()
    embedding_dimensions = []
    creation_times = []
    
    for chunk in processed_chunks:
        chunk_data = chunk.to_dict()
        
        # Extract document ID
        if 'metadata' in chunk_data and 'document_id' in chunk_data['metadata']:
            document_ids.add(chunk_data['metadata']['document_id'])
        
        # Extract embedding dimensions
        if 'embedding' in chunk_data:
            embedding_dimensions.append(len(chunk_data['embedding']))
        
        # Extract creation time
        if 'createdAt' in chunk_data:
            creation_time = chunk_data['createdAt']
            if hasattr(creation_time, 'timestamp'):
                creation_times.append(creation_time.timestamp())
    
    # Calculate statistics
    avg_dimension = sum(embedding_dimensions) / len(embedding_dimensions) if embedding_dimensions else 0
    
    # Sort creation times
    creation_times.sort()
    
    # Convert timestamps to datetime strings
    creation_dates = [datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') for ts in creation_times]
    
    return {
        'unique_documents': len(document_ids),
        'document_ids': list(document_ids),
        'avg_embedding_dimension': avg_dimension,
        'first_created': creation_dates[0] if creation_dates else None,
        'last_created': creation_dates[-1] if creation_dates else None,
    }

def get_document_stats(db):
    """
    Get statistics about documents in the database.
    """
    try:
        # Get document count
        docs_query = db.collection('research_documents')
        docs = docs_query.get()
        
        # Extract unique authors and years
        authors = set()
        years = set()
        
        for doc in docs:
            doc_data = doc.to_dict()
            metadata = doc_data.get('metadata', {})
            
            # Add author
            author = metadata.get('primary_author')
            if author:
                authors.add(author)
            
            # Add year
            year = metadata.get('year')
            if year:
                years.add(year)
        
        # Calculate year range
        year_range = f"{min(years)} - {max(years)}" if years else "Unknown"
        
        return {
            'document_count': len(docs),
            'author_count': len(authors),
            'year_range': year_range,
        }
    except Exception as e:
        print(f"Error getting document stats: {e}")
        return {}

def main():
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    print("\n==================================================")
    print("Misophonia Research Vector Database Status Check")
    print("==================================================\n")
    
    # Get document statistics
    doc_stats = get_document_stats(db)
    print(f"Document Statistics:")
    print(f"Total documents: {doc_stats.get('document_count', 'Unknown')}")
    print(f"Unique authors: {doc_stats.get('author_count', 'Unknown')}")
    print(f"Year range: {doc_stats.get('year_range', 'Unknown')}\n")
    
    # Get raw chunks
    raw_chunks = get_all_raw_chunks(db)
    
    # Get processed chunks
    processed_chunks = get_all_processed_chunks(db)
    
    # Calculate embedding progress
    if raw_chunks:
        progress = (len(processed_chunks) / len(raw_chunks)) * 100
        print(f"Embedding progress: {progress:.2f}%\n")
    
    # Analyze processed chunks
    if processed_chunks:
        chunk_analysis = analyze_processed_chunks(processed_chunks)
        
        print(f"Processed Chunk Analysis:")
        print(f"Unique documents with embeddings: {chunk_analysis.get('unique_documents', 'Unknown')}")
        print(f"Average embedding dimension: {chunk_analysis.get('avg_embedding_dimension', 'Unknown')}")
        print(f"First embedding created: {chunk_analysis.get('first_created', 'Unknown')}")
        print(f"Last embedding created: {chunk_analysis.get('last_created', 'Unknown')}\n")
        
        # Show sample of document IDs with embeddings
        doc_ids = chunk_analysis.get('document_ids', [])
        if doc_ids:
            print(f"Sample of documents with embeddings:")
            for i, doc_id in enumerate(doc_ids[:5]):
                print(f"  {i+1}. {doc_id}")
            if len(doc_ids) > 5:
                print(f"  ... and {len(doc_ids) - 5} more")
    
    # Save report to file
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'document_stats': doc_stats,
        'raw_chunks': len(raw_chunks),
        'processed_chunks': len(processed_chunks),
        'embedding_progress': (len(processed_chunks) / len(raw_chunks) * 100) if raw_chunks else 0,
    }
    
    with open('vector_database_status_check.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\nReport saved to vector_database_status_check.json")

if __name__ == "__main__":
    main()
