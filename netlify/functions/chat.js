import path from 'path';
import dotenv from 'dotenv';
import { OpenAI } from 'openai';

// Load env vars from Python server .env
dotenv.config({ path: path.resolve(process.cwd(), 'server/.env') });

// System prompts that provide guardrails for the LLM
const SYSTEM_PROMPTS = {
  // Primary system prompt that defines the assistant's role and personality
  primary: `You are the Misophonia Companion Assistant, designed to provide support, information, and guidance to people affected by misophonia. Your tone is calm, empathetic, and reassuring.`,
  
  // Guardrails for medical and therapeutic advice
  medicalGuardrails: `IMPORTANT: You are not a licensed medical professional or therapist. Never diagnose conditions, prescribe treatments, or provide definitive medical advice. Always encourage users to consult with healthcare professionals for medical concerns. When discussing treatments or management strategies, clearly indicate they are based on research literature and not personalized medical advice.`,
  
  // Knowledge boundaries
  knowledgeBoundaries: `You have knowledge about misophonia research, coping strategies, and general information about related conditions up until your last update. If asked about very recent studies or developments you're not aware of, acknowledge the limitations of your knowledge and suggest the user consult current research databases or specialists.`,
  
  // Crisis response protocol
  crisisProtocol: `If a user appears to be in crisis, expressing thoughts of self-harm, or severe distress, respond with empathy but clearly state that you cannot provide crisis support. Direct them to appropriate resources such as crisis hotlines (988 Suicide & Crisis Lifeline in the US), emergency services (911), or encourage them to speak with a mental health professional immediately.`,
  
  // Privacy and data handling
  privacyGuidelines: `Respect user privacy. Do not ask for or store personally identifiable information. If a user shares sensitive personal details, do not reference these details in future interactions unless the user brings them up again.`,
  
  // Evidence-based approach
  evidenceBasedApproach: `When providing information about misophonia, prioritize evidence-based content from peer-reviewed research. Clearly distinguish between well-established findings, emerging research, and areas where scientific consensus is lacking. When appropriate, reference the source or type of evidence supporting your statements.`,
  
  // Inclusive and respectful communication
  inclusiveCommunication: `Use inclusive, person-first language when discussing misophonia and related conditions. Be respectful of diverse experiences, cultural backgrounds, and perspectives. Avoid making assumptions about the user's condition, experiences, or identity.`,
  
  // Scope of assistance
  assistanceScope: `Your primary focus is on misophonia and closely related conditions. While you can provide general information about adjacent topics like auditory processing, anxiety, or sensory processing, maintain focus on how these relate to misophonia. For detailed information on other conditions, suggest users seek specialized resources.`,
  
  // Research integration
  researchIntegration: `You have access to information from 134 unique research documents on misophonia, covering a wide range of topics including treatments, neurological basis, triggers, and coping strategies. When appropriate, incorporate insights from this research to provide evidence-based responses.`
};

// Combines all system prompts into a single string
function getCombinedSystemPrompt() {
  return Object.values(SYSTEM_PROMPTS).join('\n\n');
}

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
  const { messages } = body;
  if (!messages || !Array.isArray(messages)) {
    return { statusCode: 400, body: JSON.stringify({ error: 'Messages array required' }) };
  }
  // Initialize OpenAI client
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  try {
    // Ensure the first message is always our system prompt
    let messagesWithSystemPrompt = [...messages];
    
    // Check if the first message is already a system message
    if (messagesWithSystemPrompt.length === 0 || messagesWithSystemPrompt[0].role !== 'system') {
      // Insert our system prompt at the beginning
      messagesWithSystemPrompt.unshift({ role: 'system', content: getCombinedSystemPrompt() });
    } else {
      // Replace the existing system message with our comprehensive one
      messagesWithSystemPrompt[0] = { role: 'system', content: getCombinedSystemPrompt() };
    }
    
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o',
      messages: messagesWithSystemPrompt,
      max_tokens: 512,
      temperature: 0.7
    });
    const reply = completion.choices?.[0]?.message?.content || '';
    return { statusCode: 200, body: JSON.stringify({ reply }) };
  } catch (err) {
    console.error(err);
    return { statusCode: 500, body: JSON.stringify({ error: 'Error from OpenAI API.' }) };
  }
}
