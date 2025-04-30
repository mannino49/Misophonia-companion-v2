#!/usr/bin/env python3

"""
Test script for PDF processing and vectorization

This script processes a few sample PDF documents, extracts text with context preservation,
and uploads the chunks to Firestore to trigger the embedding generation Cloud Function.
"""

import os
import sys
import json
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from process_pdfs import extract_metadata_from_filename, extract_text_from_pdf, create_chunks_with_context

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# Sample PDFs to process (3 files for testing)
SAMPLE_PDFS = [
    "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global/Aazh 2022 Audiological and Other Factors Predicting the Presence of Misophonia Symptoms Among a Clinical Population Seeking Help for Tinnitus and or Hyperacusis.pdf",
    "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global/Andermane 2023 A Phenomenological Cartography of Misophonia.pdf",
    "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global/Aryal 2022 Misophonia Prevalence, impact and co-morbidity among Mysore University Students in India.pdf"
]

def process_and_upload_document(pdf_path, db):
    """
    Process a single PDF document and upload chunks to Firestore.
    """
    filename = os.path.basename(pdf_path)
    print(f"\nProcessing {filename}...")
    
    try:
        # Extract metadata from filename
        metadata = extract_metadata_from_filename(filename)
        metadata["source_file"] = filename
        metadata["source_path"] = pdf_path
        
        print(f"Extracted metadata: {json.dumps(metadata, indent=2)}")
        
        # Extract text with structure
        print(f"Extracting text from {filename}...")
        full_text, sections = extract_text_from_pdf(pdf_path)
        
        print(f"Extracted {len(sections)} sections")
        
        # Create document entry
        doc_ref = db.collection('research_documents').document()
        doc_id = doc_ref.id
        
        doc_ref.set({
            "metadata": metadata,
            "summary": full_text[:500] + "...",  # Simple summary
            "sections": [s["heading"] for s in sections],
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        
        print(f"Created document entry with ID: {doc_id}")
        
        # Process each section
        total_chunks = 0
        for section_idx, section in enumerate(sections):
            # Create chunks for this section
            section_chunks = create_chunks_with_context(section["text"])
            
            print(f"  Section '{section['heading']}': {len(section_chunks)} chunks")
            
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
                
                total_chunks += 1
                
                # Add a small delay to avoid overwhelming the Cloud Function
                time.sleep(0.1)
        
        print(f"Successfully processed {filename} - {len(sections)} sections, {total_chunks} chunks")
        print(f"Document ID: {doc_id}")
        return total_chunks
        
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return 0

def main():
    # Initialize Firebase with service account
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Test database connection
        print("Testing database connection...")
        collections = [collection.id for collection in db.collections()]
        print(f"Available collections: {collections}")
        print("Firebase initialized successfully")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        sys.exit(1)
    
    # Process each sample PDF
    total_documents = 0
    total_chunks = 0
    
    for pdf_path in SAMPLE_PDFS:
        if os.path.exists(pdf_path):
            chunks = process_and_upload_document(pdf_path, db)
            if chunks > 0:
                total_documents += 1
                total_chunks += chunks
        else:
            print(f"File not found: {pdf_path}")
    
    print(f"\nVectorization Summary:")
    print(f"Processed {total_documents} documents")
    print(f"Generated {total_chunks} chunks")
    print(f"Cloud Function will generate embeddings for each chunk")
    print("Check Firebase Console to monitor progress")

if __name__ == "__main__":
    main()
