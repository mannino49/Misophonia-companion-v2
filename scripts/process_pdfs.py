#!/usr/bin/env python3

"""
PDF Processing Script for Misophonia Research Documents

This script processes PDF documents in the research/Global folder,
extracts text, creates chunks with context preservation, and uploads
them to Firestore for vector embedding generation.

Requirements:
  pip install firebase-admin PyPDF2 unstructured[pdf] regex
"""

import os
import re
import json
import argparse
from typing import Dict, List, Optional, Tuple, Any

# PDF processing
import PyPDF2
from unstructured.partition.pdf import partition_pdf

# Firebase
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Constants
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # characters
RESEARCH_DIR = "../documents/research/Global"


def extract_metadata_from_filename(filename: str) -> Dict[str, Any]:
    """
    Extract metadata from filename using regex pattern.
    Expected format: Author [Year] Title.pdf
    """
    # Remove file extension
    filename = os.path.splitext(filename)[0]
    
    # Try to extract year
    year_match = re.search(r'\b(19|20)\d{2}\b', filename)
    year = int(year_match.group(0)) if year_match else None
    
    # Split filename by year if found
    if year_match:
        parts = filename.split(str(year), 1)
        author = parts[0].strip()
        title = parts[1].strip(' -_').strip()
    else:
        # Fallback if year not found
        author_title = filename.split(' - ', 1)
        if len(author_title) > 1:
            author, title = author_title
        else:
            author = "Unknown"
            title = filename
    
    # Clean up author and title
    author = author.strip()
    title = title.strip()
    
    # Extract authors list (split by 'and' or ',')
    authors = [a.strip() for a in re.split(r'\s+and\s+|,\s*', author) if a.strip()]
    
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "primary_author": authors[0] if authors else "Unknown"
    }


def extract_text_from_pdf(pdf_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extract text from PDF with structure preservation.
    Returns the full text and a list of sections.
    """
    try:
        # First try unstructured for better structure preservation
        elements = partition_pdf(pdf_path, strategy="hi_res")
        full_text = "\n".join([str(element) for element in elements])
        
        # Extract sections based on headings
        sections = []
        current_section = {"heading": "Introduction", "text": ""}
        
        for element in elements:
            element_text = str(element)
            
            # Check if this might be a heading (heuristic)
            is_heading = (len(element_text) < 100 and 
                         element_text.strip() and
                         not element_text.endswith('.') and
                         not any(c.isdigit() for c in element_text))
            
            if is_heading:
                # Save previous section if it has content
                if current_section["text"].strip():
                    sections.append(current_section)
                
                # Start new section
                current_section = {"heading": element_text.strip(), "text": ""}
            else:
                # Add to current section
                current_section["text"] += element_text + "\n"
        
        # Add the last section
        if current_section["text"].strip():
            sections.append(current_section)
        
        return full_text, sections
        
    except Exception as e:
        print(f"Error with unstructured: {e}, falling back to PyPDF2")
        
        # Fallback to PyPDF2 (less structure preservation)
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            full_text = ""
            
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                full_text += page.extract_text() + "\n\n"
        
        # Simple section splitting by newlines
        sections = [{"heading": "Page " + str(i+1), "text": text} 
                   for i, text in enumerate(full_text.split("\n\n")) 
                   if text.strip()]
        
        return full_text, sections


def create_chunks_with_context(text: str, chunk_size: int = CHUNK_SIZE, 
                             overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """
    Create overlapping chunks from text with context preservation.
    """
    chunks = []
    start = 0
    
    while start < len(text):
        # Get chunk with overlap
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end]
        
        # Find a good break point (end of sentence)
        if end < len(text):
            last_period = chunk_text.rfind('.')
            if last_period > chunk_size - overlap:
                end = start + last_period + 1
                chunk_text = text[start:end]
        
        # Create chunk with metadata
        chunk = {
            "text": chunk_text,
            "start_char": start,
            "end_char": end,
        }
        
        chunks.append(chunk)
        
        # Move start position for next chunk (with overlap)
        start = end - overlap if end < len(text) else end
    
    # Add context references
    for i, chunk in enumerate(chunks):
        chunk["context_chunks"] = {
            "prev": i - 1 if i > 0 else None,
            "next": i + 1 if i < len(chunks) - 1 else None
        }
    
    return chunks


def process_document(pdf_path: str, db) -> None:
    """
    Process a single PDF document and upload chunks to Firestore.
    """
    filename = os.path.basename(pdf_path)
    print(f"Processing {filename}...")
    
    try:
        # Extract metadata from filename
        metadata = extract_metadata_from_filename(filename)
        metadata["source_file"] = filename
        metadata["source_path"] = pdf_path
        
        # Extract text with structure
        full_text, sections = extract_text_from_pdf(pdf_path)
        
        # Create document entry
        doc_ref = db.collection('research_documents').document()
        doc_id = doc_ref.id
        
        doc_ref.set({
            "metadata": metadata,
            "summary": full_text[:500] + "...",  # Simple summary
            "sections": [s["heading"] for s in sections],
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        
        # Process each section
        for section_idx, section in enumerate(sections):
            # Create chunks for this section
            section_chunks = create_chunks_with_context(section["text"])
            
            # Upload each chunk to Firestore
            for chunk_idx, chunk in enumerate(section_chunks):
                chunk_metadata = {
                    **metadata,
                    "document_id": doc_id,
                    "section": section["heading"],
                    "section_idx": section_idx,
                    "chunk_idx": chunk_idx,
                    "total_chunks": len(section_chunks),
                    "context_chunks": chunk["context_chunks"]
                }
                
                # Upload to raw chunks collection (will trigger Cloud Function)
                db.collection('research_chunks_raw').add({
                    "text": chunk["text"],
                    "metadata": chunk_metadata,
                    "createdAt": firestore.SERVER_TIMESTAMP
                })
        
        print(f"Successfully processed {filename} - {len(sections)} sections, "
              f"document ID: {doc_id}")
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Process PDF documents for Misophonia Research')
    parser.add_argument('--path', default=RESEARCH_DIR, 
                        help='Path to research documents directory')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit the number of documents to process (0 for all)')
    parser.add_argument('--service-account', required=True,
                        help='Path to Firebase service account JSON file')
    
    args = parser.parse_args()
    
    # Initialize Firebase
    cred = credentials.Certificate(args.service_account)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    
    # Get all PDF files
    pdf_files = []
    for root, _, files in os.walk(args.path):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    # Apply limit if specified
    if args.limit > 0:
        pdf_files = pdf_files[:args.limit]
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF
    for pdf_path in pdf_files:
        process_document(pdf_path, db)
    
    print("Processing complete!")


if __name__ == "__main__":
    main()
