#!/usr/bin/env python3

"""
Test script for PDF processing

This script tests the PDF processing functions without uploading to Firebase.
"""

import os
import sys
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from process_pdfs import extract_metadata_from_filename, extract_text_from_pdf, create_chunks_with_context, process_document

# Use absolute path for testing
RESEARCH_DIR = "/Users/mannino/CascadeProjects/Misophonia Guide/documents/research/Global"

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"
TEST_LIMIT = 3  # Number of PDFs to test

def main():
    # Initialize Firebase with service account
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Using default Firestore database
        
        # Test database connection
        print("Testing database connection...")
        collections = [collection.id for collection in db.collections()]
        print(f"Available collections: {collections}")
        print("Firebase initialized successfully")
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        sys.exit(1)
    
    # Get all PDF files
    pdf_files = []
    for root, _, files in os.walk(RESEARCH_DIR):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    # Apply limit
    pdf_files = pdf_files[:TEST_LIMIT]
    
    print(f"Found {len(pdf_files)} PDF files to test")
    
    # Test mode selection
    print("\nSelect test mode:")
    print("1. Test metadata extraction and text processing only")
    print("2. Test full document processing with Firestore upload")
    mode = input("Enter mode (1 or 2): ")
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        print(f"\nProcessing {filename}...")
        
        try:
            # Extract metadata from filename
            metadata = extract_metadata_from_filename(filename)
            print(f"Metadata: {metadata}")
            
            # Extract text with structure
            print(f"Extracting text from {filename}...")
            full_text, sections = extract_text_from_pdf(pdf_path)
            
            print(f"Extracted {len(sections)} sections:")
            for i, section in enumerate(sections[:3]):  # Show first 3 sections
                print(f"  Section {i+1}: {section['heading']}")
                print(f"    Text preview: {section['text'][:100]}...")
            
            if len(sections) > 3:
                print(f"  ... and {len(sections) - 3} more sections")
            
            # Create chunks for the first section
            if sections:
                first_section = sections[0]
                print(f"\nCreating chunks for section: {first_section['heading']}")
                chunks = create_chunks_with_context(first_section['text'])
                
                print(f"Created {len(chunks)} chunks:")
                for i, chunk in enumerate(chunks[:2]):  # Show first 2 chunks
                    print(f"  Chunk {i+1}: {chunk['text'][:100]}...")
                    print(f"    Start: {chunk['start_char']}, End: {chunk['end_char']}")
                    print(f"    Context: prev={chunk['context_chunks']['prev']}, next={chunk['context_chunks']['next']}")
                
                if len(chunks) > 2:
                    print(f"  ... and {len(chunks) - 2} more chunks")
            
            # If mode 2, process the document and upload to Firestore
            if mode == "2":
                print("\nUploading to Firestore...")
                process_document(pdf_path, db)
                print(f"Successfully uploaded {filename} to Firestore")
            
            print(f"Successfully processed {filename}")
            
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    main()
