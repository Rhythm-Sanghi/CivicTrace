#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const distAssetsDir = path.resolve(__dirname, '..', 'dist', 'assets');
if (!fs.existsSync(distAssetsDir)) {
  console.error('[Security Verification Error] dist/assets directory not found. Run vite build first.');
  process.exit(1);
}

const jsFiles = fs.readdirSync(distAssetsDir).filter((f) => f.endsWith('.js'));
if (jsFiles.length === 0) {
  console.error('[Security Verification Error] No compiled JS files found in dist/assets.');
  process.exit(1);
}

const forbiddenStrings = [
  'AdminPass2026!',
  'CitizenPass2026!',
  'ReviewerPass2026!',
  'OperatorPass2026!',
  'One-Click Seed Accounts',
];

let violationFound = false;

for (const file of jsFiles) {
  const filePath = path.join(distAssetsDir, file);
  const content = fs.readFileSync(filePath, 'utf8');

  for (const forbidden of forbiddenStrings) {
    if (content.includes(forbidden)) {
      console.error(
        `[Security Violation] Found forbidden demo credential or control "${forbidden}" in production bundle: ${file}`
      );
      violationFound = true;
    }
  }
}

if (violationFound) {
  process.exit(1);
}

console.log(
  `[Security Verification] Verified ${jsFiles.length} production bundle asset(s): zero demo credentials or seed controls found.`
);
