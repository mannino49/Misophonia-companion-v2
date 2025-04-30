#!/usr/bin/env python3

"""
Script to check Firestore configuration and project details

This script examines the Firestore configuration to help debug
issues with database access between Cloud Functions and local scripts.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json
import os

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

def main():
    # Initialize Firebase with service account
    print(f"Initializing Firebase with service account: {SERVICE_ACCOUNT_PATH}")
    try:
        # Load service account info to get project details
        with open(SERVICE_ACCOUNT_PATH, 'r') as f:
            service_account = json.load(f)
        
        project_id = service_account.get('project_id')
        print(f"Service account project ID: {project_id}")
        
        # Initialize Firebase
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Get client configuration
        client_info = {
            'project_id': firebase_admin.get_app().project_id,
            'database_id': '(default)'  # Firestore uses (default) as the default database ID
        }
        print(f"Firestore client configuration:")
        print(f"- Project ID: {client_info['project_id']}")
        print(f"- Database ID: {client_info['database_id']}")
        
        # List all collections
        print("\nListing all collections:")
        collections = [collection.id for collection in db.collections()]
        print(f"Collections: {collections}")
        
        # Check research_chunks collection
        if 'research_chunks' in collections:
            print("\nExamining research_chunks collection:")
            docs = db.collection('research_chunks').get()
            doc_list = list(docs)
            print(f"Total documents: {len(doc_list)}")
            
            if len(doc_list) > 0:
                print("Document IDs:")
                for doc in doc_list:
                    print(f"- {doc.id}")
        else:
            print("\nresearch_chunks collection not found!")
        
        # Check for any documents with IDs starting with 'sample_chunk_'
        print("\nSearching for documents with IDs starting with 'sample_chunk_':")
        found_docs = []
        
        for collection_name in collections:
            query = db.collection(collection_name).where('__name__', '>=', 'sample_chunk_').where('__name__', '<=', 'sample_chunk_z')
            results = query.get()
            
            for doc in results:
                found_docs.append({'collection': collection_name, 'id': doc.id})
        
        if found_docs:
            print(f"Found {len(found_docs)} documents:")
            for doc in found_docs:
                print(f"- Collection: {doc['collection']}, ID: {doc['id']}")
        else:
            print("No documents found with IDs starting with 'sample_chunk_'")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
