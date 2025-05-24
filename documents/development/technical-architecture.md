<!-- File: documents/development/technical-architecture.md -->
################################################################################
# File: documents/development/technical-architecture.md
################################################################################
# 🛠️ Technical Architecture

## Current Status (May 2025)
- ✅ Vector Database Implementation: 134 documents, 43,000 chunks with embeddings
- ✅ RAG Query Interface: Semantic + keyword search with high-quality response generation
- ✅ Web Interface for Vector Database: User-friendly search across research documents
- ⏳ Habit Tracking System: In planning phase

## Core Architecture
- Frontend: React + Vite
- Backend: Node.js + Express
- Database: Firebase (Firestore with vector search capabilities)
- AI: OpenAI API (secure, server-side only)
- Deployment: Netlify (frontend), Firebase Functions (backend)

## Vector Database Architecture
- Document Processing: Python scripts for PDF extraction and chunking
- Embedding Generation: OpenAI embeddings API
- Storage: Firestore with vector search capabilities
- Search API: Firebase Functions for semantic and keyword search
- Frontend Integration: React components for search interface

## Planned Habit Tracking Architecture
- User Data: Firebase Authentication + Firestore for user profiles
- Trigger Logging: React components for quick logging interface
- Data Visualization: Chart.js or D3.js for pattern visualization
- Notification System: Firebase Cloud Messaging for reminders
- Coping Tools: Audio files stored in Firebase Storage
- Analytics: Firebase Analytics for usage tracking

## Security
- All API keys and secrets are stored server-side
- No secrets exposed to the frontend or version control ([see .gitignore](../../.gitignore))
- Firebase Authentication for user management
- Firestore security rules for data protection

## References
- [Product Vision](./product-vision.md)
- [Feature Roadmap](./feature-roadmap.md)
- [Vector Database Implementation Plan](./misophonia-vector-db-implementation-plan.md)
