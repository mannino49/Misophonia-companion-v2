#!/usr/bin/env python3

"""
Test Improved Semantic Search

This script tests the semantic search function with the increased memory allocation.
"""

import os
import time
import json
import requests
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
        print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        return db
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return None

def test_semantic_search(query, filters=None, expand_context=True, timeout=60):
    """
    Test the semantic search Cloud Function with increased timeout.
    """
    try:
        # Get the project ID from the service account file
        with open(SERVICE_ACCOUNT_PATH, 'r') as f:
            service_account = json.load(f)
            project_id = service_account.get('project_id')
        
        if not project_id:
            print("Error: Could not determine project ID from service account file")
            return None
        
        # Construct the Cloud Function URL
        function_url = f"https://us-central1-{project_id}.cloudfunctions.net/semanticSearch"
        
        # Prepare the request data
        request_data = {
            "data": {
                "query": query,
                "filters": filters or {},
                "expandContext": expand_context,
                "page": 1,
                "pageSize": 5
            }
        }
        
        print(f"Sending request to {function_url}")
        print(f"Query: '{query}'")
        print(f"Filters: {json.dumps(filters or {})}")
        print(f"Expand context: {expand_context}")
        
        # Send the request with increased timeout
        response = requests.post(function_url, json=request_data, timeout=timeout)
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"Error: Received status code {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except requests.exceptions.Timeout:
        print(f"Error: Request timed out after {timeout} seconds")
        return None
    except Exception as e:
        print(f"Error testing semantic search: {e}")
        return None

def display_search_results(results):
    """
    Display search results in a readable format.
    """
    if not results or 'results' not in results:
        print("No results to display")
        return
    
    print(f"\nFound {results.get('totalResults', 0)} results (showing page {results.get('page', 1)} of {results.get('totalPages', 1)})\n")
    
    table_data = []
    for i, result in enumerate(results['results']):
        # Extract metadata
        metadata = result.get('metadata', {})
        document_id = metadata.get('document_id', 'Unknown')
        title = metadata.get('title', 'Unknown')
        authors = metadata.get('authors', 'Unknown')
        year = metadata.get('year', 'Unknown')
        section = metadata.get('section', 'Unknown')
        
        # Format the text (truncate if too long)
        text = result.get('text', '')
        if len(text) > 200:
            text = text[:197] + '...'
        
        # Add to table data
        table_data.append([
            i + 1,
            f"{authors} ({year})",
            title,
            section,
            text,
            f"{result.get('score', 0):.4f}"
        ])
    
    # Display the table
    headers = ["#", "Source", "Title", "Section", "Text Snippet", "Score"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Display context if available
    for i, result in enumerate(results['results']):
        context = result.get('context', {})
        if context and (context.get('prev') or context.get('next')):
            print(f"\nContext for result #{i + 1}:")
            
            if context.get('prev'):
                prev_text = context['prev'].get('text', '')
                if len(prev_text) > 100:
                    prev_text = prev_text[:97] + '...'
                print(f"Previous: {prev_text}")
            
            if context.get('next'):
                next_text = context['next'].get('text', '')
                if len(next_text) > 100:
                    next_text = next_text[:97] + '...'
                print(f"Next: {next_text}")

def main():
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("Failed to initialize Firebase. Exiting.")
        return
    
    print("\n==================================================")
    print("Testing Improved Semantic Search")
    print("==================================================\n")
    
    # Test queries
    queries = [
        "What are the symptoms of misophonia?",
        "How is misophonia treated?",
        "What is the relationship between misophonia and anxiety?",
        "What are the neurological mechanisms of misophonia?"
    ]
    
    for query in queries:
        print(f"\n==================================================")
        print(f"Testing query: '{query}'")
        print(f"==================================================\n")
        
        # Test with increased timeout (60 seconds)
        results = test_semantic_search(query, timeout=60)
        
        if results:
            display_search_results(results)
        else:
            print("No results returned")
        
        # Wait a bit between queries to avoid rate limiting
        time.sleep(5)

if __name__ == "__main__":
    main()
