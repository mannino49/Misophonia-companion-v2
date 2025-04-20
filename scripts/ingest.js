import fs from 'fs';
import path from 'path';
import pdfjsLib from 'pdfjs-dist/legacy/build/pdf.js';
const { getDocument } = pdfjsLib;
import admin from 'firebase-admin';
import dotenv from 'dotenv';

// Load environment variables (make sure FIREBASE_* vars are set in server/.env)
dotenv.config({ path: path.resolve(process.cwd(), 'server/.env') });

// Initialize Firebase Admin SDK
const serviceAccount = {
  projectId: process.env.FIREBASE_PROJECT_ID,
  clientEmail: process.env.FIREBASE_CLIENT_EMAIL,
  privateKey: process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
};
admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});
const db = admin.firestore();

// Function to chunk text
function chunkText(text, size = 1000, overlap = 200) {
  const chunks = [];
  for (let start = 0; start < text.length; start += size - overlap) {
    const chunk = text.slice(start, start + size);
    chunks.push(chunk.trim());
  }
  return chunks;
}

async function processPdf(filePath) {
  const buffer = fs.readFileSync(filePath);
  const loadingTask = getDocument({ data: buffer });
  const pdfDoc = await loadingTask.promise;
  const numPages = pdfDoc.numPages;
  let text = '';
  for (let i = 1; i <= numPages; i++) {
    const page = await pdfDoc.getPage(i);
    const content = await page.getTextContent();
    const strings = content.items.map(item => item.str);
    text += strings.join(' ') + '\n';
  }
  const chunks = chunkText(text);
  const basename = path.basename(filePath, '.pdf');
  const batch = db.batch();

  chunks.forEach((chunk, idx) => {
    const docRef = db.collection('research_chunks').doc(`${basename}_${idx}`);
    batch.set(docRef, {
      file: basename,
      chunkIndex: idx,
      text: chunk,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
    });
  });

  await batch.commit();
  console.log(`Indexed ${chunks.length} chunks for ${basename}`);
}

async function main() {
  const dir = path.resolve(process.cwd(), 'documents/research/Global');
  const files = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.pdf'));
  for (const file of files) {
    console.log(`Processing ${file}...`);
    await processPdf(path.join(dir, file));
  }
  console.log('Ingestion complete.');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
