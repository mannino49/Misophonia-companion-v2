import path from 'path';
import fetch from 'node-fetch';
import dotenv from 'dotenv';

dotenv.config({ path: path.resolve(process.cwd(), 'server/.env') });

export async function handler(event, context) {
  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, body: 'Method Not Allowed' };
  }
  let body;
  try {
    body = JSON.parse(event.body);
  } catch {
    return { statusCode: 400, body: JSON.stringify({ error: 'Invalid JSON' }) };
  }
  const { messages, topic } = body;
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return { statusCode: 500, body: JSON.stringify({ error: 'GEMINI_API_KEY not set' }) };
  }
  if (!messages || !Array.isArray(messages)) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Messages array required' }) };
  }
  let userPrompt = '';
  if (topic && typeof topic === 'string') {
    userPrompt += `Topic: ${topic}\n`;
  }
  userPrompt += messages.map(m => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`).join('\n');
  const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-03-25:generateContent?key=${apiKey}`;
  const res = await fetch(apiUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ role: 'user', parts: [{ text: userPrompt }] }],
      generationConfig: { temperature: 0.7, maxOutputTokens: 1024 },
      tools: [
        { function_declarations: [
            { name: 'structured_output', description: 'Return information in a structured JSON format for chat display, with sections, bullet points, and highlights.' }
          ]
        }
      ]
    })
  });
  if (!res.ok) {
    const err = await res.text();
    return { statusCode: 500, body: JSON.stringify({ error: 'Error from Gemini API', details: err }) };
  }
  const data = await res.json();
  let structured = null;
  if (data.candidates && data.candidates[0]?.content?.parts) {
    const part = data.candidates[0].content.parts[0];
    if (part.functionCall && part.functionCall.name === 'structured_output') {
      try {
        structured = JSON.parse(part.functionCall.args.json || '{}');
      } catch {
        structured = part.functionCall.args;
      }
    }
  }
  const reply = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
  return { statusCode: 200, body: JSON.stringify({ reply, structured }) };
}
