#!/usr/bin/env python3

"""
Batch Document Processing Script

This script processes PDF documents from the research directory in batches,
extracts text, creates chunks, and generates embeddings for vector search.
It processes documents in batches of 10 and tests the search functionality
after each batch.
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

# Load environment variables from .env file
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# Research documents directory
RESEARCH_DIR = "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Test queries for evaluating the search after each batch
TEST_QUERIES = [
    "What are the symptoms of misophonia?",
    "How is misophonia related to anxiety disorders?",
    "What treatments are effective for misophonia?",
    "Is misophonia more common in certain age groups?",
    "What triggers misophonia reactions?"
]

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
        except Exception as e:
            print(f"Error using unstructured on {pdf_path}: {e}")
            print("Falling back to PyPDF2...")
        
        # Fallback to PyPDF2
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            sections = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text.strip():
                    sections.append({
                        "heading": f"Page {i+1}",
                        "text": text
                    })
            
            return sections
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return []

def create_chunks(sections, metadata, max_chunk_size=1000, overlap=200):
    """
    Create overlapping chunks from document sections with context preservation.
    Returns a list of chunks with metadata and context references.
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
        
        # Create section-specific chunks
        section_chunks = []
        
        # Split text into chunks
        words = text.split()
        chunk_size_words = max(1, max_chunk_size // 5)  # Approximate words per chunk
        step_size = max(1, chunk_size_words - overlap)  # Ensure step size is at least 1
        
        for i in range(0, len(words), step_size):
            chunk_words = words[i:i + chunk_size_words]
            chunk_text = " ".join(chunk_words)
            
            # Skip very small chunks at the end
            if len(chunk_words) < chunk_size_words // 3 and i > 0:
                continue
            
            # Create chunk with metadata
            chunk = {
                "text": chunk_text,
                "metadata": {
                    **metadata,
                    "section": heading,
                    "section_idx": section_idx,
                    "chunk_idx": len(section_chunks),
                    "document_id": document_id,
                    "total_chunks": 0,  # Will update after all chunks are created
                    "context_chunks": {
                        "prev": None,
                        "next": None
                    }
                }
            }
            
            section_chunks.append(chunk)
        
        # Update context references within this section
        for i, chunk in enumerate(section_chunks):
            # Set total chunks in this section
            chunk["metadata"]["total_chunks"] = len(section_chunks)
            
            # Set previous chunk reference
            if i > 0:
                chunk["metadata"]["context_chunks"]["prev"] = i - 1
            
            # Set next chunk reference
            if i < len(section_chunks) - 1:
                chunk["metadata"]["context_chunks"]["next"] = i + 1
        
        # Add section chunks to overall chunks list
        chunks.extend(section_chunks)
    
    # Add document-level metadata to all chunks
    for chunk in chunks:
        chunk["metadata"]["document_total_chunks"] = len(chunks)
    
    return chunks

def upload_chunks_to_firestore(db, chunks, document_id, sections):
    """
    Upload document chunks to Firestore with context preservation.
    Uses batch operations and retries for reliability.
    Returns the number of chunks uploaded.
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

def test_search_functionality(db, query):
    """
    Test the search functionality with a query.
    Returns the search results.
    """
    try:
        # Get the project ID for calling Cloud Functions
        project_id = firebase_admin.get_app().project_id
        # Cloud Function URL
        function_url = f'https://us-central1-{project_id}.cloudfunctions.net/semanticSearch'
        
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
        
        response = requests.post(function_url, json=payload)
        
        if response.status_code != 200:
            print(f"Error calling search function: {response.text}")
            return []
        
        # Process the result
        data = response.json()['result']
        return data['results']
    except Exception as e:
        print(f"Error testing search: {e}")
        return []

def process_batch(pdf_files, batch_num, db, chunk_size=1000, chunk_overlap=200, max_chunks_per_file=5000):
    """
    Process a batch of PDF files.
    Returns statistics about the processed batch.
    """
    stats = {
        "batch_num": batch_num,
        "files_processed": 0,
        "chunks_created": 0,
        "errors": [],
        "file_stats": []  # Track stats for each file
    }
    
    for pdf_file in tqdm(pdf_files, desc=f"Processing Batch {batch_num}"):
        try:
            # Extract metadata from filename
            metadata = extract_metadata_from_filename(pdf_file)
            print(f"\nProcessing: {metadata['title']} by {metadata['primary_author']} ({metadata['year']})")
            
            # Extract text from PDF
            sections = extract_text_from_pdf(pdf_file)
            print(f"Extracted {len(sections)} sections")
            
            if not sections:
                print(f"Warning: No text extracted from {pdf_file}")
                stats["errors"].append(f"No text extracted from {pdf_file}")
                continue
            
            # Create chunks with context preservation
            chunks = create_chunks(sections, metadata, max_chunk_size=chunk_size, overlap=chunk_overlap)
            print(f"Created {len(chunks)} chunks")
            
            # Limit chunks if there are too many (to avoid timeouts)
            if len(chunks) > max_chunks_per_file:
                print(f"Warning: Limiting chunks from {len(chunks)} to {max_chunks_per_file} to avoid timeouts")
                chunks = chunks[:max_chunks_per_file]
            
            if not chunks:
                print(f"Warning: No chunks created from {pdf_file}")
                stats["errors"].append(f"No chunks created from {pdf_file}")
                continue
            
            # Generate a document ID
            document_id = f"doc_{batch_num}_{stats['files_processed']}_{metadata['primary_author']}_{metadata['year']}"
            document_id = re.sub(r'[^a-zA-Z0-9_]', '', document_id)  # Clean ID
            
            # Upload chunks to Firestore with context preservation
            chunks_uploaded = upload_chunks_to_firestore(db, chunks, document_id, sections)
            print(f"Uploaded {chunks_uploaded} chunks to Firestore")
            
            stats["files_processed"] += 1
            stats["chunks_created"] += chunks_uploaded
            
            # Brief pause to avoid overwhelming Firestore
            time.sleep(1)
            
        except Exception as e:
            print(f"Error processing {pdf_file}: {e}")
            stats["errors"].append(f"Error processing {pdf_file}: {e}")
    
    return stats

def wait_for_embeddings(db, batch_stats, max_wait_time=300):
    """
    Wait for embeddings to be generated for the uploaded chunks.
    Returns the number of chunks with embeddings.
    """
    print(f"\nWaiting for embeddings to be generated for {batch_stats['chunks_created']} chunks...")
    start_time = time.time()
    chunks_with_embeddings = 0
    
    while time.time() - start_time < max_wait_time:
        # Check how many chunks have embeddings
        chunks = db.collection('research_chunks').get()
        chunks_with_embeddings = len(list(chunks))
        
        print(f"Found {chunks_with_embeddings} chunks with embeddings after {int(time.time() - start_time)} seconds")
        
        # If all chunks have embeddings, we're done
        if chunks_with_embeddings >= batch_stats["chunks_created"]:
            print("All chunks have embeddings!")
            break
        
        # Wait before checking again
        time.sleep(30)
    
    return chunks_with_embeddings

def test_search(db, batch_num):
    """
    Test the search functionality with test queries.
    Returns the test results.
    """
    print(f"\nTesting search functionality for Batch {batch_num}...")
    test_results = []
    
    for query in TEST_QUERIES:
        print(f"\nQuery: '{query}'")
        results = test_search_functionality(db, query)
        
        print(f"Found {len(results)} results")
        if results:
            print(f"Top result: {results[0]['metadata']['title']} (similarity: {results[0]['similarity']:.4f})")
        
        test_results.append({
            "query": query,
            "num_results": len(results),
            "top_result": results[0] if results else None
        })
    
    return test_results

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Batch process PDF documents for vector search')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of documents per batch')
    parser.add_argument('--start-batch', type=int, default=1, help='Batch number to start with')
    parser.add_argument('--max-batches', type=int, default=None, help='Maximum number of batches to process')
    parser.add_argument('--skip-wait', action='store_true', help='Skip waiting for embeddings')
    parser.add_argument('--skip-test', action='store_true', help='Skip testing search functionality')
    parser.add_argument('--random-sample', action='store_true', help='Process a random sample of documents instead of sequential batches')
    parser.add_argument('--sample-size', type=int, default=40, help='Number of documents to sample if using random sampling')
    parser.add_argument('--chunk-size', type=int, default=1000, help='Maximum size of text chunks in characters')
    parser.add_argument('--chunk-overlap', type=int, default=200, help='Overlap between chunks in characters')
    parser.add_argument('--max-chunks-per-file', type=int, default=5000, help='Maximum number of chunks per file to avoid timeouts')
    parser.add_argument('--retry-failed', action='store_true', help='Retry processing files that previously failed')
    args = parser.parse_args()
    
    # Check if OpenAI API Key is set
    if not OPENAI_API_KEY:
        print("\n⚠️ OPENAI_API_KEY environment variable not set!")
        print("Please set the environment variable before running this script:")
        print("export OPENAI_API_KEY=your_api_key_here")
        return
    
    # Get list of PDF files
    pdf_files = glob.glob(os.path.join(RESEARCH_DIR, "*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {RESEARCH_DIR}")
    
    # If using random sampling, select a random subset of files
    if args.random_sample:
        if args.sample_size >= len(pdf_files):
            print(f"Sample size {args.sample_size} is larger than the number of available files {len(pdf_files)}")
            print("Processing all files instead")
        else:
            print(f"Randomly sampling {args.sample_size} files from {len(pdf_files)} available files")
            random.seed(42)  # For reproducibility
            pdf_files = random.sample(pdf_files, args.sample_size)
            print(f"Selected {len(pdf_files)} files for processing")
    
    # Sort files by name for consistent batching
    pdf_files.sort()
    
    # Calculate number of batches
    num_batches = (len(pdf_files) + args.batch_size - 1) // args.batch_size
    if args.max_batches:
        num_batches = min(num_batches, args.max_batches)
    
    print(f"Processing {len(pdf_files)} files in {num_batches} batches of {args.batch_size}")
    
    # Initialize Firebase
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    # Process batches
    all_stats = []
    for batch_num in range(args.start_batch, args.start_batch + num_batches):
        batch_start = (batch_num - 1) * args.batch_size
        batch_end = min(batch_start + args.batch_size, len(pdf_files))
        batch_files = pdf_files[batch_start:batch_end]
        
        print(f"\n{'='*50}")
        print(f"Processing Batch {batch_num} of {args.start_batch + num_batches - 1}")
        print(f"Files {batch_start + 1} to {batch_end} of {len(pdf_files)}")
        print(f"{'='*50}\n")
        
        # Process the batch
        batch_stats = process_batch(batch_files, batch_num, db, chunk_size=args.chunk_size, 
                                 chunk_overlap=args.chunk_overlap, max_chunks_per_file=args.max_chunks_per_file)
        all_stats.append(batch_stats)
        
        # Wait for embeddings to be generated
        if not args.skip_wait:
            chunks_with_embeddings = wait_for_embeddings(db, batch_stats)
            batch_stats["chunks_with_embeddings"] = chunks_with_embeddings
        
        # Test search functionality
        if not args.skip_test:
            test_results = test_search(db, batch_num)
            batch_stats["test_results"] = test_results
        
        # Save batch statistics
        with open(f"batch_{batch_num}_stats.json", "w") as f:
            json.dump(batch_stats, f, indent=2)
        
        print(f"\nBatch {batch_num} complete!")
        print(f"Files processed: {batch_stats['files_processed']}")
        print(f"Chunks created: {batch_stats['chunks_created']}")
        if not args.skip_wait:
            print(f"Chunks with embeddings: {batch_stats['chunks_with_embeddings']}")
        if batch_stats["errors"]:
            print(f"Errors: {len(batch_stats['errors'])}")
        
        # Wait before processing next batch
        if batch_num < args.start_batch + num_batches - 1:
            print(f"\nWaiting 60 seconds before processing next batch...")
            time.sleep(60)
    
    # Save overall statistics
    overall_stats = {
        "total_files": len(pdf_files),
        "batches_processed": len(all_stats),
        "total_files_processed": sum(s["files_processed"] for s in all_stats),
        "total_chunks_created": sum(s["chunks_created"] for s in all_stats),
        "total_errors": sum(len(s["errors"]) for s in all_stats),
        "batch_stats": all_stats
    }
    
    with open("overall_processing_stats.json", "w") as f:
        json.dump(overall_stats, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"Processing complete!")
    print(f"{'='*50}")
    print(f"Total files processed: {overall_stats['total_files_processed']} of {overall_stats['total_files']}")
    print(f"Total chunks created: {overall_stats['total_chunks_created']}")
    print(f"Total errors: {overall_stats['total_errors']}")
    print(f"\nSee overall_processing_stats.json for details")

if __name__ == "__main__":
    main()
