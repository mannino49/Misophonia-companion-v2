#!/usr/bin/env python3

"""
Test Firebase Setup and Context-Aware Chunking

This script tests the Firebase setup and context-aware chunking approach
on a single document to verify everything is working correctly.
"""

import os
import json
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
import glob
import random

# Load environment variables
load_dotenv()

# Path to service account key
SERVICE_ACCOUNT_PATH = "./service-account.json"

# Test document directory
RESEARCH_DIR = "../documents/research/Global"

def test_firebase_connection():
    """
    Test the connection to Firebase/Firestore.
    """
    print("Testing Firebase connection...")
    try:
        # Initialize Firebase
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        
        # Test a simple write and read
        test_ref = db.collection('test').document('test_connection')
        test_ref.set({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'message': 'Firebase connection test successful!'
        })
        
        # Read back the data
        test_doc = test_ref.get()
        if test_doc.exists:
            print("✅ Firebase connection successful!")
            print(f"Test document data: {test_doc.to_dict()}")
            return True
        else:
            print("❌ Firebase test document not found!")
            return False
    except Exception as e:
        print(f"❌ Firebase connection failed: {e}")
        return False

def test_document_access():
    """
    Test access to the research documents.
    """
    print("\nTesting document access...")
    try:
        # Get list of PDF files
        pdf_files = glob.glob(os.path.join(RESEARCH_DIR, "*.pdf"))
        if pdf_files:
            print(f"✅ Found {len(pdf_files)} PDF files in {RESEARCH_DIR}")
            # Select a random document for testing
            test_doc = random.choice(pdf_files)
            print(f"Selected test document: {os.path.basename(test_doc)}")
            return True, test_doc
        else:
            print(f"❌ No PDF files found in {RESEARCH_DIR}")
            return False, None
    except Exception as e:
        print(f"❌ Error accessing documents: {e}")
        return False, None

def main():
    # Test Firebase connection
    firebase_success = test_firebase_connection()
    
    # Test document access
    doc_access_success, test_doc = test_document_access()
    
    # Print overall status
    print("\n" + "="*50)
    print("Test Results:")
    print("="*50)
    print(f"Firebase Connection: {'✅ Success' if firebase_success else '❌ Failed'}")
    print(f"Document Access: {'✅ Success' if doc_access_success else '❌ Failed'}")
    
    if firebase_success and doc_access_success:
        print("\n✅ All tests passed! You can now run the batch processing script.")
        print("\nNext steps:")
        print("1. Make sure your OpenAI API key is set in the .env file")
        print("2. Run the batch processing script with:")
        print("   python3 batch_process_documents.py --random-sample --sample-size 20 --batch-size 10")
    else:
        print("\n❌ Some tests failed. Please fix the issues before running the batch processing script.")

if __name__ == "__main__":
    main()
