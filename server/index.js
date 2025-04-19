import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { OpenAI } from 'openai';
import fetch from 'node-fetch';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// Gemini 2.5 Pro API endpoint
app.post('/api/gemini', async (req, res) => {
  try {
    const { messages, topic } = req.body;
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) return res.status(500).json({ error: 'GEMINI_API_KEY not set in server/.env.' });
    if (!messages || !Array.isArray(messages)) {
      return res.status(400).json({ error: 'Messages array required.' });
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
    res.json({
      reply: geminiData.candidates?.[0]?.content?.parts?.[0]?.text || '',
      structured
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Error from Gemini API.' });
  }
});

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

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
