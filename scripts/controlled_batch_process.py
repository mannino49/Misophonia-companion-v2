#!/usr/bin/env python3

"""
Controlled Batch Processing Script

This script processes a controlled number of documents from the research directory,
allowing for careful monitoring and testing between batches.
"""

import os
import time
import json
import glob
import random
import argparse
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
from tqdm import tqdm
import PyPDF2
import re
from unstructured.partition.pdf import partition_pdf
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

# Research documents directory
RESEARCH_DIR = "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

def get_processed_documents(db):
    """
    Get a list of documents that have already been processed.
    """
    try:
        # Get all documents in the research_documents collection
        docs = db.collection('research_documents').get()
        processed_docs = []
        
        for doc in docs:
            data = doc.to_dict()
            if 'metadata' in data and 'source_path' in data['metadata']:
                processed_docs.append(data['metadata']['source_path'])
        
        return processed_docs
    except Exception as e:
        print(f"Error getting processed documents: {e}")
        return []

def select_next_batch(all_files, processed_files, batch_size, selection_method='sequential'):
    """
    Select the next batch of files to process.
    """
    # Filter out already processed files
    remaining_files = [f for f in all_files if f not in processed_files]
    print(f"Found {len(remaining_files)} unprocessed files out of {len(all_files)} total files")
    
    if not remaining_files:
        print("No files left to process!")
        return []
    
    # Select files based on the specified method
    if selection_method == 'random':
        # Random selection
        if len(remaining_files) <= batch_size:
            return remaining_files
        else:
            return random.sample(remaining_files, batch_size)
    else:
        # Sequential selection
        return remaining_files[:batch_size]

def process_batch(db, files_to_process, max_chunks_per_file=1000, chunk_size=1000, chunk_overlap=200):
    """
    Process a batch of files and upload chunks to Firestore.
    """
    from batch_process_documents import extract_metadata_from_filename, extract_text_from_pdf, create_chunks, upload_chunks_to_firestore
    
    stats = {
        "files_processed": 0,
        "chunks_created": 0,
        "errors": [],
        "file_stats": []
    }
    
    for pdf_file in tqdm(files_to_process, desc="Processing Files"):
        file_stats = {
            "file": os.path.basename(pdf_file),
            "path": pdf_file,
            "sections": 0,
            "chunks": 0,
            "success": False,
            "error": None
        }
        
        try:
            # Extract metadata from filename
            metadata = extract_metadata_from_filename(pdf_file)
            file_stats.update({
                "title": metadata['title'],
                "author": metadata['primary_author'],
                "year": metadata['year']
            })
            
            print(f"\nProcessing: {metadata['title']} by {metadata['primary_author']} ({metadata['year']})")
            
            # Extract text from PDF
            sections = extract_text_from_pdf(pdf_file)
            print(f"Extracted {len(sections)} sections")
            file_stats["sections"] = len(sections)
            
            if not sections:
                error_msg = f"No text extracted from {pdf_file}"
                print(f"Warning: {error_msg}")
                stats["errors"].append(error_msg)
                file_stats["error"] = error_msg
                stats["file_stats"].append(file_stats)
                continue
            
            # Create chunks with context preservation
            chunks = create_chunks(sections, metadata, max_chunk_size=chunk_size, overlap=chunk_overlap)
            print(f"Created {len(chunks)} chunks")
            
            # Limit chunks if there are too many
            if len(chunks) > max_chunks_per_file:
                print(f"Warning: Limiting chunks from {len(chunks)} to {max_chunks_per_file} to avoid timeouts")
                chunks = chunks[:max_chunks_per_file]
            
            file_stats["chunks"] = len(chunks)
            
            if not chunks:
                error_msg = f"No chunks created from {pdf_file}"
                print(f"Warning: {error_msg}")
                stats["errors"].append(error_msg)
                file_stats["error"] = error_msg
                stats["file_stats"].append(file_stats)
                continue
            
            # Generate a document ID
            document_id = f"doc_{stats['files_processed']}_{metadata['primary_author']}_{metadata['year']}"
            document_id = re.sub(r'[^a-zA-Z0-9_]', '', document_id)  # Clean ID
            
            # Upload chunks to Firestore
            chunks_uploaded = upload_chunks_to_firestore(db, chunks, document_id, sections)
            print(f"Uploaded {chunks_uploaded} chunks to Firestore")
            
            stats["files_processed"] += 1
            stats["chunks_created"] += chunks_uploaded
            file_stats["success"] = True
            
            # Brief pause to avoid overwhelming Firestore
            time.sleep(2)
            
        except Exception as e:
            error_msg = f"Error processing {pdf_file}: {e}"
            print(f"Error: {error_msg}")
            stats["errors"].append(error_msg)
            file_stats["error"] = str(e)
            file_stats["success"] = False
        
        stats["file_stats"].append(file_stats)
    
    return stats

def wait_for_embeddings(db, batch_stats, wait_time=300, check_interval=30):
    """
    Wait for embeddings to be generated for the uploaded chunks.
    """
    print(f"\nWaiting for embeddings to be generated (max {wait_time} seconds)...")
    start_time = time.time()
    
    # Get initial count
    initial_count = len(list(db.collection('research_chunks').limit(1000).get()))
    print(f"Initial processed chunks: {initial_count}")
    
    while time.time() - start_time < wait_time:
        # Check current count
        current_count = len(list(db.collection('research_chunks').limit(1000).get()))
        new_chunks = current_count - initial_count
        
        print(f"Current processed chunks: {current_count} (+{new_chunks} new)")
        
        if new_chunks > 0:
            print(f"\n✅ {new_chunks} new embeddings generated!")
            return True
        
        # Wait before checking again
        print(f"Waiting {check_interval} seconds...")
        time.sleep(check_interval)
    
    print("\n⚠️ No new embeddings detected within the wait time")
    return False

def test_search(db, query="What are the symptoms of misophonia?"):
    """
    Test the search functionality with a query.
    """
    try:
        # Get the project ID for calling Cloud Functions
        project_id = firebase_admin.get_app().project_id
        # Cloud Function URL
        function_url = f'https://us-central1-{project_id}.cloudfunctions.net/semanticSearch'
        
        print(f"\nTesting search with query: '{query}'")
        
        # Call the Cloud Function via HTTP
        payload = {
            'data': {
                'query': query,
                'filters': {},
                'expandContext': True,
                'page': 1,
                'pageSize': 5,
                'similarityThreshold': 0.6
            }
        }
        
        response = requests.post(function_url, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"Error calling search function: {response.text}")
            return False
        
        # Process the result
        data = response.json()['result']
        results = data['results']
        
        print(f"Found {len(results)} results")
        
        if results:
            print("\nTop result:")
            top = results[0]
            print(f"Title: {top['metadata'].get('title', 'Unknown')}")
            print(f"Author: {top['metadata'].get('primary_author', 'Unknown')}")
            print(f"Year: {top['metadata'].get('year', 'Unknown')}")
            print(f"Similarity: {top['similarity']:.4f}")
            print(f"Text snippet: {top['text'][:200]}...")
            return True
        else:
            print("No results found")
            return False
    except Exception as e:
        print(f"Error testing search: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Controlled batch processing of research documents')
    parser.add_argument('--batch-size', type=int, default=5, help='Number of documents to process in this batch')
    parser.add_argument('--selection', choices=['sequential', 'random'], default='sequential', help='Method for selecting documents')
    parser.add_argument('--max-chunks', type=int, default=1000, help='Maximum chunks per document')
    parser.add_argument('--chunk-size', type=int, default=1000, help='Size of each chunk in characters')
    parser.add_argument('--chunk-overlap', type=int, default=200, help='Overlap between chunks in characters')
    parser.add_argument('--wait-time', type=int, default=300, help='Time to wait for embeddings in seconds')
    parser.add_argument('--skip-wait', action='store_true', help='Skip waiting for embeddings')
    parser.add_argument('--skip-test', action='store_true', help='Skip testing search functionality')
    args = parser.parse_args()
    
    # Check if OpenAI API Key is set
    if not OPENAI_API_KEY:
        print("\n⚠️ OPENAI_API_KEY environment variable not set!")
        print("Please set the environment variable before running this script:")
        print("export OPENAI_API_KEY=your_api_key_here")
        return
    
    # Initialize Firebase
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    # Get all PDF files
    pdf_files = glob.glob(os.path.join(RESEARCH_DIR, "*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {RESEARCH_DIR}")
    
    # Get already processed documents
    processed_files = get_processed_documents(db)
    print(f"Found {len(processed_files)} already processed documents")
    
    # Select next batch of files to process
    files_to_process = select_next_batch(pdf_files, processed_files, args.batch_size, args.selection)
    
    if not files_to_process:
        print("No files to process. Exiting.")
        return
    
    print(f"\nSelected {len(files_to_process)} files for processing:")
    for i, file in enumerate(files_to_process):
        print(f"{i+1}. {os.path.basename(file)}")
    
    # Process the batch
    print("\n" + "="*50)
    print("Processing Batch")
    print("="*50)
    
    batch_stats = process_batch(
        db, 
        files_to_process, 
        max_chunks_per_file=args.max_chunks,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    
    # Save batch statistics
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"batch_stats_{timestamp}.json", "w") as f:
        json.dump(batch_stats, f, indent=2)
    
    print("\n" + "="*50)
    print("Batch Processing Complete")
    print("="*50)
    print(f"Files processed: {batch_stats['files_processed']}")
    print(f"Chunks created: {batch_stats['chunks_created']}")
    if batch_stats["errors"]:
        print(f"Errors: {len(batch_stats['errors'])}")
        for error in batch_stats["errors"]:
            print(f"  - {error}")
    
    # Wait for embeddings if not skipped
    if not args.skip_wait:
        embeddings_generated = wait_for_embeddings(db, batch_stats, wait_time=args.wait_time)
    
    # Test search if not skipped
    if not args.skip_test:
        test_search(db)
    
    print("\nBatch statistics saved to batch_stats_{timestamp}.json")
    print("\nDone!")

if __name__ == "__main__":
    from datetime import datetime
    main()
