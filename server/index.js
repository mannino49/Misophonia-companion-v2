// File: server/index.js
import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { OpenAI } from 'openai';
import fetch from 'node-fetch';
<<<<<<< Updated upstream
import httpProxy from 'http-proxy';
=======
import fs from 'fs';
import path from 'path';
>>>>>>> Stashed changes

dotenv.config();

// Set AI provider here - "openai" or "gemini"
const AI_PROVIDER = process.env.AI_PROVIDER || "openai";

const app = express();

//app.use(cors());  --> This is the default behavior
app.use(cors({
  origin: [
    '[https://misophonia-guide.netlify.app](https://misophonia-guide.netlify.app)',
    'http://localhost:5173'
  ]
}));
app.use(express.json());

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

<<<<<<< Updated upstream
// Research Assistant endpoint (handles both Gemini and OpenAI)
=======
function cosine(a, b) {
  const dot = a.reduce((sum, v, i) => sum + v * b[i], 0);
  const normA = Math.sqrt(a.reduce((s, v) => s + v * v, 0));
  const normB = Math.sqrt(b.reduce((s, v) => s + v * v, 0));
  return dot / (normA * normB);
}

// Gemini 2.5 Pro API endpoint
>>>>>>> Stashed changes
app.post('/api/gemini', async (req, res) => {
  try {
    const { messages, topic } = req.body;
    
    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: 'Messages array required.' });
    }
    
    // Using OpenAI
    if (AI_PROVIDER === "openai") {
      // Format messages for OpenAI
      const systemPrompt = topic 
        ? `You are a knowledgeable research assistant focusing on the topic: ${topic}. Provide information about misophonia research.`
        : "You are a knowledgeable research assistant on misophonia research.";
      
      const openaiMessages = [
        { role: 'system', content: systemPrompt },
        ...messages
      ];
      
      const completion = await openai.chat.completions.create({
        model: 'gpt-4o',
        messages: openaiMessages,
        max_tokens: 1024,
        temperature: 0.7
      });
      
      return res.json({
        reply: completion.choices[0]?.message?.content || '',
        structured: null,
        provider: 'openai'
      });
    }
    
    // Using Gemini
    else {
      const apiKey = process.env.GEMINI_API_KEY;
      if (!apiKey) {
        return res.status(500).json({ error: 'GEMINI_API_KEY not set in server/.env.' });
      }
      
      // Compose prompt for Gemini
      let userPrompt = '';
      if (topic && typeof topic === 'string') {
        userPrompt += `Topic: ${topic}\n`;
      }
      userPrompt += messages.map(m => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`).join('\n');
      
      // Gemini API call
      const geminiRes = await fetch('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-03-25:generateContent?key=' + apiKey, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [{ text: userPrompt }] }],
          generationConfig: {
            temperature: 0.7,
            maxOutputTokens: 1024,
          },
          tools: [
            { "function_declarations": [
              { "name": "structured_output", "description": "Return information in a structured JSON format for chat display, with sections, bullet points, and highlights." }
            ]}
          ]
        })
      });
      
      if (!geminiRes.ok) {
        const err = await geminiRes.text();
        return res.status(500).json({ error: 'Error from Gemini API', details: err });
      }
      
      const geminiData = await geminiRes.json();
      // Parse structured output if present
      let structured = null;
      if (geminiData.candidates && geminiData.candidates[0]?.content?.parts) {
        const part = geminiData.candidates[0].content.parts[0];
        if (part.functionCall && part.functionCall.name === 'structured_output') {
          try {
            structured = JSON.parse(part.functionCall.args.json || '{}');
          } catch {
            structured = part.functionCall.args;
          }
        }
      }
      
      return res.json({
        reply: geminiData.candidates?.[0]?.content?.parts?.[0]?.text || '',
        structured,
        provider: 'gemini'
      });
    }
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: `Error from ${AI_PROVIDER === "openai" ? "OpenAI" : "Gemini"} API.` });
  }
});

<<<<<<< Updated upstream
// Keep existing OpenAI chat endpoint
=======
app.post('/api/test-query', async (req, res) => {
  try {
    const { question } = req.body;
    if (!question || typeof question !== 'string') {
      return res.status(400).json({ error: 'Question required.' });
    }
    // Embed the query
    const embRes = await openai.embeddings.create({ model: 'text-embedding-ada-002', input: question });
    const qVec = embRes.data[0].embedding;
    // Load test embeddings and chunks
    const embs = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), '..', 'data', 'test_embeddings.json'), 'utf8'));
    const chunks = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), '..', 'data', 'test_chunks.json'), 'utf8'));
    // Compute similarities
    const sims = embs.map(e => {
      const chunk = chunks.find(c => c.file === e.file && c.index === e.index);
      return { sim: cosine(qVec, e.embedding), text: chunk ? chunk.text : '' };
    });
    sims.sort((a, b) => b.sim - a.sim);
    const topTexts = sims.slice(0, 5).map((s, i) => `${i+1}. ${s.text}`).join('\n\n');
    // Ask the model
    const prompt = `Use the following excerpts to answer the question.

${topTexts}

Question: ${question}`;
    const chatRes = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'system', content: 'You are an AI research assistant. Answer concisely based on provided context.' },
        { role: 'user', content: prompt }
      ]
    });
    const reply = chatRes.choices[0].message.content.trim();
    res.json({ answer: reply });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error in test-query', details: err.message });
  }
});

app.post('/api/research-query', async (req, res) => {
  try {
    const { question } = req.body;
    if (!question || typeof question !== 'string') {
      return res.status(400).json({ error: 'Question required.' });
    }
    // Embed the query
    const embRes = await openai.embeddings.create({ model: 'text-embedding-ada-002', input: question });
    const qVec = embRes.data[0].embedding;
    // Load research embeddings and chunks
    const embs = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), '..', 'data', 'research_embeddings.json'), 'utf8'));
    const chunks = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), '..', 'data', 'research_chunks.json'), 'utf8'));
    // Compute similarities
    const sims = embs.map(e => {
      const c = chunks.find(c => c.file === e.file && c.index === e.index);
      return { sim: cosine(qVec, e.embedding), text: c ? c.text : '' };
    });
    sims.sort((a, b) => b.sim - a.sim);
    const topTexts = sims.slice(0, 5).map((s, i) => `${i+1}. ${s.text}`).join('\n\n');
    // Ask the model
    const prompt = `Use the following excerpts to answer the question.\n\n${topTexts}\n\nQuestion: ${question}`;
    const chatRes = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'system', content: 'You are an AI research assistant. Answer concisely based on provided context.' },
        { role: 'user', content: prompt }
      ]
    });
    const reply = chatRes.choices[0].message.content.trim();
    res.json({ answer: reply });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Error in research-query', details: err.message });
  }
});

>>>>>>> Stashed changes
app.post('/api/chat', async (req, res) => {
  try {
    const { messages } = req.body;
    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: 'Messages array required.' });
    }
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages,
      max_tokens: 512,
      temperature: 0.7
    });
    const reply = completion.choices[0]?.message?.content || '';
    res.json({ reply });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error from OpenAI API.' });
  }
});

// ───────────────────────── RAG proxy ─────────────────────────
const proxy = httpProxy.createProxyServer({ changeOrigin: true });

app.post('/api/rag', (req, res) => {
  proxy.web(req, res, { target: 'http://localhost:8080/search' }, err => {
    console.error(err);
    res.status(502).json({ error: 'RAG service unreachable' });
  });
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Server running with ${AI_PROVIDER.toUpperCase()} on port ${PORT}`);
});
