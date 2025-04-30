#!/usr/bin/env python3

"""
Test Current Vector Database Implementation

This script tests the current state of the Misophonia Research Vector Database
with the documents that have been processed so far. It performs several test
queries and displays the results with context expansion.
"""

import os
import json
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
import requests
import argparse
from tabulate import tabulate
from colorama import Fore, Style, init

# Initialize colorama
init()

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

# Test queries for evaluating the search
TEST_QUERIES = [
    "What are the symptoms of misophonia?",
    "How is misophonia related to anxiety disorders?",
    "What treatments are effective for misophonia?",
    "Is misophonia more common in certain age groups?",
    "What triggers misophonia reactions?",
    "How does misophonia affect daily life?",
    "What is the relationship between misophonia and other sensory disorders?",
    "What neurological mechanisms are involved in misophonia?"
]

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

def get_embedding_status(db):
    """
    Get the current status of embedding generation.
    """
    try:
        raw_chunks = len(list(db.collection('research_chunks_raw').limit(1000).get()))
        processed_chunks = len(list(db.collection('research_chunks').limit(1000).get()))
        
        print(f"\n{Fore.BLUE}=== Embedding Status ==={Style.RESET_ALL}")
        print(f"Raw chunks (sample): {raw_chunks}")
        print(f"Processed chunks (sample): {processed_chunks}")
        
        # Get some sample processed chunks to examine
        if processed_chunks > 0:
            print(f"\n{Fore.GREEN}✓ Embeddings are being generated!{Style.RESET_ALL}")
            
            # Get a sample processed chunk
            sample_chunks = list(db.collection('research_chunks').limit(1).get())
            if sample_chunks:
                sample = sample_chunks[0].to_dict()
                print(f"\n{Fore.BLUE}Sample Processed Chunk:{Style.RESET_ALL}")
                print(f"Document ID: {sample_chunks[0].id}")
                if 'embedding' in sample:
                    print(f"Embedding dimensions: {len(sample['embedding'])}")
                if 'metadata' in sample:
                    metadata = sample['metadata']
                    print(f"Title: {metadata.get('title', 'Unknown')}")
                    print(f"Author: {metadata.get('primary_author', 'Unknown')}")
                    print(f"Year: {metadata.get('year', 'Unknown')}")
                    print(f"Section: {metadata.get('section', 'Unknown')}")
            
            return True
        else:
            print(f"\n{Fore.YELLOW}⚠ No embeddings found yet. Processing may still be ongoing.{Style.RESET_ALL}")
            return False
    except Exception as e:
        print(f"\n{Fore.RED}Error checking embedding status: {e}{Style.RESET_ALL}")
        return False

def test_search(db, query, expand_context=True, similarity_threshold=0.6):
    """
    Test the semantic search with a specific query.
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
                'expandContext': expand_context,
                'page': 1,
                'pageSize': 5,
                'similarityThreshold': similarity_threshold
            }
        }
        
        print(f"\n{Fore.BLUE}Query: '{query}'{Style.RESET_ALL}")
        print("Calling search function...")
        
        response = requests.post(function_url, json=payload, timeout=30)
        
        if response.status_code != 200:
            print(f"{Fore.RED}Error calling search function: {response.text}{Style.RESET_ALL}")
            return []
        
        # Process the result
        data = response.json()['result']
        results = data['results']
        
        print(f"{Fore.GREEN}Found {len(results)} results{Style.RESET_ALL}")
        
        return results
    except Exception as e:
        print(f"{Fore.RED}Error testing search: {e}{Style.RESET_ALL}")
        return []

def display_results(results):
    """
    Display search results in a readable format.
    """
    if not results:
        print(f"{Fore.YELLOW}No results to display{Style.RESET_ALL}")
        return
    
    # Prepare table data
    table_data = []
    for i, result in enumerate(results):
        metadata = result.get('metadata', {})
        similarity = result.get('similarity', 0) * 100  # Convert to percentage
        
        # Format text snippet (truncate if too long)
        text = result.get('text', '')
        if len(text) > 200:
            text = text[:197] + '...'
        
        # Get document info
        title = metadata.get('title', 'Unknown')
        author = metadata.get('primary_author', 'Unknown')
        year = metadata.get('year', 'Unknown')
        section = metadata.get('section', 'Unknown')
        
        # Add to table
        table_data.append([
            i + 1,
            f"{similarity:.1f}%",
            f"{author} ({year})",
            title,
            section,
            text
        ])
    
    # Display table
    headers = ["#", "Similarity", "Source", "Title", "Section", "Text Snippet"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

def test_context_expansion(db, query):
    """
    Test context expansion by comparing results with and without expansion.
    """
    print(f"\n{Fore.BLUE}=== Testing Context Expansion ==={Style.RESET_ALL}")
    print(f"Query: '{query}'")
    
    # Test without context expansion
    print("\nWithout context expansion:")
    results_without_expansion = test_search(db, query, expand_context=False)
    
    # Test with context expansion
    print("\nWith context expansion:")
    results_with_expansion = test_search(db, query, expand_context=True)
    
    # Compare results
    if results_without_expansion and results_with_expansion:
        without_count = len(results_without_expansion)
        with_count = len(results_with_expansion)
        
        print(f"\n{Fore.BLUE}=== Context Expansion Comparison ==={Style.RESET_ALL}")
        print(f"Results without expansion: {without_count}")
        print(f"Results with expansion: {with_count}")
        
        if with_count > without_count:
            print(f"{Fore.GREEN}✓ Context expansion retrieved {with_count - without_count} additional results!{Style.RESET_ALL}")
        elif with_count == without_count:
            print(f"{Fore.YELLOW}⚠ Context expansion did not retrieve additional results.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}⚠ Context expansion retrieved fewer results.{Style.RESET_ALL}")
    
    return results_with_expansion

def run_comprehensive_test(db):
    """
    Run a comprehensive test of the vector database.
    """
    print(f"\n{Fore.BLUE}=== Running Comprehensive Test ==={Style.RESET_ALL}")
    
    all_results = []
    
    for query in TEST_QUERIES:
        results = test_search(db, query)
        if results:
            all_results.append({
                'query': query,
                'results': results
            })
            display_results(results)
    
    # Test context expansion with a specific query
    if TEST_QUERIES:
        context_results = test_context_expansion(db, TEST_QUERIES[0])
    
    return all_results

def query_raw_chunks(db, keyword, limit=5):
    """
    Perform a simple keyword search on raw chunks for testing when embeddings are not ready.
    """
    print(f"\n{Fore.BLUE}=== Direct Firestore Query Test ==={Style.RESET_ALL}")
    print(f"Searching for keyword: '{keyword}' in raw chunks")
    
    try:
        # Query raw chunks that contain the keyword in their text
        # This is a simple contains query, not a semantic search
        results = []
        
        # Get all chunks (inefficient but works for testing)
        chunks = list(db.collection('research_chunks_raw').limit(1000).get())
        print(f"Examining {len(chunks)} raw chunks...")
        
        # Filter chunks that contain the keyword
        for chunk in chunks:
            data = chunk.to_dict()
            if 'text' in data and keyword.lower() in data['text'].lower():
                results.append({
                    'id': chunk.id,
                    'text': data['text'],
                    'metadata': data.get('metadata', {})
                })
                if len(results) >= limit:
                    break
        
        print(f"{Fore.GREEN}Found {len(results)} chunks containing '{keyword}'{Style.RESET_ALL}")
        
        # Display results
        if results:
            table_data = []
            for i, result in enumerate(results):
                metadata = result.get('metadata', {})
                
                # Format text snippet (truncate if too long)
                text = result.get('text', '')
                if len(text) > 200:
                    text = text[:197] + '...'
                
                # Get document info
                title = metadata.get('title', 'Unknown')
                author = metadata.get('primary_author', 'Unknown')
                year = metadata.get('year', 'Unknown')
                section = metadata.get('section', 'Unknown')
                
                # Add to table
                table_data.append([
                    i + 1,
                    f"{author} ({year})",
                    title,
                    section,
                    text
                ])
            
            # Display table
            headers = ["#", "Source", "Title", "Section", "Text Snippet"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        return results
    except Exception as e:
        print(f"{Fore.RED}Error querying raw chunks: {e}{Style.RESET_ALL}")
        return []

def main():
    parser = argparse.ArgumentParser(description='Test the current state of the Misophonia Research Vector Database')
    parser.add_argument('--query', type=str, help='Specific query to test')
    parser.add_argument('--threshold', type=float, default=0.6, help='Similarity threshold (0.0 to 1.0)')
    parser.add_argument('--context', action='store_true', help='Test context expansion')
    parser.add_argument('--comprehensive', action='store_true', help='Run comprehensive test with all test queries')
    parser.add_argument('--raw', action='store_true', help='Query raw chunks directly (for testing when embeddings are not ready)')
    parser.add_argument('--keyword', type=str, default='misophonia', help='Keyword to search for in raw chunks')
    args = parser.parse_args()
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    # Check embedding status
    has_embeddings = get_embedding_status(db)
    
    if args.query:
        # Test specific query
        results = test_search(db, args.query, similarity_threshold=args.threshold)
        display_results(results)
    elif args.context:
        # Test context expansion
        query = args.query if args.query else TEST_QUERIES[0]
        results = test_context_expansion(db, query)
        display_results(results)
    elif args.comprehensive:
        # Run comprehensive test
        run_comprehensive_test(db)
    elif args.raw:
        # Query raw chunks directly
        query_raw_chunks(db, args.keyword)
    else:
        # Default: run a simple test with the first query
        if has_embeddings:
            print(f"\n{Fore.BLUE}=== Running Simple Test ==={Style.RESET_ALL}")
            results = test_search(db, TEST_QUERIES[0])
            display_results(results)
            
            # If no results from semantic search, try raw chunks as fallback
            if not results:
                print(f"\n{Fore.YELLOW}No results from semantic search. Trying raw chunks as fallback...{Style.RESET_ALL}")
                query_raw_chunks(db, "misophonia")
        else:
            print(f"\n{Fore.YELLOW}Skipping search test as no embeddings were found.{Style.RESET_ALL}")
            print("Trying raw chunks instead...")
            query_raw_chunks(db, "misophonia")

if __name__ == "__main__":
    main()
