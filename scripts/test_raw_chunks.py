#!/usr/bin/env python3

"""
Test Raw Chunks Script

This script tests searching through raw chunks in the Firestore database
without relying on the semantic search function.
"""

import os
import time
import json
import argparse
import random
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from tabulate import tabulate
import re

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

def search_raw_chunks(db, keyword, limit=1000):
    """
    Search for a keyword in raw chunks and return matching chunks.
    """
    try:
        # Get a sample of raw chunks
        chunks_query = db.collection('research_chunks_raw').limit(limit)
        chunks = chunks_query.get()
        
        print(f"Examining {len(chunks)} raw chunks...")
        
        # Search for keyword in chunks
        matching_chunks = []
        for chunk in chunks:
            chunk_data = chunk.to_dict()
            if keyword.lower() in chunk_data.get('text', '').lower():
                matching_chunks.append({
                    'id': chunk.id,
                    'text': chunk_data.get('text', ''),
                    'metadata': chunk_data.get('metadata', {})
                })
        
        print(f"Found {len(matching_chunks)} chunks containing '{keyword}'")
        return matching_chunks
    except Exception as e:
        print(f"Error searching raw chunks: {e}")
        return []

def display_results(results):
    """
    Display search results in a formatted table.
    """
    if not results:
        print("No results found.")
        return
    
    # Prepare table data
    table_data = []
    for i, result in enumerate(results):
        # Extract metadata
        metadata = result.get('metadata', {})
        source = f"{metadata.get('primary_author', 'Unknown')} ({metadata.get('year', 'Unknown')})"
        title = metadata.get('title', 'Unknown')
        section = metadata.get('section', 'Unknown')
        
        # Format text snippet (first 200 characters)
        text = result.get('text', '')
        text_snippet = text[:200] + '...' if len(text) > 200 else text
        
        # Add to table
        table_data.append([i+1, source, title, section, text_snippet])
    
    # Display table
    print(tabulate(table_data, headers=['#', 'Source', 'Title', 'Section', 'Text Snippet'], tablefmt='grid'))

def search_by_topic(db, topic, limit=1000):
    """
    Search for documents related to a specific topic.
    """
    print(f"\n=== Searching for documents related to '{topic}' ===\n")
    
    # Search raw chunks
    results = search_raw_chunks(db, topic, limit)
    
    # Display results
    if results:
        display_results(results)
    else:
        print(f"No documents found related to '{topic}'.")

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
        
        print(f"\n=== Document Statistics ===\n")
        print(f"Total documents: {len(docs)}")
        print(f"Unique authors: {len(authors)}")
        print(f"Year range: {year_range}")
        
        # Get raw chunks count
        raw_chunks_query = db.collection('research_chunks_raw').limit(1)
        raw_chunks_count = len(list(db.collection('research_chunks_raw').limit(10000).get()))
        
        # Get processed chunks count
        processed_chunks_query = db.collection('research_chunks').limit(1)
        processed_chunks_count = len(list(db.collection('research_chunks').limit(10000).get()))
        
        print(f"\n=== Chunk Statistics ===\n")
        print(f"Raw chunks (sample): {raw_chunks_count}")
        print(f"Processed chunks (sample): {processed_chunks_count}")
        
        if raw_chunks_count > 0:
            progress = (processed_chunks_count / raw_chunks_count) * 100
            print(f"Embedding progress: {progress:.2f}%")
        
        return {
            'document_count': len(docs),
            'author_count': len(authors),
            'year_range': year_range,
            'raw_chunks': raw_chunks_count,
            'processed_chunks': processed_chunks_count
        }
    except Exception as e:
        print(f"Error getting document stats: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description='Test searching raw chunks in the Firestore database')
    parser.add_argument('--keyword', type=str, help='Keyword to search for')
    parser.add_argument('--limit', type=int, default=1000, help='Maximum number of chunks to examine')
    parser.add_argument('--topic', type=str, help='Topic to search for (e.g., "treatment", "diagnosis")')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    # Show database statistics
    if args.stats or not (args.keyword or args.topic):
        get_document_stats(db)
    
    # Search by keyword
    if args.keyword:
        print(f"\n=== Searching for keyword: '{args.keyword}' ===\n")
        results = search_raw_chunks(db, args.keyword, args.limit)
        if results:
            display_results(results)
    
    # Search by topic
    if args.topic:
        search_by_topic(db, args.topic, args.limit)
    
    # If no search parameters provided, show predefined topics
    if not (args.keyword or args.topic):
        print("\n=== Predefined Topics ===\n")
        topics = [
            "misophonia symptoms",
            "misophonia treatment",
            "hyperacusis",
            "tinnitus",
            "sound sensitivity",
            "auditory processing",
            "cognitive behavioral therapy",
            "neuroscience"
        ]
        
        for topic in topics:
            print(f"- {topic}")
        
        print("\nRun with --topic 'topic_name' to search for a specific topic.")

if __name__ == "__main__":
    main()
