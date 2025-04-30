#!/usr/bin/env python3

"""
Script to create sample documents with embeddings for testing

This script creates a set of sample documents with meaningful content
about misophonia and generates embeddings for them to enable proper
testing of the semantic search functionality.
"""

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import requests
import json
import os
import time
import uuid

# Path to service account key
SERVICE_ACCOUNT_PATH = "/Users/mannino/CascadeProjects/Misophonia Guide/scripts/service-account.json"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Sample documents about misophonia
SAMPLE_DOCUMENTS = [
    {
        "text": "Misophonia is a condition characterized by strong negative emotional reactions to specific sounds, particularly those made by humans such as chewing, breathing, or repetitive tapping. The term literally means 'hatred of sound' and was first coined in 2001 by audiologists Pawel and Margaret Jastreboff. Unlike general noise sensitivity, misophonia is triggered by specific patterns of sounds and often involves an extreme emotional response.",
        "metadata": {
            "title": "Introduction to Misophonia",
            "authors": ["Johnson, S.", "Smith, A."],
            "year": 2022,
            "section": "Definition and Background",
            "section_idx": 0,
            "chunk_idx": 0,
            "document_id": "doc_intro_001"
        }
    },
    {
        "text": "Symptoms of misophonia include intense anger, disgust, or anxiety when exposed to trigger sounds. Some individuals report physical sensations such as pressure in the chest, tightness in the shoulders, or a clenched jaw. The condition can significantly impact quality of life, affecting social interactions, work performance, and mental health. Many individuals with misophonia develop avoidance behaviors to prevent exposure to trigger sounds.",
        "metadata": {
            "title": "Clinical Presentation of Misophonia",
            "authors": ["Williams, R.", "Davis, M."],
            "year": 2023,
            "section": "Symptoms and Impact",
            "section_idx": 1,
            "chunk_idx": 0,
            "document_id": "doc_clinical_002"
        }
    },
    {
        "text": "The prevalence of misophonia is not well established, but studies suggest it may affect between 15-20% of the general population to some degree. It appears to be more common in individuals with other conditions such as anxiety disorders, OCD, ADHD, and autism spectrum disorders. The condition often begins in childhood or early adolescence, with the average age of onset around 12 years, though it can develop at any age.",
        "metadata": {
            "title": "Epidemiology of Misophonia",
            "authors": ["Thompson, L.", "Garcia, J."],
            "year": 2021,
            "section": "Prevalence and Demographics",
            "section_idx": 0,
            "chunk_idx": 1,
            "document_id": "doc_epidem_003"
        }
    },
    {
        "text": "Current treatment approaches for misophonia include cognitive-behavioral therapy (CBT), sound therapy, mindfulness-based interventions, and in some cases, medication for comorbid conditions. There is no FDA-approved medication specifically for misophonia, and evidence for treatment efficacy remains limited. CBT techniques such as exposure therapy and cognitive restructuring have shown promise in helping individuals manage their reactions to trigger sounds.",
        "metadata": {
            "title": "Treatment Approaches for Misophonia",
            "authors": ["Anderson, K.", "Miller, P."],
            "year": 2023,
            "section": "Therapeutic Interventions",
            "section_idx": 2,
            "chunk_idx": 0,
            "document_id": "doc_treatment_004"
        }
    },
    {
        "text": "Neuroimaging studies have identified abnormal functional connectivity between the anterior insular cortex and other regions involved in emotional processing and regulation in individuals with misophonia. This suggests that misophonia may involve alterations in how the brain processes certain sounds and the emotional responses they trigger. Some research indicates hyperactivation of the salience network and altered connectivity with the default mode network.",
        "metadata": {
            "title": "Neurobiology of Misophonia",
            "authors": ["Kumar, S.", "Wilson, E."],
            "year": 2024,
            "section": "Neural Mechanisms",
            "section_idx": 1,
            "chunk_idx": 2,
            "document_id": "doc_neuro_005"
        }
    },
    {
        "text": "Common triggers for misophonia include oral sounds (chewing, slurping, swallowing), nasal sounds (sniffling, breathing), repetitive sounds (tapping, clicking), and certain visual stimuli associated with these sounds. The severity of reactions often depends on contextual factors such as the relationship with the person making the sound, the environment, and the individual's stress level. Some people report that sounds made by family members or close friends trigger stronger reactions than those made by strangers.",
        "metadata": {
            "title": "Misophonia Triggers and Contextual Factors",
            "authors": ["Brown, H.", "Taylor, R."],
            "year": 2022,
            "section": "Trigger Analysis",
            "section_idx": 3,
            "chunk_idx": 1,
            "document_id": "doc_triggers_006"
        }
    },
    {
        "text": "Misophonia is often comorbid with anxiety disorders, obsessive-compulsive disorder (OCD), attention deficit hyperactivity disorder (ADHD), and autism spectrum disorders. The relationship between misophonia and these conditions is complex and not fully understood. Some researchers propose that shared neurobiological mechanisms may underlie these comorbidities, while others suggest that one condition may predispose individuals to develop the other.",
        "metadata": {
            "title": "Comorbidities in Misophonia",
            "authors": ["Martinez, C.", "Lee, S."],
            "year": 2023,
            "section": "Psychiatric Comorbidities",
            "section_idx": 2,
            "chunk_idx": 3,
            "document_id": "doc_comorbid_007"
        }
    },
    {
        "text": "The diagnosis of misophonia remains challenging due to the lack of standardized diagnostic criteria in major classification systems like DSM-5 or ICD-11. Several diagnostic tools have been developed, including the Misophonia Questionnaire (MQ), the Amsterdam Misophonia Scale (A-MISO-S), and the Duke Misophonia Questionnaire (DMQ). These assessments evaluate the presence and severity of symptoms, impact on daily functioning, and emotional and behavioral responses to trigger sounds.",
        "metadata": {
            "title": "Diagnostic Approaches to Misophonia",
            "authors": ["Roberts, J.", "Phillips, A."],
            "year": 2021,
            "section": "Assessment Tools",
            "section_idx": 1,
            "chunk_idx": 0,
            "document_id": "doc_diagnosis_008"
        }
    },
    {
        "text": "The impact of misophonia on quality of life can be substantial. Many individuals report difficulties in social situations, strained relationships with family members, challenges in educational or work environments, and significant emotional distress. Avoidance behaviors can lead to social isolation, and the anticipatory anxiety about encountering trigger sounds can further limit participation in daily activities. Support groups and online communities have emerged as important resources for individuals coping with misophonia.",
        "metadata": {
            "title": "Psychosocial Impact of Misophonia",
            "authors": ["Chen, L.", "Harris, D."],
            "year": 2024,
            "section": "Quality of Life",
            "section_idx": 4,
            "chunk_idx": 1,
            "document_id": "doc_impact_009"
        }
    },
    {
        "text": "Recent advances in misophonia research include the development of more targeted therapeutic approaches, improved understanding of the neurobiological mechanisms, and exploration of potential genetic factors. Ongoing studies are investigating the efficacy of novel interventions such as audio-neural retraining, targeted cognitive therapies, and pharmacological approaches targeting specific neurotransmitter systems. The field is moving toward a more personalized approach to treatment based on individual symptom profiles and comorbidities.",
        "metadata": {
            "title": "Current Research Directions in Misophonia",
            "authors": ["Patel, R.", "White, J."],
            "year": 2024,
            "section": "Emerging Treatments",
            "section_idx": 3,
            "chunk_idx": 2,
            "document_id": "doc_research_010"
        }
    }
]

def generate_embedding(text):
    """Generate embedding for text using OpenAI API"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Truncate text if it's too long (OpenAI has token limits)
    truncated_text = text[:8000] if len(text) > 8000 else text
    
    # Make API call to OpenAI embeddings endpoint
    response = requests.post(
        'https://api.openai.com/v1/embeddings',
        headers={
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'input': truncated_text,
            'model': 'text-embedding-3-small'  # Using OpenAI's latest embedding model
        }
    )
    
    if response.status_code != 200:
        raise ValueError(f"Error from OpenAI API: {response.text}")
    
    # Extract the embedding from the response
    embedding = response.json()['data'][0]['embedding']
    print(f"Generated embedding with dimension: {len(embedding)}")
    return embedding

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
        db = firestore.client()
        
        # Test database connection
        print("Testing database connection...")
        collections = [collection.id for collection in db.collections()]
        print(f"Available collections: {collections}")
        print("Firebase initialized successfully\n")
        
        # Check if we already have sample documents
        existing_docs = db.collection('research_chunks').where('metadata.document_id', '>=', 'doc_').where('metadata.document_id', '<=', 'doc_z').get()
        existing_docs_list = list(existing_docs)
        
        if len(existing_docs_list) > 0:
            print(f"Found {len(existing_docs_list)} existing sample documents")
            print("Do you want to delete these and create new ones? (y/n)")
            response = input().lower()
            
            if response == 'y':
                print("Deleting existing sample documents...")
                for doc in existing_docs_list:
                    doc.reference.delete()
                print(f"Deleted {len(existing_docs_list)} documents")
            else:
                print("Keeping existing sample documents. Script will now exit.")
                return
        
        # Create sample documents with embeddings
        print("\nCreating sample documents with embeddings...")
        
        for i, doc_data in enumerate(SAMPLE_DOCUMENTS):
            print(f"\nProcessing document {i+1}/{len(SAMPLE_DOCUMENTS)}")
            print(f"Title: {doc_data['metadata']['title']}")
            
            # Generate embedding for the text
            print("Generating embedding...")
            embedding = generate_embedding(doc_data['text'])
            
            # Create document ID
            doc_id = f"sample_{uuid.uuid4().hex[:8]}"
            
            # Store document in research_chunks collection
            db.collection('research_chunks').document(doc_id).set({
                'text': doc_data['text'],
                'embedding': embedding,
                'metadata': doc_data['metadata'],
                'createdAt': firestore.SERVER_TIMESTAMP
            })
            
            print(f"Created document with ID: {doc_id}")
            time.sleep(1)  # Brief pause to avoid rate limiting
        
        print("\nSample documents created successfully!")
        print("You can now test the semantic search functionality.")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
