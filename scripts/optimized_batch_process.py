#!/usr/bin/env python3

"""
Optimized Batch Processing Script

This script processes documents with optimized chunk sizes to balance
context preservation with processing efficiency.
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
from datetime import datetime

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

# Research documents directory
RESEARCH_DIR = "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

def extract_metadata_from_filename(filename):
    """
    Extract metadata (author, year, title) from the filename.
    Expected format: Author YYYY Title.pdf
    """
    # Remove file extension
    basename = os.path.basename(filename)
    name_without_ext = os.path.splitext(basename)[0]
    
    # Extract year using regex (4 digits)
    year_match = re.search(r'\b(19|20)\d{2}\b', name_without_ext)
    year = int(year_match.group(0)) if year_match else None
    
    # Extract author (assume it's before the year)
    if year_match:
        author_part = name_without_ext[:year_match.start()].strip()
        title_part = name_without_ext[year_match.end():].strip()
    else:
        # If no year found, make a best guess
        parts = name_without_ext.split(' ', 1)
        author_part = parts[0] if len(parts) > 0 else 'Unknown'
        title_part = parts[1] if len(parts) > 1 else name_without_ext
    
    # Clean up author and title
    author_part = author_part.strip()
    title_part = title_part.strip()
    
    # If title starts with a separator like '-', remove it
    title_part = re.sub(r'^[-_:;]\s*', '', title_part)
    
    return {
        "primary_author": author_part,
        "authors": [author_part],
        "year": year,
        "title": title_part,
        "source_file": basename,
        "source_path": filename
    }

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using PyPDF2 and unstructured.
    Returns a list of sections with text content.
    """
    try:
        # First try with unstructured for better structure preservation
        try:
            # Set a timeout for partition_pdf to prevent hanging on problematic PDFs
            import signal
            from contextlib import contextmanager
            
            @contextmanager
            def timeout(seconds):
                def handler(signum, frame):
                    raise TimeoutError(f"Function timed out after {seconds} seconds")
                original_handler = signal.signal(signal.SIGALRM, handler)
                signal.alarm(seconds)
                try:
                    yield
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, original_handler)
            
            # Try with timeout
            with timeout(60):  # 60 second timeout
                elements = partition_pdf(pdf_path, strategy="hi_res")
                sections = []
                current_section = {"heading": "Page 1", "text": ""}
                page_num = 1
                
                for element in elements:
                    # Check if this is a new section heading
                    if hasattr(element, 'metadata') and element.metadata.get('section_title'):
                        # Save previous section if it has content
                        if current_section["text"].strip():
                            sections.append(current_section)
                        
                        # Start new section
                        current_section = {
                            "heading": element.metadata.get('section_title'),
                            "text": str(element)
                        }
                    # Check if this is a new page
                    elif hasattr(element, 'metadata') and element.metadata.get('page_number') and element.metadata.get('page_number') > page_num:
                        page_num = element.metadata.get('page_number')
                        # Save previous section if it has content
                        if current_section["text"].strip():
                            sections.append(current_section)
                        
                        # Start new page section
                        current_section = {
                            "heading": f"Page {page_num}",
                            "text": str(element)
                        }
                    else:
                        # Add to current section
                        current_section["text"] += "\n" + str(element)
                
                # Add the last section
                if current_section["text"].strip():
                    sections.append(current_section)
                
                # If we got sections, return them
                if sections:
                    return sections
        except TimeoutError as te:
            print(f"Timeout while processing {pdf_path}: {te}")
            print("Falling back to PyPDF2...")
        except Exception as e:
            print(f"Error using unstructured on {pdf_path}: {e}")
            print("Falling back to PyPDF2...")
        
        # Fallback to PyPDF2
        with open(pdf_path, 'rb') as file:
            try:
                reader = PyPDF2.PdfReader(file)
                sections = []
                
                for i, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            sections.append({
                                "heading": f"Page {i+1}",
                                "text": text
                            })
                    except Exception as page_error:
                        print(f"Error extracting text from page {i+1} in {pdf_path}: {page_error}")
                
                return sections
            except Exception as pdf_error:
                print(f"Error reading PDF {pdf_path} with PyPDF2: {pdf_error}")
                return []
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return []

def create_optimized_chunks(sections, metadata, chunk_size=2000, overlap=300):
    """
    Create optimized chunks from document sections with context preservation.
    Uses larger chunk sizes to reduce the total number of chunks while
    maintaining context.
    """
    chunks = []
    document_id = metadata.get('document_id', f"{metadata['primary_author']}_{metadata['year']}")
    
    # Process each section separately to maintain section context
    for section_idx, section in enumerate(sections):
        text = section["text"]
        heading = section["heading"]
        
        # Skip empty sections
        if not text.strip():
            continue
        
        # For very short sections, keep them as a single chunk
        if len(text) <= chunk_size * 1.5:
            chunk = {
                "text": text,
                "metadata": {
                    **metadata,
                    "section": heading,
                    "section_idx": section_idx,
                    "chunk_idx": 0,
                    "document_id": document_id,
                    "total_chunks": 1,
                    "context_chunks": {
                        "prev": None,
                        "next": None
                    }
                }
            }
            chunks.append(chunk)
            continue
        
        # Create section-specific chunks
        section_chunks = []
        
        # Split text into chunks - use sentences as natural boundaries when possible
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed the chunk size and we already have content,
            # save the current chunk and start a new one
            if current_chunk and len(current_chunk) + len(sentence) > chunk_size:
                section_chunks.append(current_chunk)
                # Start new chunk with overlap from the end of the previous chunk
                words = current_chunk.split()
                overlap_words = min(len(words), overlap // 5)  # Approximate words for overlap
                current_chunk = " ".join(words[-overlap_words:]) + " " + sentence
            else:
                # Add sentence to current chunk
                current_chunk += (" " if current_chunk else "") + sentence
        
        # Add the last chunk if it has content
        if current_chunk:
            section_chunks.append(current_chunk)
        
        # Create chunk objects with metadata
        for i, chunk_text in enumerate(section_chunks):
            chunk = {
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "section": heading,
                    "section_idx": section_idx,
                    "chunk_idx": i,
                    "document_id": document_id,
                    "total_chunks": len(section_chunks),
                    "context_chunks": {
                        "prev": i - 1 if i > 0 else None,
                        "next": i + 1 if i < len(section_chunks) - 1 else None
                    }
                }
            }
            chunks.append(chunk)
    
    # Add document-level metadata to all chunks
    for chunk in chunks:
        chunk["metadata"]["document_total_chunks"] = len(chunks)
    
    return chunks

def upload_chunks_to_firestore(db, chunks, document_id, sections):
    """
    Upload document chunks to Firestore with context preservation.
    Uses batch operations and retries for reliability.
    """
    MAX_RETRIES = 5
    MAX_BATCH_SIZE = 500  # Firestore has a limit of 500 operations per batch
    
    # Track successful uploads
    chunks_uploaded = 0
    
    # First, store the document metadata with retry logic
    if chunks and len(chunks) > 0:
        doc_metadata = chunks[0]["metadata"]
        doc_ref = db.collection('research_documents').document(document_id)
        
        for retry in range(MAX_RETRIES):
            try:
                doc_ref.set({
                    "metadata": doc_metadata,
                    "summary": f"Document with {len(chunks)} chunks",
                    "sections": [section["heading"] for section in sections],
                    "createdAt": firestore.SERVER_TIMESTAMP
                })
                print(f"Document metadata uploaded successfully after {retry + 1} attempt(s)")
                break
            except Exception as e:
                print(f"Error uploading document metadata (attempt {retry + 1}): {e}")
                if retry == MAX_RETRIES - 1:
                    print(f"Failed to upload document metadata after {MAX_RETRIES} attempts")
                    return 0
                time.sleep(2 ** retry)  # Exponential backoff
    
    # Store chunks in batches with retry logic
    for batch_start in range(0, len(chunks), MAX_BATCH_SIZE):
        batch_end = min(batch_start + MAX_BATCH_SIZE, len(chunks))
        batch_chunks = chunks[batch_start:batch_end]
        
        print(f"Processing batch of {len(batch_chunks)} chunks ({batch_start+1} to {batch_end} of {len(chunks)})")
        
        for retry in range(MAX_RETRIES):
            try:
                # Create a batch
                batch = db.batch()
                
                # Add each chunk to the batch
                for chunk in batch_chunks:
                    # Create a unique ID that preserves the hierarchical structure
                    chunk_id = f"{document_id}_{chunk['metadata']['section_idx']}_{chunk['metadata']['chunk_idx']}"
                    
                    # Ensure the context references are correct
                    context_chunks = chunk["metadata"]["context_chunks"]
                    
                    # Add to batch
                    chunk_ref = db.collection('research_chunks_raw').document(chunk_id)
                    batch.set(chunk_ref, {
                        "text": chunk["text"],
                        "metadata": chunk["metadata"],
                        "createdAt": firestore.SERVER_TIMESTAMP
                    })
                
                # Commit the batch
                batch.commit()
                chunks_uploaded += len(batch_chunks)
                print(f"Batch uploaded successfully after {retry + 1} attempt(s): {len(batch_chunks)} chunks")
                break
            except Exception as e:
                print(f"Error uploading chunk batch (attempt {retry + 1}): {e}")
                if retry == MAX_RETRIES - 1:
                    print(f"Failed to upload chunk batch after {MAX_RETRIES} attempts")
                    return chunks_uploaded
                time.sleep(2 ** retry)  # Exponential backoff
    
    return chunks_uploaded

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

def process_batch(db, files_to_process, max_chunks_per_file=500):
    """
    Process a batch of files with optimized chunking.
    """
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
            
            # Create optimized chunks with context preservation
            chunks = create_optimized_chunks(sections, metadata)
            print(f"Created {len(chunks)} optimized chunks")
            
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
            print(f"\nu2705 {new_chunks} new embeddings generated!")
            return True
        
        # Wait before checking again
        print(f"Waiting {check_interval} seconds...")
        time.sleep(check_interval)
    
    print("\nu26a0ufe0f No new embeddings detected within the wait time")
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
    parser = argparse.ArgumentParser(description='Optimized batch processing of research documents')
    parser.add_argument('--batch-size', type=int, default=5, help='Number of documents to process in this batch')
    parser.add_argument('--selection', choices=['sequential', 'random'], default='sequential', help='Method for selecting documents')
    parser.add_argument('--max-chunks', type=int, default=500, help='Maximum chunks per document')
    parser.add_argument('--wait-time', type=int, default=300, help='Time to wait for embeddings in seconds')
    parser.add_argument('--skip-wait', action='store_true', help='Skip waiting for embeddings')
    parser.add_argument('--skip-test', action='store_true', help='Skip testing search functionality')
    args = parser.parse_args()
    
    # Check if OpenAI API Key is set
    if not OPENAI_API_KEY:
        print("\nu26a0ufe0f OPENAI_API_KEY environment variable not set!")
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
    print("Processing Batch with Optimized Chunking")
    print("="*50)
    
    batch_stats = process_batch(
        db, 
        files_to_process, 
        max_chunks_per_file=args.max_chunks
    )
    
    # Save batch statistics
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"optimized_batch_stats_{timestamp}.json", "w") as f:
        json.dump(batch_stats, f, indent=2)
    
    print("\n" + "="*50)
    print("Optimized Batch Processing Complete")
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
    
    print("\nBatch statistics saved to optimized_batch_stats_{timestamp}.json")
    print("\nDone!")

if __name__ == "__main__":
    main()
