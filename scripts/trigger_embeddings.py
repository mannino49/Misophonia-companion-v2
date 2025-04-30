#!/usr/bin/env python3

"""
Script to manually trigger embedding generation for sample chunks

This script creates a few sample document chunks in the research_chunks_raw collection
to trigger the Cloud Function for embedding generation.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import time
import uuid

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# Sample text chunks for testing
SAMPLE_CHUNKS = [
    {
        "text": "Misophonia is a condition characterized by strong negative emotional reactions to specific sounds, particularly those made by humans such as chewing, breathing, or repetitive tapping. The term literally means 'hatred of sound' and was first coined in 2001 by audiologists Pawel and Margaret Jastreboff.",
        "metadata": {
            "title": "Introduction to Misophonia",
            "authors": ["Sample Author"],
            "year": 2023,
            "section": "Definition and Background",
            "section_idx": 0,
            "chunk_idx": 0,
            "document_id": "sample_doc_001"
        }
    },
    {
        "text": "Symptoms of misophonia include intense anger, disgust, or anxiety when exposed to trigger sounds. Some individuals report physical sensations such as pressure in the chest, tightness in the shoulders, or a clenched jaw. The condition can significantly impact quality of life, affecting social interactions, work performance, and mental health.",
        "metadata": {
            "title": "Clinical Presentation of Misophonia",
            "authors": ["Sample Researcher"],
            "year": 2024,
            "section": "Symptoms and Impact",
            "section_idx": 1,
            "chunk_idx": 0,
            "document_id": "sample_doc_002"
        }
    },
    {
        "text": "The prevalence of misophonia is not well established, but studies suggest it may affect between 15-20% of the general population to some degree. It appears to be more common in individuals with other conditions such as anxiety disorders, OCD, ADHD, and autism spectrum disorders. The condition often begins in childhood or early adolescence.",
        "metadata": {
            "title": "Epidemiology of Misophonia",
            "authors": ["Sample Epidemiologist"],
            "year": 2022,
            "section": "Prevalence and Demographics",
            "section_idx": 0,
            "chunk_idx": 1,
            "document_id": "sample_doc_003"
        }
    },
    {
        "text": "Current treatment approaches for misophonia include cognitive-behavioral therapy (CBT), sound therapy, mindfulness-based interventions, and in some cases, medication for comorbid conditions. There is no FDA-approved medication specifically for misophonia, and evidence for treatment efficacy remains limited.",
        "metadata": {
            "title": "Treatment Approaches for Misophonia",
            "authors": ["Sample Clinician"],
            "year": 2023,
            "section": "Therapeutic Interventions",
            "section_idx": 2,
            "chunk_idx": 0,
            "document_id": "sample_doc_004"
        }
    },
    {
        "text": "Neuroimaging studies have identified abnormal functional connectivity between the anterior insular cortex and other regions involved in emotional processing and regulation in individuals with misophonia. This suggests that misophonia may involve alterations in how the brain processes certain sounds and the emotional responses they trigger.",
        "metadata": {
            "title": "Neurobiology of Misophonia",
            "authors": ["Sample Neuroscientist"],
            "year": 2024,
            "section": "Neural Mechanisms",
            "section_idx": 1,
            "chunk_idx": 2,
            "document_id": "sample_doc_005"
        }
    }
]

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
    
    # Add sample chunks to trigger embedding generation
    print("\nAdding sample chunks to research_chunks_raw collection...")
    for i, chunk in enumerate(SAMPLE_CHUNKS):
        # Generate a unique ID for the chunk
        chunk_id = f"sample_chunk_{uuid.uuid4().hex[:8]}"
        
        # Add the chunk to the research_chunks_raw collection
        db.collection('research_chunks_raw').document(chunk_id).set({
            "text": chunk["text"],
            "metadata": chunk["metadata"],
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        
        print(f"Added chunk {i+1}/{len(SAMPLE_CHUNKS)} with ID: {chunk_id}")
        
        # Add a small delay to avoid overwhelming the Cloud Function
        time.sleep(1)
    
    print("\nSample chunks added successfully!")
    print("The Cloud Function should now be generating embeddings for these chunks.")
    print("Wait a few minutes and then check the research_chunks collection.")

if __name__ == "__main__":
    main()
