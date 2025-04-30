#!/usr/bin/env python3

"""
Script to check for specific documents in the research_chunks collection

This script specifically looks for the sample chunks we recently added
to verify that they were properly processed by the Cloud Function.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import datetime

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# Sample document IDs to check
SAMPLE_IDS = [
    'sample_chunk_b6527d40',
    'sample_chunk_4e82a7ed',
    'sample_chunk_44ec1da2',
    'sample_chunk_0184f011',
    'sample_chunk_8004fa0a'
]

def json_serializer(obj):
    """Custom JSON serializer to handle Firestore timestamps"""
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    raise TypeError(f'Type {type(obj)} not serializable')

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
        print("Firebase initialized successfully\n")
        
        # Check for our specific sample documents
        print("Checking for sample documents in research_chunks collection...")
        found_count = 0
        
        for doc_id in SAMPLE_IDS:
            doc_ref = db.collection('research_chunks').document(doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                found_count += 1
                doc_data = doc.to_dict()
                
                # Replace embedding with its dimension for display
                if 'embedding' in doc_data:
                    embedding_length = len(doc_data['embedding']) if isinstance(doc_data['embedding'], list) else 'Not a list'
                    doc_data['embedding'] = f"[{embedding_length} dimensional vector]"
                
                print(f"\n✅ Found document {doc_id}")
                print(f"Fields: {list(doc_data.keys())}")
                
                # Print metadata
                if 'metadata' in doc_data:
                    print(f"Metadata: {json.dumps(doc_data['metadata'], default=json_serializer, indent=2)}")
            else:
                print(f"\n❌ Document {doc_id} not found")
        
        print(f"\nFound {found_count} out of {len(SAMPLE_IDS)} sample documents")
        
        if found_count == 0:
            print("\nPossible issues:")
            print("1. The Cloud Function might be using a different database or project")
            print("2. There might be permission issues with the service account")
            print("3. The document IDs might be different from what we expect")
            
            # Check for any documents in the collection
            all_docs = db.collection('research_chunks').limit(10).get()
            all_docs_list = list(all_docs)
            
            print(f"\nTotal documents in research_chunks collection: {len(all_docs_list)}")
            if len(all_docs_list) > 0:
                print("Sample document IDs in collection:")
                for doc in all_docs_list:
                    print(f"- {doc.id}")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
