#!/usr/bin/env python3

"""
Monitoring Script for Misophonia Research Vector Database

This script monitors the progress of document processing, embedding generation,
and provides insights into the vector database status.
"""

import os
import json
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import argparse

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

def initialize_firebase():
    """
    Initialize Firebase connection.
    """
    try:
        # Initialize Firebase
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

def get_collection_stats(db, collection_name):
    """
    Get statistics for a Firestore collection.
    """
    try:
        docs = db.collection(collection_name).get()
        doc_count = len(list(docs))
        return doc_count
    except Exception as e:
        print(f"Error getting stats for {collection_name}: {e}")
        return 0

def get_embedding_progress(db):
    """
    Get progress of embedding generation.
    """
    try:
        raw_chunks = get_collection_stats(db, 'research_chunks_raw')
        processed_chunks = get_collection_stats(db, 'research_chunks')
        
        if raw_chunks > 0:
            progress_percentage = (processed_chunks / raw_chunks) * 100
        else:
            progress_percentage = 0
            
        return {
            'raw_chunks': raw_chunks,
            'processed_chunks': processed_chunks,
            'progress_percentage': progress_percentage
        }
    except Exception as e:
        print(f"Error getting embedding progress: {e}")
        return {
            'raw_chunks': 0,
            'processed_chunks': 0,
            'progress_percentage': 0
        }

def get_document_stats(db):
    """
    Get statistics about processed documents.
    """
    try:
        docs = db.collection('research_documents').get()
        doc_count = len(list(docs))
        
        # Get document metadata
        years = []
        authors = set()
        
        for doc in db.collection('research_documents').get():
            data = doc.to_dict()
            if 'metadata' in data:
                metadata = data['metadata']
                if 'year' in metadata and metadata['year']:
                    years.append(metadata['year'])
                if 'primary_author' in metadata and metadata['primary_author']:
                    authors.add(metadata['primary_author'])
        
        return {
            'document_count': doc_count,
            'unique_authors': len(authors),
            'year_range': [min(years) if years else None, max(years) if years else None],
            'years_distribution': {year: years.count(year) for year in set(years)}
        }
    except Exception as e:
        print(f"Error getting document stats: {e}")
        return {
            'document_count': 0,
            'unique_authors': 0,
            'year_range': [None, None],
            'years_distribution': {}
        }

def get_chunk_stats(db):
    """
    Get statistics about chunks.
    """
    try:
        # Sample some chunks to analyze
        chunks = list(db.collection('research_chunks').limit(100).get())
        
        if not chunks:
            return {
                'avg_chunk_length': 0,
                'embedding_dimensions': 0
            }
        
        # Calculate average chunk length
        chunk_lengths = []
        embedding_dimensions = 0
        
        for chunk in chunks:
            data = chunk.to_dict()
            if 'text' in data:
                chunk_lengths.append(len(data['text']))
            if 'embedding' in data and isinstance(data['embedding'], list):
                embedding_dimensions = len(data['embedding'])
                break
        
        return {
            'avg_chunk_length': sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0,
            'embedding_dimensions': embedding_dimensions
        }
    except Exception as e:
        print(f"Error getting chunk stats: {e}")
        return {
            'avg_chunk_length': 0,
            'embedding_dimensions': 0
        }

def monitor_progress(db, interval=30, max_time=3600):
    """
    Monitor processing progress over time.
    """
    start_time = time.time()
    progress_data = []
    
    print("Starting monitoring...")
    print("Press Ctrl+C to stop monitoring")
    
    try:
        while time.time() - start_time < max_time:
            # Get current progress
            embedding_progress = get_embedding_progress(db)
            document_stats = get_document_stats(db)
            
            # Record progress
            progress_data.append({
                'timestamp': time.time(),
                'raw_chunks': embedding_progress['raw_chunks'],
                'processed_chunks': embedding_progress['processed_chunks'],
                'documents': document_stats['document_count']
            })
            
            # Print current status
            print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Documents: {document_stats['document_count']}")
            print(f"Raw chunks: {embedding_progress['raw_chunks']}")
            print(f"Processed chunks: {embedding_progress['processed_chunks']}")
            print(f"Embedding progress: {embedding_progress['progress_percentage']:.2f}%")
            
            # Sleep for the specified interval
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    
    # Save progress data
    with open('processing_progress.json', 'w') as f:
        json.dump(progress_data, f, indent=2)
    
    return progress_data

def plot_progress(progress_data):
    """
    Plot processing progress.
    """
    if not progress_data:
        print("No progress data to plot")
        return
    
    # Extract data
    timestamps = [entry['timestamp'] - progress_data[0]['timestamp'] for entry in progress_data]
    raw_chunks = [entry['raw_chunks'] for entry in progress_data]
    processed_chunks = [entry['processed_chunks'] for entry in progress_data]
    documents = [entry['documents'] for entry in progress_data]
    
    # Create plot
    plt.figure(figsize=(12, 8))
    
    # Plot chunks
    plt.subplot(2, 1, 1)
    plt.plot(timestamps, raw_chunks, 'b-', label='Raw Chunks')
    plt.plot(timestamps, processed_chunks, 'g-', label='Processed Chunks')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Count')
    plt.title('Chunk Processing Progress')
    plt.legend()
    plt.grid(True)
    
    # Plot documents
    plt.subplot(2, 1, 2)
    plt.plot(timestamps, documents, 'r-', label='Documents')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Count')
    plt.title('Document Processing Progress')
    plt.legend()
    plt.grid(True)
    
    plt.tight_layout()
    plt.savefig('processing_progress.png')
    print("Progress plot saved to processing_progress.png")

def generate_report(db):
    """
    Generate a comprehensive report on the vector database status.
    """
    print("\nGenerating comprehensive report...")
    
    # Get all stats
    embedding_progress = get_embedding_progress(db)
    document_stats = get_document_stats(db)
    chunk_stats = get_chunk_stats(db)
    
    # Create report
    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'document_stats': document_stats,
        'embedding_stats': embedding_progress,
        'chunk_stats': chunk_stats
    }
    
    # Print report summary
    print("\n" + "="*50)
    print("Misophonia Research Vector Database Report")
    print("="*50)
    print(f"Generated: {report['timestamp']}")
    print("\nDocument Statistics:")
    print(f"Total documents: {document_stats['document_count']}")
    print(f"Unique authors: {document_stats['unique_authors']}")
    if document_stats['year_range'][0] and document_stats['year_range'][1]:
        print(f"Year range: {document_stats['year_range'][0]} - {document_stats['year_range'][1]}")
    
    print("\nChunk Statistics:")
    print(f"Raw chunks: {embedding_progress['raw_chunks']}")
    print(f"Processed chunks: {embedding_progress['processed_chunks']}")
    print(f"Embedding progress: {embedding_progress['progress_percentage']:.2f}%")
    print(f"Average chunk length: {chunk_stats['avg_chunk_length']:.2f} characters")
    print(f"Embedding dimensions: {chunk_stats['embedding_dimensions']}")
    
    # Save report to file
    with open('vector_database_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print("\nReport saved to vector_database_report.json")
    return report

def main():
    parser = argparse.ArgumentParser(description='Monitor Misophonia Research Vector Database processing')
    parser.add_argument('--monitor', action='store_true', help='Monitor processing progress over time')
    parser.add_argument('--interval', type=int, default=30, help='Monitoring interval in seconds')
    parser.add_argument('--max-time', type=int, default=3600, help='Maximum monitoring time in seconds')
    parser.add_argument('--report', action='store_true', help='Generate a comprehensive report')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    if args.monitor:
        # Monitor progress
        progress_data = monitor_progress(db, args.interval, args.max_time)
        plot_progress(progress_data)
    
    if args.report or not args.monitor:
        # Generate report
        generate_report(db)

if __name__ == "__main__":
    main()
