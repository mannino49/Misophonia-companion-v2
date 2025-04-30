#!/usr/bin/env python3

"""
Script to check Firestore collections and their structure

This script lists all collections in the Firestore database and
examines their structure to help debug issues with the vector database.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import datetime

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

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
        
        # Check each collection
        for collection_name in collections:
            print(f"Examining collection: {collection_name}")
            docs = db.collection(collection_name).limit(3).get()
            doc_list = list(docs)
            print(f"Found {len(doc_list)} documents in {collection_name} collection")
            
            if len(doc_list) > 0:
                # Check the first document's structure
                sample_doc = doc_list[0].to_dict()
                print(f"Sample document ID: {doc_list[0].id}")
                print(f"Document fields: {list(sample_doc.keys())}")
                
                # If this is the research_chunks_raw collection, check if we have the right fields
                if collection_name == 'research_chunks_raw':
                    if 'text' in sample_doc and 'metadata' in sample_doc:
                        print("✅ research_chunks_raw has the expected fields (text, metadata)")
                    else:
                        print("❌ research_chunks_raw is missing expected fields")
                
                # If this is the research_chunks collection, check if we have embeddings
                if collection_name == 'research_chunks':
                    if 'embedding' in sample_doc:
                        embedding = sample_doc['embedding']
                        if isinstance(embedding, list):
                            print(f"✅ research_chunks has embeddings (dimension: {len(embedding)})")
                        else:
                            print(f"❌ research_chunks has embeddings but they are not in list format: {type(embedding)}")
                    else:
                        print("❌ research_chunks is missing embeddings field")
            
            print("\n" + "-"*50 + "\n")
        
        # Check if we have a research_chunks collection
        if 'research_chunks' not in collections:
            print("\n⚠️ The research_chunks collection does not exist!")
            print("This suggests that the Cloud Function is not successfully creating the collection.")
            print("Possible issues:")
            print("1. The Cloud Function might not have proper permissions")
            print("2. There might be an error in the Cloud Function that's not being logged")
            print("3. The database path might be incorrect")
            
            # Check if we can create the collection manually
            print("\nAttempting to create a test document in research_chunks collection...")
            try:
                db.collection('research_chunks').document('test_doc').set({
                    'text': 'This is a test document',
                    'embedding': [0.1] * 10,  # Small test embedding
                    'metadata': {'test': True},
                    'createdAt': firestore.SERVER_TIMESTAMP
                })
                print("✅ Successfully created test document in research_chunks collection")
                print("This suggests the Cloud Function has permission issues or logic errors")
            except Exception as e:
                print(f"❌ Failed to create test document: {e}")
                print("This suggests there might be permission issues with the database")
    
    except Exception as e:
        print(f"Error initializing Firebase: {e}")

if __name__ == "__main__":
    main()
