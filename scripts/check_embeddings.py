#!/usr/bin/env python3

"""
Script to check if embeddings have been generated

This script checks the research_chunks collection to see if embeddings
have been generated for our sample chunks.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import datetime
from google.cloud.firestore_v1.types import Document

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

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
        return
    
    # Check research_chunks collection
    print("\nChecking research_chunks collection for embeddings...")
    chunks = db.collection('research_chunks').limit(10).get()
    chunk_list = list(chunks)
    
    print(f"Found {len(chunk_list)} documents in research_chunks collection")
    
    if len(chunk_list) > 0:
        print("\nSample documents:")
        for i, chunk in enumerate(chunk_list[:3]):  # Show up to 3 samples
            doc = chunk.to_dict()
            # Replace embedding vector with its length for display
            if 'embedding' in doc:
                embedding_length = len(doc['embedding']) if isinstance(doc['embedding'], list) else 'Not a list'
                doc['embedding'] = f"[{embedding_length} dimensional vector]"
            
            print(f"\nDocument {i+1}:")
            # Custom JSON serialization to handle Firestore timestamps
            def json_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                raise TypeError(f'Type {type(obj)} not serializable')
            
            print(json.dumps(doc, indent=2, default=json_serializer))
    else:
        print("\nNo documents found in research_chunks collection.")
        print("The Cloud Function might still be processing or there might be an issue.")
        
        # Check raw chunks collection
        raw_chunks = db.collection('research_chunks_raw').limit(5).get()
        raw_chunk_list = list(raw_chunks)
        print(f"\nFound {len(raw_chunk_list)} documents in research_chunks_raw collection")
        
        if len(raw_chunk_list) > 0:
            print("Sample raw chunk:")
            raw_doc = raw_chunk_list[0].to_dict()
            # Custom JSON serialization to handle Firestore timestamps
            def json_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                raise TypeError(f'Type {type(obj)} not serializable')
            
            print(json.dumps(raw_doc, indent=2, default=json_serializer))

if __name__ == "__main__":
    main()
