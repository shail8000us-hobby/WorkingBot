#!/usr/bin/env node
/**
 * Help Coverage Validation Script
 * 
 * Validates that all UI controls with data-action-id have corresponding
 * entries in the help registry. Fails CI if unmapped actions are found.
 */

const fs = require('fs');
const path = require('path');

// Paths
const REGISTRY_PATH = path.join(__dirname, '../../backend/help/help_registry.json');
const SRC_DIR = path.join(__dirname, '../src');

// Simple file walker (avoiding dependencies)
function walkSync(dir, fileList = []) {
  const files = fs.readdirSync(dir);
  
  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat.isDirectory()) {
      fileList = walkSync(filePath, fileList);
    } else if (file.endsWith('.js') || file.endsWith('.jsx')) {
      fileList.push(filePath);
    }
  });
  
  return fileList;
}

function main() {
  console.log('🔍 Validating Help System Coverage...\n');

  // Load help registry
  if (!fs.existsSync(REGISTRY_PATH)) {
    console.error('❌ Help registry not found at:', REGISTRY_PATH);
    console.error('   Run: npm run help:build\n');
    process.exit(1);
  }

  const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
  const actionIds = new Set(registry.map(a => a.action_id));

  console.log(`✅ Loaded ${actionIds.size} actions from registry`);

  // Find all data-action-id attributes in source files
  const files = walkSync(SRC_DIR);
  const usedActionIds = new Set();
  const unmappedActions = [];
  const fileUsage = {};

  files.forEach(file => {
    const content = fs.readFileSync(file, 'utf8');
    const regex = /data-action-id=["']([^"']+)["']/g;
    let match;
    
    while ((match = regex.exec(content)) !== null) {
      const actionId = match[1];
      usedActionIds.add(actionId);
      
      if (!actionIds.has(actionId)) {
        unmappedActions.push({ 
          file: path.relative(process.cwd(), file), 
          actionId 
        });
      }
      
      // Track file usage
      if (!fileUsage[file]) {
        fileUsage[file] = [];
      }
      fileUsage[file].push(actionId);
    }
  });

  console.log(`✅ Found ${usedActionIds.size} action IDs in frontend code`);
  console.log(`✅ Scanned ${files.length} source files\n`);

  // Report unmapped actions
  if (unmappedActions.length > 0) {
    console.error(`❌ ${unmappedActions.length} UNMAPPED ACTIONS FOUND:\n`);
    
    unmappedActions.forEach(({ file, actionId }) => {
      console.error(`   ⚠️  "${actionId}" in ${file}`);
    });
    
    console.error('\n💡 To fix:');
    console.error('   1. Ensure backend route exists for this action');
    console.error('   2. Add docstring or @help annotation to the route handler');
    console.error('   3. Run: npm run help:build');
    console.error('   4. Commit updated help_registry.json\n');
    
    process.exit(1);
  }

  // Report backend actions with no frontend usage
  const unusedActions = [...actionIds].filter(id => !usedActionIds.has(id));
  
  if (unusedActions.length > 0) {
    console.log(`ℹ️  ${unusedActions.length} backend actions have no UI controls:`);
    unusedActions.slice(0, 10).forEach(id => {
      console.log(`   • ${id}`);
    });
    if (unusedActions.length > 10) {
      console.log(`   ... and ${unusedActions.length - 10} more`);
    }
    console.log('\n   This is OK if they are API-only endpoints.\n');
  }

  // Success summary
  console.log('═'.repeat(60));
  console.log('✅ HELP SYSTEM VALIDATION PASSED');
  console.log('═'.repeat(60));
  console.log(`📊 Coverage: ${usedActionIds.size}/${actionIds.size} actions documented`);
  console.log(`📁 Files scanned: ${files.length}`);
  console.log(`🔒 No unmapped actions found`);
  console.log('═'.repeat(60));
  console.log('\n✨ All UI controls have help documentation!\n');
}

// Run
try {
  main();
} catch (error) {
  console.error('❌ Validation failed:', error.message);
  process.exit(1);
}
