#!/usr/bin/env node
/**
 * Tailwind v4 Configuration Checker
 * Run with: node check-tailwind.js
 */

const fs = require('fs');
const path = require('path');

console.log('🔍 Checking Tailwind v4 Configuration...\n');

// Check 1: globals.css import syntax
try {
  const globalsCss = fs.readFileSync('src/app/globals.css', 'utf8');
  const hasCorrectImport = globalsCss.includes('@import "tailwindcss";');
  const hasWrongImport = globalsCss.includes('@import url("tailwindcss")');
  
  if (hasCorrectImport && !hasWrongImport) {
    console.log('✅ globals.css: Correct @import "tailwindcss"; syntax');
  } else if (hasWrongImport) {
    console.log('❌ globals.css: Wrong syntax! Use @import "tailwindcss"; (not url())');
  } else {
    console.log('❌ globals.css: Missing Tailwind import!');
  }
} catch (err) {
  console.log('❌ globals.css: File not found!');
}

// Check 2: PostCSS config
try {
  const postcssConfig = fs.readFileSync('postcss.config.mjs', 'utf8');
  const hasCorrectPlugin = postcssConfig.includes('["@tailwindcss/postcss"]');
  const hasWrongPlugin = postcssConfig.includes('{ \'@tailwindcss/postcss\': {} }');
  
  if (hasCorrectPlugin && !hasWrongPlugin) {
    console.log('✅ postcss.config.mjs: Correct array syntax');
  } else if (hasWrongPlugin) {
    console.log('❌ postcss.config.mjs: Wrong syntax! Use array format');
  } else {
    console.log('❌ postcss.config.mjs: Missing correct plugin config!');
  }
} catch (err) {
  console.log('❌ postcss.config.mjs: File not found!');
}

// Check 3: No conflicting config files
const configFiles = ['tailwind.config.js', 'tailwind.config.ts', 'tailwind.config.mjs'];
configFiles.forEach(file => {
  if (fs.existsSync(file)) {
    console.log(`❌ ${file}: This file conflicts with Tailwind v4! Delete it.`);
  } else {
    console.log(`✅ ${file}: Not present (correct for v4)`);
  }
});

// Check 4: Package.json dependencies
try {
  const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
  const deps = { ...packageJson.dependencies, ...packageJson.devDependencies };
  
  if (deps['@tailwindcss/postcss'] && deps['tailwindcss']) {
    console.log('✅ package.json: Tailwind v4 dependencies present');
  } else {
    console.log('❌ package.json: Missing Tailwind v4 dependencies!');
  }
} catch (err) {
  console.log('❌ package.json: Cannot read file!');
}

console.log('\n📖 See TAILWIND_V4_SETUP.md for detailed instructions');
