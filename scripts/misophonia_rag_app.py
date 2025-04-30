#!/usr/bin/env python3

import os
import sys
import json
import logging
import time
import threading
import firebase_admin
from firebase_admin import credentials, firestore
import openai
import numpy as np
from dotenv import load_dotenv
import re
from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from concurrent.futures import ThreadPoolExecutor

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

# Global cache for embeddings to improve performance
embedding_cache = {}

# Global variable to track if Firebase has been initialized
firebase_initialized = False

def initialize_firebase():
    """Initialize Firebase with service account."""
    global firebase_initialized
    
    # Use a lock to prevent race conditions in threaded environment
    if not firebase_initialized:
        try:
            # Try to get the default app
            firebase_admin.get_app()
            firebase_initialized = True
        except ValueError:
            # Initialize with service account
            service_account_path = './service-account.json'
            logger.info(f"Initializing Firebase with service account: {service_account_path}")
            if not os.path.exists(service_account_path):
                logger.error(f"Service account file not found at {service_account_path}")
                sys.exit(1)
                
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            firebase_initialized = True
    
    return firestore.client()

def generate_embedding(text):
    """Generate embedding for the given text using OpenAI API."""
    # Check cache first
    if text in embedding_cache:
        return embedding_cache[text]
        
    try:
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        embedding = response.data[0].embedding
        
        # Cache the result
        embedding_cache[text] = embedding
        
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def fetch_chunks_batch(db, batch_size=1000, start_after=None):
    """Fetch chunks in batches to handle large collections."""
    query = db.collection('research_chunks').limit(batch_size)
    
    if start_after:
        query = query.start_after(start_after)
        
    docs = list(query.stream())
    logger.info(f"Fetched {len(docs)} chunks from Firestore")
    return docs

def semantic_search(query, limit=10, similarity_threshold=0.65):
    """Perform semantic search using embeddings with batched processing."""
    logger.info(f"Performing semantic search for: '{query}' with limit {limit}")
    db = initialize_firebase()
    
    # Generate embedding for the query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []
    
    # Process chunks in batches
    results = []
    last_doc = None
    total_processed = 0
    batch_size = 2000  # Increased batch size
    max_chunks = 20000  # Increased limit to process more chunks
    
    start_time = time.time()
    
    while total_processed < max_chunks:
        # Fetch batch of chunks
        chunks = fetch_chunks_batch(db, batch_size, last_doc)
        if not chunks:
            break
            
        # Update last_doc for pagination
        last_doc = chunks[-1]
        
        # Process chunks
        for chunk in chunks:
            total_processed += 1
            chunk_data = chunk.to_dict()
            
            if 'embedding' not in chunk_data:
                continue
                
            chunk_embedding = chunk_data['embedding']
            
            # Calculate cosine similarity
            similarity = np.dot(query_embedding, chunk_embedding) / \
                        (np.linalg.norm(query_embedding) * np.linalg.norm(chunk_embedding))
            
            if similarity > similarity_threshold:
                results.append({
                    'chunk_id': chunk.id,
                    'text': chunk_data.get('text', ''),
                    'metadata': chunk_data.get('metadata', {}),
                    'similarity': float(similarity),
                    'match_type': f"Semantic ({similarity:.4f})"
                })
    
    end_time = time.time()
    logger.info(f"Processed {total_processed} chunks in {end_time - start_time:.2f} seconds")
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def fetch_raw_chunks_batch(db, batch_size=1000, start_after=None):
    """Fetch raw chunks in batches to handle large collections."""
    query = db.collection('research_chunks_raw').limit(batch_size)
    
    if start_after:
        query = query.start_after(start_after)
        
    docs = list(query.stream())
    return docs

def keyword_search(query, limit=10, relevance_threshold=0.15):
    """Perform keyword-based search on raw chunks with batched processing."""
    logger.info(f"Performing keyword search for: '{query}' with limit {limit}")
    db = initialize_firebase()
    
    # Extract search terms from query
    search_terms = query.lower().split()
    
    # Define additional related terms for misophonia topics
    topic_expansions = {
        'treatment': ['therapy', 'intervention', 'approach', 'management', 'technique', 'strategy', 'protocol', 'treatment'],
        'symptom': ['sign', 'manifestation', 'indication', 'characteristic', 'feature', 'symptom'],
        'trigger': ['stimulus', 'sound', 'noise', 'cue', 'provocation', 'elicit', 'trigger'],
        'coping': ['manage', 'deal', 'handle', 'strategy', 'technique', 'skill', 'coping'],
        'anxiety': ['anxious', 'stress', 'distress', 'fear', 'worry', 'panic', 'anxiety'],
        'anger': ['rage', 'irritation', 'frustration', 'annoyance', 'irritability', 'anger'],
        'brain': ['neural', 'neurological', 'cognitive', 'neuroanatomical', 'neurobiological', 'brain'],
        'children': ['child', 'adolescent', 'teen', 'youth', 'pediatric', 'young', 'children'],
        'comorbid': ['comorbidity', 'coexisting', 'concurrent', 'accompanying', 'associated', 'comorbid']
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
    
    logger.info(f"Expanded search terms: {expanded_terms}")
    
    # Process chunks in batches
    results = []
    last_doc = None
    total_processed = 0
    batch_size = 2000  # Increased batch size
    max_chunks = 20000  # Increased limit to process more chunks
    
    start_time = time.time()
    
    while total_processed < max_chunks:
        # Fetch batch of raw chunks
        chunks = fetch_raw_chunks_batch(db, batch_size, last_doc)
        if not chunks:
            break
            
        # Update last_doc for pagination
        last_doc = chunks[-1]
        
        # Process chunks
        for chunk in chunks:
            total_processed += 1
            chunk_data = chunk.to_dict()
            
            if 'text' not in chunk_data:
                continue
                
            text = chunk_data['text'].lower()
            metadata = chunk_data.get('metadata', {})
            
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
                if relevance > relevance_threshold:
                    results.append({
                        'chunk_id': metadata.get('chunk_id', 'unknown'),
                        'text': chunk_data['text'],
                        'metadata': metadata,
                        'similarity': float(relevance),
                        'match_type': f"Keyword ({relevance:.4f})"
                    })
    
    end_time = time.time()
    logger.info(f"Processed {total_processed} raw chunks in {end_time - start_time:.2f} seconds")
    
    # Sort by relevance score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def comprehensive_search(query, limit=10, semantic_threshold=0.65, keyword_threshold=0.15):
    """Perform both semantic and keyword search and combine results."""
    logger.info(f"Starting comprehensive search for: '{query}' with limit {limit}")
    
    # Initialize Firebase before starting threads
    db = initialize_firebase()
    
    # Use ThreadPoolExecutor to run searches in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Request more results than needed to ensure diversity
        search_limit = limit * 3
        semantic_future = executor.submit(semantic_search, query, search_limit, semantic_threshold)
        keyword_future = executor.submit(keyword_search, query, search_limit, keyword_threshold)
        
        semantic_results = semantic_future.result()
        keyword_results = keyword_future.result()
    
    # Track documents to ensure diversity
    combined_results = []
    seen_chunk_ids = set()
    seen_doc_ids = set()
    doc_count = {}  # Count occurrences of each document
    
    # Function to extract document ID from result
    def get_doc_id(result):
        metadata = result.get('metadata', {})
        return metadata.get('document_id', '')
    
    # Process semantic results first (they're usually more relevant)
    for result in semantic_results:
        chunk_id = result.get('chunk_id')
        doc_id = get_doc_id(result)
        
        # Skip if we've seen this chunk
        if chunk_id in seen_chunk_ids:
            continue
            
        # Add the result
        combined_results.append(result)
        seen_chunk_ids.add(chunk_id)
        
        # Track document counts
        if doc_id:
            seen_doc_ids.add(doc_id)
            doc_count[doc_id] = doc_count.get(doc_id, 0) + 1
    
    # Add keyword results that aren't duplicates
    for result in keyword_results:
        chunk_id = result.get('chunk_id')
        doc_id = get_doc_id(result)
        
        # Skip if we've seen this chunk
        if chunk_id in seen_chunk_ids:
            continue
            
        # Prioritize results from documents we haven't seen yet
        if doc_id and doc_id not in seen_doc_ids:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
            seen_doc_ids.add(doc_id)
            doc_count[doc_id] = doc_count.get(doc_id, 0) + 1
        # Or if we've seen fewer than 3 chunks from this document
        elif doc_id and doc_count.get(doc_id, 0) < 3:
            combined_results.append(result)
            seen_chunk_ids.add(chunk_id)
            doc_count[doc_id] = doc_count.get(doc_id, 0) + 1
    
    # Sort by similarity score, but with a boost for document diversity
    def diversity_score(result):
        doc_id = get_doc_id(result)
        # Boost score for documents with fewer occurrences
        doc_boost = 1.0 / (doc_count.get(doc_id, 1) + 1) if doc_id else 0
        return result['similarity'] + (doc_boost * 0.1)  # Small boost for diversity
    
    # Sort using the diversity score
    combined_results.sort(key=diversity_score, reverse=True)
    
    # Limit to requested number while ensuring document diversity
    final_results = []
    final_doc_ids = set()
    
    # First pass: add one result from each unique document
    for result in combined_results:
        doc_id = get_doc_id(result)
        if doc_id and doc_id not in final_doc_ids and len(final_results) < limit:
            final_results.append(result)
            final_doc_ids.add(doc_id)
    
    # Second pass: fill remaining slots with best results
    remaining_slots = limit - len(final_results)
    if remaining_slots > 0:
        for result in combined_results:
            if result not in final_results and len(final_results) < limit:
                final_results.append(result)
                
    # Sort final results by similarity for display
    final_results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Count unique documents
    doc_ids = set()
    for result in final_results:
        metadata = result.get('metadata', {})
        doc_id = metadata.get('document_id')
        if doc_id:
            doc_ids.add(doc_id)
    
    logger.info(f"Found {len(final_results)} results from {len(doc_ids)} unique documents")
    
    return final_results

def generate_rag_response(query, search_results, max_tokens=1200):
    """Generate a RAG response using the search results and OpenAI."""
    try:
        logger.info("Generating RAG response")
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

Format your response with clear paragraphs and use markdown formatting for headings and emphasis where appropriate.
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Misophonia Research Guide</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #5D3FD3;
            --secondary-color: #E6E6FA;
            --accent-color: #9370DB;
            --text-color: #333;
            --light-bg: #F8F9FA;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--light-bg);
            padding-bottom: 50px;
        }
        
        .header {
            background-color: var(--primary-color);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.1rem;
            max-width: 700px;
            margin: 0 auto;
        }
        
        .search-container {
            background-color: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        
        .search-box {
            position: relative;
        }
        
        .search-input {
            padding-right: 50px;
            border: 2px solid var(--secondary-color);
            transition: border-color 0.3s;
        }
        
        .search-input:focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 0.25rem rgba(93, 63, 211, 0.25);
        }
        
        .btn-search {
            background-color: var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .btn-search:hover {
            background-color: #4930A8;
            border-color: #4930A8;
        }
        
        .response-container {
            background-color: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        
        .response-container h2 {
            color: var(--primary-color);
            font-weight: 600;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--secondary-color);
        }
        
        .response-content {
            font-size: 1.1rem;
            line-height: 1.7;
        }
        
        .sources-container {
            background-color: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .sources-container h2 {
            color: var(--primary-color);
            font-weight: 600;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--secondary-color);
        }
        
        .source-card {
            border-left: 4px solid var(--accent-color);
            background-color: var(--light-bg);
            margin-bottom: 1.5rem;
            transition: transform 0.2s;
        }
        
        .source-card:hover {
            transform: translateY(-3px);
        }
        
        .source-header {
            font-weight: 600;
            color: var(--primary-color);
        }
        
        .source-meta {
            font-size: 0.9rem;
            color: #666;
        }
        
        .source-text {
            font-size: 1rem;
            margin-top: 0.5rem;
        }
        
        .match-badge {
            background-color: var(--accent-color);
            color: white;
            font-size: 0.8rem;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }
        
        .loading-container {
            display: {{ 'flex' if loading else 'none' }};
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        
        .spinner-border {
            color: var(--primary-color);
            width: 3rem;
            height: 3rem;
            margin-bottom: 1rem;
        }
        
        .loading-text {
            color: var(--primary-color);
            font-weight: 500;
        }
        
        .footer {
            text-align: center;
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid #ddd;
            color: #666;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .header {
                padding: 1.5rem 0;
            }
            
            .search-container,
            .response-container,
            .sources-container {
                padding: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="header text-center">
        <div class="container">
            <h1>Misophonia Research Guide</h1>
            <p>Evidence-based information from 128 research documents on misophonia</p>
        </div>
    </div>
    
    <div class="container">
        <div class="search-container">
            <form method="POST" action="/">
                <div class="mb-4">
                    <label for="query" class="form-label fw-bold">Ask a question about misophonia:</label>
                    <div class="search-box">
                        <input type="text" class="form-control form-control-lg search-input" id="query" name="query" placeholder="E.g., What are effective treatments for misophonia?" value="{{ query }}" required>
                    </div>
                </div>
                
                <div class="row align-items-center">
                    <div class="col-md-6 mb-3 mb-md-0">
                        <div class="d-flex align-items-center">
                            <label for="limit" class="form-label me-2 mb-0">Number of sources:</label>
                            <select class="form-select" id="limit" name="limit">
                                <option value="5" {% if limit == 5 %}selected{% endif %}>5</option>
                                <option value="10" {% if limit == 10 or not limit %}selected{% endif %}>10</option>
                                <option value="15" {% if limit == 15 %}selected{% endif %}>15</option>
                                <option value="20" {% if limit == 20 %}selected{% endif %}>20</option>
                            </select>
                        </div>
                    </div>
                    <div class="col-md-6 text-md-end">
                        <button type="submit" class="btn btn-primary btn-lg btn-search">Search Research</button>
                    </div>
                </div>
            </form>
        </div>
        
        <div class="loading-container" id="loading-container">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="loading-text">Searching across research documents and generating response...</p>
        </div>
        
        {% if response %}
            <div class="response-container">
                <h2>Research-Based Answer</h2>
                <div class="response-content">
                    {{ response|replace('\n', '<br>')|safe }}
                </div>
            </div>
        {% endif %}
        
        {% if results %}
            <div class="sources-container">
                <h2>Source Documents ({{ unique_doc_count }} unique documents)</h2>
                
                {% for result in results %}
                    <div class="card source-card mb-4">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <h5 class="source-header mb-0">
                                    {% if result.metadata.source is string %}
                                        {{ result.metadata.source }}
                                    {% elif result.metadata.source is iterable and result.metadata.source is not string %}
                                        {{ result.metadata.source|join('') }}
                                    {% else %}
                                        Unknown
                                    {% endif %}
                                    ({{ result.metadata.year or 'Unknown' }})
                                </h5>
                                <span class="match-badge">{{ result.match_type }}</span>
                            </div>
                            
                            <div class="source-meta">
                                <strong>Title:</strong> {{ result.metadata.title or 'Unknown Title' }}<br>
                                <strong>Section:</strong> {{ result.metadata.section or 'Unknown Section' }}<br>
                                <strong>Document ID:</strong> {{ result.metadata.document_id or 'Unknown' }}
                            </div>
                            
                            <div class="source-text mt-3">
                                {{ result.text }}
                            </div>
                        </div>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
        
        <div class="footer">
            <p>Misophonia Research Guide &copy; 2025 | Powered by OpenAI and Firebase</p>
        </div>
    </div>
    
    <script>
        // Show loading indicator when form is submitted
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.querySelector('form');
            const loadingContainer = document.getElementById('loading-container');
            
            if (form) {
                form.addEventListener('submit', function() {
                    loadingContainer.style.display = 'flex';
                });
            }
        });
    </script>
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
            logger.info(f"Processing query: {query} with limit {limit}")
            try:
                results = comprehensive_search(query, limit=limit)
                # Log document diversity
                doc_ids = set()
                for result in results:
                    metadata = result.get('metadata', {})
                    doc_id = metadata.get('document_id', '')
                    if doc_id:
                        doc_ids.add(doc_id)
                logger.info(f"Retrieved {len(results)} results from {len(doc_ids)} unique documents")
                
                response = generate_rag_response(query, results)
            except Exception as e:
                logger.error(f"Error processing query: {e}")
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

@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint for programmatic search."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
            
        query = data.get('query', '')
        limit = int(data.get('limit', 10))
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
            
        # Perform search
        results = comprehensive_search(query, limit=limit)
        
        # Generate RAG response
        response = generate_rag_response(query, results)
        
        # Count unique documents
        unique_docs = set()
        for result in results:
            metadata = result.get('metadata', {})
            doc_id = metadata.get('document_id', '')
            if doc_id:
                unique_docs.add(doc_id)
        
        return jsonify({
            'query': query,
            'results': results,
            'response': response,
            'unique_document_count': len(unique_docs)
        })
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/stats')
def stats():
    """Endpoint to get database statistics."""
    try:
        db = initialize_firebase()
        
        # Get counts
        research_chunks_count = db.collection('research_chunks').count().get()[0][0].value
        raw_chunks_count = db.collection('research_chunks_raw').count().get()[0][0].value
        
        # Get sample document IDs
        chunks = db.collection('research_chunks').limit(100).stream()
        doc_ids = set()
        for chunk in chunks:
            chunk_data = chunk.to_dict()
            if 'metadata' in chunk_data and 'document_id' in chunk_data['metadata']:
                doc_ids.add(chunk_data['metadata']['document_id'])
        
        return jsonify({
            'processed_chunks': research_chunks_count,
            'raw_chunks': raw_chunks_count,
            'unique_documents': len(doc_ids),
            'sample_documents': list(doc_ids)[:10]
        })
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': f'Failed to get stats: {str(e)}'}), 500

if __name__ == '__main__':
    logger.info("Starting Misophonia Research Guide server...")
    app.run(debug=True, host='0.0.0.0', port=3333)
