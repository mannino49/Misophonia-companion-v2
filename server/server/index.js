// Express backend for Misophonia Companion Chatbot
const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
require('dotenv').config();
const fetch = require('node-fetch');

const app = express();
const PORT = process.env.PORT || 3001;

// Enable CORS for Netlify frontend and local dev
app.use(cors({
  origin: [
    '[https://misophonia-guide.netlify.app](https://misophonia-guide.netlify.app)',
    'http://localhost:5173'
  ]
}));

app.use(bodyParser.json());

// Chat endpoint
app.post('/api/chat', async (req, res) => {
  try {
    const { messages } = req.body;
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return res.status(500).json({ error: 'OpenAI API key not set in .env' });
    }
    const openaiRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: 'gpt-3.5-turbo',
        messages: messages
      })
    });
    if (!openaiRes.ok) {
      const error = await openaiRes.text();
      return res.status(500).json({ error: error });
    }
    const data = await openaiRes.json();
    const reply = data.choices?.[0]?.message?.content || 'No response from AI.';
    res.json({ reply });
  } catch (err) {
    res.status(500).json({ error: 'Server error', details: err.message });
  }
});

app.get('/', (req, res) => {
  res.send('Misophonia Companion backend is running.');
});

app.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});
