const fs = require('fs');
const path = require('path');

const STORE_PATH = path.join(__dirname, '..', 'data', 'seen.json');
const MAX_ENTRIES = 500;

function load() {
  try {
    const raw = fs.readFileSync(STORE_PATH, 'utf8');
    return new Set(JSON.parse(raw));
  } catch {
    return new Set();
  }
}

function save(seenSet) {
  const entries = Array.from(seenSet).slice(-MAX_ENTRIES);
  fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(entries));
}

module.exports = { load, save };
