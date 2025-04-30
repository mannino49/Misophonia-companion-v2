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
from flask import Flask, render_template, request, jsonify

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
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def semantic_search(query, limit=5):
    """Perform semantic search using embeddings."""
    db = initialize_firebase()
    
    # Generate embedding for the query
    query_embedding = generate_embedding(query)
    if not query_embedding:
        return []
    
    # Fetch chunks with embeddings
    chunks_ref = db.collection('research_chunks')
    chunks = chunks_ref.limit(1000).stream()  # Limit to 1000 for performance
    
    # Calculate similarity scores
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
        
        if similarity > 0.75:  # Threshold for relevance
            results.append({
                'chunk_id': chunk.id,
                'text': chunk_data.get('text', ''),
                'metadata': chunk_data.get('metadata', {}),
                'similarity': float(similarity),  # Convert to float for JSON serialization
                'match_type': f"Semantic ({similarity:.4f})"
            })
    
    # Sort by similarity score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def keyword_search(query, limit=5):
    """Perform keyword-based search on raw chunks."""
    db = initialize_firebase()
    
    # Fetch raw chunks
    raw_chunks_ref = db.collection('research_chunks_raw')
    raw_chunks = raw_chunks_ref.limit(1000).stream()  # Limit to 1000 for performance
    raw_chunks_list = [chunk.to_dict() for chunk in raw_chunks]
    
    # Extract search terms from query
    search_terms = query.lower().split()
    
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
    
    # Search for matching chunks
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
    
    # Sort by relevance score (descending)
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Return top results
    return results[:limit]

def comprehensive_search(query, limit=5):
    """Perform both semantic and keyword search and combine results."""
    semantic_results = semantic_search(query, limit)
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
    
    return final_results

def generate_rag_response(query, search_results, max_tokens=500):
    """Generate a RAG response using the search results and OpenAI."""
    try:
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
            
        query = data.get('query', '')
        limit = int(data.get('limit', 5))
        
        if not query:
            return jsonify({'error': 'No query provided'}), 400
    
        # Perform search
        results = comprehensive_search(query, limit)
        
        # Generate RAG response
        response = generate_rag_response(query, results)
        
        return jsonify({
            'results': results,
            'response': response
        })
    except Exception as e:
        print(f"Error in search endpoint: {e}")
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/stats')
def stats():
    db = initialize_firebase()
    
    # Get counts
    research_chunks = db.collection('research_chunks').count().get()[0][0].value
    raw_chunks = db.collection('research_chunks_raw').count().get()[0][0].value
    
    # Get sample document IDs
    chunks = db.collection('research_chunks').limit(100).stream()
    doc_ids = set()
    for chunk in chunks:
        chunk_data = chunk.to_dict()
        if 'metadata' in chunk_data and 'document_id' in chunk_data['metadata']:
            doc_ids.add(chunk_data['metadata']['document_id'])
    
    return jsonify({
        'processed_chunks': research_chunks,
        'raw_chunks': raw_chunks,
        'unique_documents': len(doc_ids),
        'sample_documents': list(doc_ids)[:10]
    })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(script_dir, 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create index.html template
    with open(os.path.join(templates_dir, 'index.html'), 'w') as f:
        f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Misophonia Research RAG Interface</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .search-box {
            margin-bottom: 20px;
        }
        .results-container {
            margin-top: 20px;
        }
        .result-card {
            margin-bottom: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .result-card .card-header {
            font-weight: bold;
            display: flex;
            justify-content: space-between;
        }
        .similarity-badge {
            font-size: 0.8rem;
        }
        .loading {
            text-align: center;
            padding: 20px;
            display: none;
        }
        .response-container {
            margin-top: 30px;
            padding: 20px;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .stats-container {
            margin-top: 30px;
            padding: 15px;
            background-color: #e9ecef;
            border-radius: 8px;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Misophonia Research RAG Interface</h1>
            <p class="text-muted">Search across 128 research documents with semantic and keyword-based retrieval</p>
        </div>
        
        <div class="search-box">
            <div class="input-group mb-3">
                <input type="text" id="search-input" class="form-control form-control-lg" placeholder="Ask a question about misophonia..." aria-label="Search query">
                <button class="btn btn-primary" type="button" id="search-button">Search</button>
            </div>
            <div class="form-text">Try questions about treatments, neurological basis, symptoms, or coping strategies</div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p>Searching research documents and generating response...</p>
        </div>
        
        <div id="response-area" style="display: none;">
            <div class="response-container">
                <h3>Research-Based Answer</h3>
                <div id="response-content"></div>
            </div>
            
            <div class="results-container">
                <h3>Source Documents</h3>
                <div id="results-list"></div>
            </div>
        </div>
        
        <div class="stats-container" id="stats-container">
            <h5>Database Statistics</h5>
            <div id="stats-content">
                <p>Loading statistics...</p>
            </div>
        </div>
    </div>
    
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const searchInput = document.getElementById('search-input');
            const searchButton = document.getElementById('search-button');
            const loadingIndicator = document.getElementById('loading');
            const responseArea = document.getElementById('response-area');
            const responseContent = document.getElementById('response-content');
            const resultsList = document.getElementById('results-list');
            const statsContent = document.getElementById('stats-content');
            
            // Load stats on page load
            fetch('/stats')
                .then(response => response.json())
                .then(data => {
                    statsContent.innerHTML = `
                        <p><strong>Processed Chunks:</strong> ${data.processed_chunks} (with embeddings)</p>
                        <p><strong>Raw Chunks:</strong> ${data.raw_chunks} (total in collection)</p>
                        <p><strong>Unique Documents:</strong> ${data.unique_documents} (with embeddings)</p>
                        <p><strong>Sample Documents:</strong> ${data.sample_documents.join(', ')}</p>
                    `;
                })
                .catch(error => {
                    console.error('Error fetching stats:', error);
                    statsContent.innerHTML = '<p>Error loading statistics</p>';
                });
            
            // Search function
            function performSearch() {
                const query = searchInput.value.trim();
                if (!query) return;
                
                // Show loading, hide results
                loadingIndicator.style.display = 'block';
                responseArea.style.display = 'none';
                
                // Perform search
                console.log('Sending search request for query:', query);
                fetch('/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        query: query,
                        limit: 5
                    })
                })
                .then(response => response.json())
                .then(data => {
                    // Hide loading
                    loadingIndicator.style.display = 'none';
                    
                    // Show response
                    responseContent.innerHTML = `<p>${data.response.replace(/\n/g, '<br>')}</p>`;
                    
                    // Show results
                    resultsList.innerHTML = '';
                    data.results.forEach((result, index) => {
                        const metadata = result.metadata || {};
                        const source = metadata.source || 'Unknown';
                        const sourceStr = Array.isArray(source) ? source.join('') : source;
                        const year = metadata.year || 'Unknown';
                        const title = metadata.title || 'Unknown Title';
                        const section = metadata.section || 'Unknown Section';
                        
                        const resultCard = document.createElement('div');
                        resultCard.className = 'card result-card';
                        resultCard.innerHTML = `
                            <div class="card-header bg-light">
                                <span>${sourceStr} (${year})</span>
                                <span class="similarity-badge badge bg-primary">${result.match_type}</span>
                            </div>
                            <div class="card-body">
                                <h5 class="card-title">${title}</h5>
                                <h6 class="card-subtitle mb-2 text-muted">${section}</h6>
                                <p class="card-text">${result.text}</p>
                            </div>
                        `;
                        resultsList.appendChild(resultCard);
                    });
                    
                    responseArea.style.display = 'block';
                })
                .catch(error => {
                    console.error('Error performing search:', error);
                    loadingIndicator.style.display = 'none';
                    alert('Error performing search: ' + error);
                    responseContent.innerHTML = '<p class="text-danger">Error: Failed to perform search. Please check the console for details.</p>';
                    responseArea.style.display = 'block';
                });
            }
            
            // Event listeners
            searchButton.addEventListener('click', performSearch);
            searchInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
        });
    </script>
</body>
</html>
''')
    
    print(f"Templates directory created at: {templates_dir}")
    print("Starting Flask server...")
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=8080)
