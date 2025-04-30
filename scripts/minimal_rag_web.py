#!/usr/bin/env python3

import os
import sys
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore
import openai
import numpy as np
from dotenv import load_dotenv
import re
from flask import Flask, render_template_string, request, jsonify

# Load environment variables
load_dotenv()

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Firebase
def initialize_firebase():
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Initialize with service account
        service_account_path = './service-account.json'
        print(f"Initializing Firebase with service account: {service_account_path}")
        if not os.path.exists(service_account_path):
            logger.error(f"Service account file not found at {service_account_path}")
            sys.exit(1)
            
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
        
    return firestore.client()

# Generate embedding for the query
def generate_embedding(text):
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        embedding = response.data[0].embedding
        print(f"Successfully generated query embedding with dimension {len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

# Semantic search function
def semantic_search(query, limit=10):
    print(f"\n--- Semantic Search ---\n")
    print(f"Performing semantic search for: '{query}' with limit {limit}")
    db = initialize_firebase()
    
    # Generate embedding for the query
    print(f"Generating embedding for query: '{query}'")
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []
    
    # Fetch chunks with embeddings
    print("Fetching chunks with embeddings...")
    chunks_ref = db.collection('research_chunks')
    chunks = chunks_ref.limit(5000).stream()  # Increased to 5000 for better coverage
    
    # Calculate similarity scores
    print("Calculating similarity scores...")
    results = []
    skipped = 0
    processed = 0
    
    for chunk in chunks:
        processed += 1
        chunk_data = chunk.to_dict()
        
        if 'embedding' not in chunk_data:
            skipped += 1
            continue
            
        chunk_embedding = chunk_data['embedding']
        
        # Calculate cosine similarity
        similarity = np.dot(query_embedding, chunk_embedding) / \
                    (np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding))
        
        if similarity > 0.60:  # Further lowered threshold for better diversity
            results.append({
                'chunk_id': chunk.id,
                'text': chunk_data.get('text', ''),
                'metadata': chunk_data.get('metadata', {}),
                'similarity': float(similarity),
                'match_type': f"Semantic ({similarity:.4f})"
            })
    
    print(f"Processed {processed} chunks, skipped {skipped} chunks")
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

# Keyword search function
def keyword_search(query, limit=10):
    print(f"\n--- Keyword Search ---\n")
    print(f"Performing keyword search for: '{query}' with limit {limit}")
    db = initialize_firebase()
    
    # Fetch raw chunks
    print("Fetching raw chunks...")
    raw_chunks_ref = db.collection('research_chunks_raw')
    raw_chunks = raw_chunks_ref.limit(5000).stream()  # Increased to 5000 for better coverage
    raw_chunks_list = [chunk.to_dict() for chunk in raw_chunks]
    print(f"Found {len(raw_chunks_list)} raw chunks")
    
    # Extract search terms from query
    search_terms = query.lower().split()
    print(f"Expanded search terms: {search_terms}")
    
    # Define additional related terms for misophonia topics
    topic_expansions = {
        'treatment': ['therapy', 'intervention', 'approach', 'management', 'technique', 'strategy', 'protocol'],
        'symptom': ['sign', 'manifestation', 'indication', 'characteristic', 'feature'],
        'trigger': ['stimulus', 'sound', 'noise', 'cue', 'provocation', 'elicit'],
        'coping': ['manage', 'deal', 'handle', 'strategy', 'technique', 'skill'],
        'anxiety': ['anxious', 'stress', 'distress', 'fear', 'worry', 'panic'],
        'anger': ['rage', 'irritation', 'frustration', 'annoyance', 'irritability'],
        'brain': ['neural', 'neurological', 'cognitive', 'neuroanatomical', 'neurobiological'],
        'children': ['child', 'adolescent', 'teen', 'youth', 'pediatric', 'young'],
        'comorbid': ['comorbidity', 'coexisting', 'concurrent', 'accompanying', 'associated']
    }
    
    # Expand search terms with related terms
    expanded_terms = search_terms.copy()
    for term in search_terms:
        for topic, related_terms in topic_expansions.items():
            if term in topic or topic in term:
                expanded_terms.extend(related_terms)
    
    # Remove duplicates and very common words
    common_words = ['the', 'and', 'or', 'in', 'of', 'to', 'a', 'is', 'that', 'for', 'on', 'with']
    expanded_terms = [term for term in expanded_terms if term not in common_words]
    expanded_terms = list(set(expanded_terms))
    print(f"Expanded search terms: {expanded_terms}")
    
    # Search for matching chunks
    print("Searching for matching chunks...")
    results = []
    
    for chunk in raw_chunks_list:
        if 'text' not in chunk:
            continue
            
        text = chunk['text'].lower()
        metadata = chunk.get('metadata', {})
        
        # Count matches for each term
        match_count = 0
        for term in expanded_terms:
            if term in text:
                match_count += 1
        
        # Calculate a simple relevance score based on match count
        if match_count > 0:
            relevance = match_count / len(expanded_terms)
            
            # Boost score for exact phrase matches
            if query.lower() in text:
                relevance += 0.3
            
            # Only include if relevance is above threshold
            if relevance > 0.10:  # Further lowered threshold for keyword search
                results.append({
                    'chunk_id': metadata.get('chunk_id', 'unknown'),
                    'text': chunk['text'],
                    'metadata': metadata,
                    'similarity': float(relevance),
                    'match_type': f"Keyword ({relevance:.4f})"
                })
    
    print(f"Found {len(results)} matching chunks")
    
    # Sort by relevance score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

# Combined search function
def comprehensive_search(query, limit=10):
    print(f"\n==================================================\nSearching for: '{query}'\n==================================================\n")
    
    # Perform semantic search
    semantic_results = semantic_search(query, limit=limit*3)  # Get even more results for diversity
    
    # Perform keyword search
    keyword_results = keyword_search(query, limit=limit*3)  # Get even more results for diversity
    
    # Combine results with document diversity
    print("\n--- Combining Results for Document Diversity ---\n")
    
    # Print information about available documents
    semantic_doc_ids = set()
    for result in semantic_results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        if doc_id:
            semantic_doc_ids.add(doc_id)
    print(f"Semantic search found results from {len(semantic_doc_ids)} unique documents")
    
    keyword_doc_ids = set()
    for result in keyword_results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        if doc_id:
            keyword_doc_ids.add(doc_id)
    print(f"Keyword search found results from {len(keyword_doc_ids)} unique documents")
    
    # Track documents to ensure diversity
    combined_results = []
    seen_chunk_ids = set()
    seen_doc_ids = set()
    
    # Add semantic results first (they're usually more relevant)
    for result in semantic_results:
        chunk_id = result.get('chunk_id')
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        source = metadata.get('source', 'Unknown')
        title = metadata.get('title', 'Unknown')
        
        # Debug document information
        print(f"Considering semantic result - Doc ID: {doc_id}, Source: {source}, Title: {title}")
        
        if chunk_id not in seen_chunk_ids:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
            if doc_id:
                seen_doc_ids.add(doc_id)
                print(f"  Added semantic result from document {doc_id}")
    
    # Add keyword results that aren't duplicates
    for result in keyword_results:
        chunk_id = result.get('chunk_id')
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        source = metadata.get('source', 'Unknown')
        title = metadata.get('title', 'Unknown')
        
        # Debug document information
        print(f"Considering keyword result - Doc ID: {doc_id}, Source: {source}, Title: {title}")
        
        if chunk_id not in seen_chunk_ids:
            # Prioritize results from documents we haven't seen yet
            if doc_id and doc_id not in seen_doc_ids:
                combined_results.append(result)
                seen_chunk_ids.add(chunk_id)
                seen_doc_ids.add(doc_id)
                print(f"  Added keyword result from document {doc_id}")
    
    # Sort by similarity score
    combined_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Ensure document diversity in final results
    final_results = []
    final_doc_ids = set()
    doc_count = {}
    
    # First pass: add one result from each unique document
    print("\nFirst pass: Adding one result from each unique document")
    for result in combined_results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        source = metadata.get('source', 'Unknown')
        
        if doc_id and doc_id not in final_doc_ids and len(final_results) < limit:
            final_results.append(result)
            final_doc_ids.add(doc_id)
            doc_count[doc_id] = 1
            print(f"  Added first result from document {doc_id}, source: {source}")
    
    # Second pass: fill remaining slots with best results
    print("\nSecond pass: Filling remaining slots")
    for result in combined_results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        source = metadata.get('source', 'Unknown')
        
        # Limit to 2 chunks per document for diversity
        if result not in final_results and len(final_results) < limit:
            if not doc_id:
                print(f"  Adding result with no document ID")
                final_results.append(result)
            elif doc_count.get(doc_id, 0) < 2:
                final_results.append(result)
                doc_count[doc_id] = doc_count.get(doc_id, 0) + 1
                print(f"  Added additional result from document {doc_id}, source: {source}")
    
    # Sort final results by similarity for display
    final_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    print(f"\nFound {len(final_results)} results from {len(final_doc_ids)} unique documents\n")
    
    return final_results

# Generate RAG response
def generate_rag_response(query, search_results, max_tokens=1000):
    try:
        print("\n--- RAG Response ---\n")
        # Format search results for prompt
        formatted_results = ""
        for i, result in enumerate(search_results, 1):
            metadata = result.get('metadata', {})
            source = metadata.get('source', 'Unknown')
            if isinstance(source, list):
                source_str = f"[{''.join(source)}]"
            else:
                source_str = f"[{source}]"
                
            year = metadata.get('year', 'None')
            title = metadata.get('title', 'Unknown Title')
            section = metadata.get('section', 'Unknown Section')
            text = result.get('text', '')
            
            formatted_results += f"Source {i}: {source_str} ({year}). {title}. {section}\n"
            formatted_results += f"Text: {text}\n\n"
        
        # Prepare prompt with search results
        prompt = f"""You are an AI assistant specialized in misophonia, a condition where specific sounds trigger strong emotional reactions.
        
Based on the following research information, please answer this question: "{query}"

Research information:
{formatted_results}

Provide a comprehensive, evidence-based answer that directly addresses the question. 
Cite specific sources from the research information when making claims.
If the research information doesn't contain relevant details to answer the question, acknowledge the limitations of the available information.
"""
        
        # Generate response
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides evidence-based information about misophonia based on scientific research."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generating RAG response: {e}")
        return f"Error generating response: {str(e)}"

# HTML template for the interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Misophonia Research Guide</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        form {
            margin-bottom: 20px;
        }
        input[type="text"] {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-bottom: 10px;
        }
        .form-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        select {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        input[type="submit"] {
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        input[type="submit"]:hover {
            background-color: #45a049;
        }
        .results {
            margin-top: 20px;
        }
        .result {
            margin-bottom: 15px;
            padding: 15px;
            background-color: #f9f9f9;
            border-left: 3px solid #4CAF50;
        }
        .source {
            font-weight: bold;
            color: #333;
        }
        .similarity {
            color: #666;
            font-size: 0.9em;
        }
        .response {
            margin-top: 20px;
            padding: 20px;
            background-color: #e9f7ef;
            border-radius: 5px;
            border-left: 5px solid #2ecc71;
        }
        .loading {
            text-align: center;
            display: {{ 'block' if loading else 'none' }};
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 2s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Misophonia Research Guide</h1>
        <p style="text-align: center;">Search across 128 research documents with semantic and keyword-based retrieval</p>
        
        <form method="POST" action="/">
            <input type="text" name="query" placeholder="Ask a question about misophonia..." value="{{ query }}" required>
            
            <div class="form-row">
                <div>
                    <label for="limit">Number of sources:</label>
                    <select name="limit" id="limit">
                        <option value="5" {% if limit == 5 %}selected{% endif %}>5</option>
                        <option value="10" {% if limit == 10 or not limit %}selected{% endif %}>10</option>
                        <option value="15" {% if limit == 15 %}selected{% endif %}>15</option>
                        <option value="20" {% if limit == 20 %}selected{% endif %}>20</option>
                    </select>
                </div>
                <input type="submit" value="Search">
            </div>
        </form>
        
        <div class="loading">
            <div class="spinner"></div>
            <p>Searching research documents and generating response...</p>
        </div>
        
        {% if response %}
            <div class="response">
                <h2>Research-Based Answer</h2>
                <p>{{ response|replace('\n', '<br>')|safe }}</p>
            </div>
        {% endif %}
        
        {% if results %}
            <div class="results">
                <h2>Source Documents ({{ unique_doc_count }} unique documents)</h2>
                {% for result in results %}
                    <div class="result">
                        <div class="source">
                            {% if result.metadata.source is string %}
                                [{{ result.metadata.source }}]
                            {% elif result.metadata.source is iterable and result.metadata.source is not string %}
                                [{{ result.metadata.source|join('') }}]
                            {% else %}
                                [Unknown]
                            {% endif %}
                            ({{ result.metadata.year or 'Unknown' }}). 
                            {{ result.metadata.title or 'Unknown Title' }}. 
                            {{ result.metadata.section or 'Unknown Section' }}
                        </div>
                        <div class="similarity">{{ result.match_type }} | Document ID: {{ result.metadata.document_id or 'Unknown' }}</div>
                        <p>{{ result.text }}</p>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    </div>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def index():
    query = ''
    results = []
    response = ''
    loading = False
    limit = 10
    
    if request.method == 'POST':
        query = request.form.get('query', '')
        limit = int(request.form.get('limit', 10))
        loading = True
        
        if query:
            print(f"Processing query: {query} with limit {limit}")
            try:
                results = comprehensive_search(query, limit=limit)
                response = generate_rag_response(query, results)
            except Exception as e:
                print(f"Error processing query: {e}")
                response = f"Error: {str(e)}"
            finally:
                loading = False
    
    # Count unique document sources
    unique_docs = set()
    for result in results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        if doc_id:
            unique_docs.add(doc_id)
    
    return render_template_string(
        HTML_TEMPLATE,
        query=query,
        results=results,
        response=response,
        loading=loading,
        limit=limit,
        unique_doc_count=len(unique_docs)
    )

if __name__ == '__main__':
    print("Starting Misophonia Research Guide server...")
    app.run(debug=True, host='0.0.0.0', port=6789)
