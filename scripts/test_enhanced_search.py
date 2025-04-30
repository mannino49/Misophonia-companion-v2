#!/usr/bin/env python3

"""
Script to test enhanced semantic search functionality

This script tests the enhanced semantic search Cloud Function with
context expansion, metadata filtering, and pagination capabilities.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
import requests
import json
import os
import time

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Sample test queries with different filter combinations
TEST_SCENARIOS = [
    {
        "name": "Basic search with no filters",
        "query": "What are the symptoms of misophonia?",
        "filters": {},
        "expandContext": True,
        "page": 1,
        "pageSize": 3
    },
    {
        "name": "Search with year filter",
        "query": "What are the symptoms of misophonia?",
        "filters": {"year": 2023},
        "expandContext": True,
        "page": 1,
        "pageSize": 3
    },
    {
        "name": "Search with author filter",
        "query": "What are the symptoms of misophonia?",
        "filters": {"authors": ["Williams, R."]},
        "expandContext": True,
        "page": 1,
        "pageSize": 3
    },
    {
        "name": "Search with year range filter",
        "query": "What are the symptoms of misophonia?",
        "filters": {"year": [2020, 2022]},
        "expandContext": True,
        "page": 1,
        "pageSize": 3
    },
    {
        "name": "Search with pagination (page 2)",
        "query": "misophonia",
        "filters": {},
        "expandContext": True,
        "page": 2,
        "pageSize": 3
    },
    {
        "name": "Search without context expansion",
        "query": "What are the symptoms of misophonia?",
        "filters": {},
        "expandContext": False,
        "page": 1,
        "pageSize": 3
    },
    {
        "name": "Search with higher similarity threshold",
        "query": "What are the symptoms of misophonia?",
        "filters": {},
        "expandContext": True,
        "similarityThreshold": 0.75,
        "page": 1,
        "pageSize": 3
    }
]

def main():
    # Check if OpenAI API Key is set
    if not OPENAI_API_KEY:
        print("\nu26a0ufe0f OPENAI_API_KEY environment variable not set!")
        print("Please set the environment variable before running this script:")
        print("export OPENAI_API_KEY=your_api_key_here")
        return
    
    # Initialize Firebase with service account
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        
        # Get the project ID for calling Cloud Functions
        project_id = firebase_admin.get_app().project_id
        # Cloud Function URL
        function_url = f'https://us-central1-{project_id}.cloudfunctions.net/semanticSearch'
        
        # Test database connection
        db = firestore.client()
        print("Testing database connection...")
        collections = [collection.id for collection in db.collections()]
        print(f"Available collections: {collections}")
        print("Firebase initialized successfully\n")
        
        # Check if we have documents in research_chunks collection
        chunks = db.collection('research_chunks').get()
        chunk_list = list(chunks)
        print(f"Found {len(chunk_list)} documents in research_chunks collection")
        
        if len(chunk_list) == 0:
            print("\nu26a0ufe0f No documents found in research_chunks collection!")
            print("Please make sure to create sample documents first.")
            return
        
        # Run test scenarios
        print("\n" + "-"*50)
        print("TESTING ENHANCED SEMANTIC SEARCH")
        print("-"*50)
        
        for i, scenario in enumerate(TEST_SCENARIOS):
            print(f"\nScenario {i+1}: {scenario['name']}")
            print(f"Query: '{scenario['query']}'")
            print(f"Filters: {json.dumps(scenario['filters'])}")
            print(f"Expand Context: {scenario['expandContext']}")
            print(f"Page: {scenario['page']}, Page Size: {scenario['pageSize']}")
            
            if 'similarityThreshold' in scenario:
                print(f"Similarity Threshold: {scenario['similarityThreshold']}")
            
            # Call the Cloud Function
            try:
                # Call the Cloud Function via HTTP
                payload = {
                    'data': {
                        'query': scenario['query'],
                        'filters': scenario['filters'],
                        'expandContext': scenario['expandContext'],
                        'page': scenario['page'],
                        'pageSize': scenario['pageSize'],
                        'similarityThreshold': scenario.get('similarityThreshold', 0.6)
                    }
                }
                
                response = requests.post(function_url, json=payload)
                
                if response.status_code != 200:
                    raise Exception(f'Error calling Cloud Function: {response.text}')
                
                # Process the result
                data = response.json()['result']
                
                print(f"\nResults: {len(data['results'])} of {data['totalResults']} total")
                print(f"Page {data['page']} of {data['totalPages']}")
                
                # Display results
                for j, result in enumerate(data['results']):
                    print(f"\nResult {j+1} (similarity: {result['similarity']:.4f})")
                    print(f"ID: {result['id']}")
                    print(f"Text: {result['text'][:150]}..." if len(result['text']) > 150 else f"Text: {result['text']}")
                    
                    # Display metadata
                    if 'metadata' in result:
                        print(f"Title: {result['metadata'].get('title', 'N/A')}")
                        print(f"Authors: {', '.join(result['metadata'].get('authors', ['N/A']))}")
                        print(f"Year: {result['metadata'].get('year', 'N/A')}")
                    
                    # Display context if available
                    if 'context' in result and scenario['expandContext']:
                        if result['context']['prev']:
                            print(f"\n  Previous Context:")
                            print(f"  {result['context']['prev']['text'][:100]}..." if len(result['context']['prev']['text']) > 100 else f"  {result['context']['prev']['text']}")
                        
                        if result['context']['next']:
                            print(f"\n  Next Context:")
                            print(f"  {result['context']['next']['text'][:100]}..." if len(result['context']['next']['text']) > 100 else f"  {result['context']['next']['text']}")
                
                print("\n" + "-"*50)
            
            except Exception as e:
                print(f"Error calling Cloud Function: {e}")
                print("\n" + "-"*50)
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
