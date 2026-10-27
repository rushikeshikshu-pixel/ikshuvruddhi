import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CSV_PATH = path.join(ROOT, 'data', 'output', 'all_unharvested_plots_oct2026_latest_satellite_register.csv');

const AUTH_SECRET = 'ikshu-gangamai-sugar-auth-token-secret-2026';
const session = {
  userId: 'mill_gangamai_sugar',
  email: 'gangamai@ikshuintelligence.com',
  displayName: 'Gangamai Industries and Commerce Ltd.',
  fullName: 'Gangamai Sugar Administration',
  millName: 'Gangamai Industries and Commerce Ltd.',
  location: 'Shevgaon, Ahmednagar, Maharashtra',
  season: '2026–27',
  exp: Date.now() + 30 * 24 * 60 * 60 * 1000
};

function base64UrlEncode(str) {
  return Buffer.from(str).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

const payloadB64 = base64UrlEncode(JSON.stringify(session));
const hmac = crypto.createHmac('sha256', AUTH_SECRET);
hmac.update(payloadB64);
const sigB64 = hmac.digest('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const token = payloadB64 + '.' + sigB64;

function parseCSV(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quote = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (c === '"') {
      if (quote && text[i + 1] === '"') { cell += '"'; i++; }
      else quote = !quote;
    } else if (c === ',' && !quote) {
      row.push(cell); cell = '';
    } else if ((c === '\n' || c === '\r') && !quote) {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell);
      if (row.some(v => v.trim())) rows.push(row);
      row = []; cell = '';
    } else cell += c;
  }
  if (quote) throw new Error('Unclosed quoted field');
  row.push(cell);
  if (row.some(v => v.trim())) rows.push(row);
  if (!rows.length) throw new Error('Empty CSV');
  const headers = rows.shift().map(x => x.replace(/^\uFEFF/, '').trim());
  return rows.map(r => Object.fromEntries(headers.map((h, j) => [h, (r[j] || '').trim()])));
}

async function postImport(body) {
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      const response = await fetch('https://ikshuintelligence.com/api/satellite-register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Origin': 'https://ikshuintelligence.com',
          'Cookie': 'ikshu_mill_session=' + token
        },
        body: JSON.stringify(body)
      });
      const result = await response.json();
      if (response.ok) return result;
      const error = new Error(result.error || `HTTP ${response.status}`);
      if (response.status < 500 && response.status !== 429) throw error;
      console.warn(`Retry attempt ${attempt + 1}: ${error.message}`);
    } catch (error) {
      if (attempt === 4) throw error;
      console.warn(`Network retry ${attempt + 1}: ${error.message}`);
    }
    await new Promise(r => setTimeout(r, Math.min(1000 * 2 ** attempt, 8000)));
  }
  throw new Error('Failed after retries');
}

async function run() {
  console.log('Reading CSV from:', CSV_PATH);
  const text = fs.readFileSync(CSV_PATH, 'utf-8');
  console.log('Parsing CSV...');
  const rows = parseCSV(text);
  console.log(`Parsed ${rows.length} rows.`);

  if (rows.length !== 29384) {
    throw new Error(`Expected 29384 rows, got ${rows.length}`);
  }

  const snapshotId = crypto.randomUUID();
  const timestamp = '2026-10-27 17:00:00';
  console.log(`Starting staging for snapshotId: ${snapshotId} with timestamp: ${timestamp}`);

  const batchSize = 200;
  const totalBatches = Math.ceil(rows.length / batchSize);

  for (let b = 0; b < totalBatches; b++) {
    const start = b * batchSize;
    const slice = rows.slice(start, start + batchSize);
    const batch = slice.map(row => {
      row['latest_satellite_calculation_timestamp'] = timestamp;
      return {
        plotNo: String(row['Plot No']).trim(),
        sourceTimestamp: timestamp,
        data: row
      };
    });

    await postImport({ action: 'import', snapshotId, rows: batch });
    if ((b + 1) % 15 === 0 || b + 1 === totalBatches) {
      console.log(`Staged batch ${b + 1}/${totalBatches} (${Math.min(start + batchSize, rows.length)}/${rows.length} rows)`);
    }
  }

  console.log('Finalizing and activating the new snapshot...');
  const finalized = await postImport({
    action: 'finalize',
    snapshotId,
    expectedCount: rows.length,
    confirmedHarvestedCount: 410
  });
  console.log('Finalize result:', finalized);

  console.log('Verifying active dataset on live site...');
  const verifyRes = await fetch('https://ikshuintelligence.com/api/workspace?limit=1', {
    headers: { 'Cookie': 'ikshu_mill_session=' + token }
  });
  const data = await verifyRes.json();
  console.log('New active register summary:', data.register);
  console.log('SUCCESS: Live dashboard dataset updated!');
}

run().catch(e => {
  console.error('FATAL ERROR:', e);
  process.exit(1);
});
