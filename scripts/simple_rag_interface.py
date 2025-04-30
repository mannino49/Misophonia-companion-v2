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

def initialize_firebase():
    """Initialize Firebase with service account."""
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

def generate_embedding(text):
    """Generate embedding for the given text using OpenAI API."""
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        embedding = response.data[0].embedding
        print(f"Successfully generated embedding with dimension {len(embedding)}")
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def semantic_search(query, limit=5):
    """Perform semantic search using embeddings."""
    print(f"Performing semantic search for: '{query}'")
    db = initialize_firebase()
    
    # Generate embedding for the query
    print(f"Generating embedding for query: '{query}'")
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []
    
    # Fetch chunks with embeddings
    print("Fetching chunks with embeddings...")
    chunks_ref = db.collection('research_chunks')
    chunks = chunks_ref.limit(5000).stream()  # Increased limit to 5000 for better coverage
    
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
        
        if similarity > 0.70:  # Lowered threshold for better diversity
            results.append({
                'chunk_id': chunk.id,
                'text': chunk_data.get('text', ''),
                'metadata': chunk_data.get('metadata', {}),
                'similarity': float(similarity),  # Convert to float for JSON serialization
                'match_type': f"Semantic ({similarity:.4f})"
            })
    
    print(f"Processed {processed} chunks, skipped {skipped} chunks")
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def keyword_search(query, limit=5):
    """Perform keyword-based search on raw chunks."""
    print(f"Performing keyword search for: '{query}'")
    db = initialize_firebase()
    
    # Fetch raw chunks
    print("Fetching raw chunks...")
    raw_chunks_ref = db.collection('research_chunks_raw')
    raw_chunks = raw_chunks_ref.limit(5000).stream()  # Increased limit to 5000 for better coverage
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
            if relevance > 0.2:  # Lower threshold for keyword search
                results.append({
                    'chunk_id': metadata.get('chunk_id', 'unknown'),
                    'text': chunk['text'],
                    'metadata': metadata,
                    'similarity': float(relevance),  # Convert to float for JSON serialization
                    'match_type': f"Keyword ({relevance:.4f})"
                })
    
    print(f"Found {len(results)} matching chunks")
    
    # Sort by relevance score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def comprehensive_search(query, limit=8):
    """Perform both semantic and keyword search and combine results."""
    print(f"\n==================================================\nSearching for: '{query}'\n==================================================\n")
    
    print("\n--- Semantic Search ---\n")
    semantic_results = semantic_search(query, limit)
    
    print("\n--- Keyword Search ---\n")
    keyword_results = keyword_search(query, limit)
    
    # Combine results, prioritizing semantic matches
    combined_results = []
    seen_chunk_ids = set()
    
    # Add semantic results first
    for result in semantic_results:
        chunk_id = result.get('chunk_id')
        if chunk_id not in seen_chunk_ids:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
    
    # Add keyword results that aren't duplicates
    for result in keyword_results:
        chunk_id = result.get('chunk_id')
        if chunk_id not in seen_chunk_ids:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
    
    # Sort by similarity score
    combined_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Limit to requested number
    final_results = combined_results[:limit]
    
    print("\n--- Combined Results ---\n")
    print(f"\nFound {len(final_results)} results\n")
    
    return final_results

def generate_rag_response(query, search_results, max_tokens=1000):
    """Generate a RAG response using the search results and OpenAI."""
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

# HTML template for the simple interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Misophonia Research RAG Interface</title>
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
            width: 70%;
            padding: 10px;
            font-size: 16px;
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
        <h1>Misophonia Research RAG Interface</h1>
        <p style="text-align: center;">Search across 128 research documents with semantic and keyword-based retrieval</p>
        
        <form method="POST" action="/">
            <div style="margin-bottom: 10px;">
                <input type="text" name="query" placeholder="Ask a question about misophonia..." value="{{ query }}" required style="width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px;">
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <label for="limit">Number of sources: </label>
                    <select name="limit" id="limit" style="padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                        <option value="5" {% if limit == 5 %}selected{% endif %}>5</option>
                        <option value="8" {% if limit == 8 or not limit %}selected{% endif %}>8</option>
                        <option value="12" {% if limit == 12 %}selected{% endif %}>12</option>
                        <option value="15" {% if limit == 15 %}selected{% endif %}>15</option>
                    </select>
                </div>
                <input type="submit" value="Search" style="padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px;">
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
                            <span style="font-size: 0.8em; color: #666;">Document ID: {{ result.metadata.document_id or 'Unknown' }}</span>
                        </div>
                        <div class="similarity">{{ result.match_type }}</div>
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
    
    if request.method == 'POST':
        query = request.form.get('query', '')
        limit = int(request.form.get('limit', 8))  # Allow user to specify result limit
        loading = True
        
        if query:
            print(f"Processing query: {query} with limit {limit}")
            results = comprehensive_search(query, limit=limit)
            response = generate_rag_response(query, results)
            loading = False
    
    # Count unique document sources
    unique_docs = set()
    for result in results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id', '')
        if doc_id:
            unique_docs.add(doc_id)
    
    # Get the limit value to pre-select in the dropdown
    limit = len(results) if results else 8
    
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
    print("Starting Flask server...")
    app.run(debug=True, host='0.0.0.0', port=7070)
