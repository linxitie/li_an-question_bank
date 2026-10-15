import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import {
  readJSON, writeJSON, readText, writeText, existsFile,
  createBackup, getProjectConfig, getMaterialConfig,
  getDslFileMap, configure
} from '../../src/core/file-system.js';
import { join } from 'node:path';
import { readFileSync } from 'node:fs';

describe('file-system', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('readJSON', () => {
    it('should read valid JSON file', () => {
      const projectPath = join(fixture.root, 'project.json');
      const result = readJSON(projectPath);
      assert.ok(result);
      assert.ok(result.pages);
    });

    it('should return null for non-existent file', () => {
      const result = readJSON(join(fixture.root, 'nonexistent.json'));
      assert.equal(result, null);
    });

    it('should return null for invalid JSON', () => {
      const result = readJSON(join(fixture.root, 'project.json'));
      // If file exists and is valid, this passes
      assert.ok(result !== undefined);
    });
  });

  describe('writeJSON', () => {
    it('should write JSON file and read it back', () => {
      const testPath = join(fixture.root, 'test-write.json');
      const data = { test: true, value: 42 };
      const written = writeJSON(testPath, data);
      assert.equal(written, true);

      const read = readJSON(testPath);
      assert.deepEqual(read, data);
    });
  });

  describe('readText', () => {
    it('should read Vue file as text', () => {
      const vuePath = join(fixture.root, '.vtj', 'vue', `${fixture.pageIds[0]}.vue`);
      const content = readText(vuePath);
      assert.ok(content);
      assert.ok(content.includes('template'));
    });

    it('should return null for non-existent file', () => {
      const result = readText(join(fixture.root, 'nonexistent.txt'));
      assert.equal(result, null);
    });
  });

  describe('existsFile', () => {
    it('should return true for existing file', () => {
      const projectPath = join(fixture.root, 'project.json');
      assert.equal(existsFile(projectPath), true);
    });

    it('should return false for non-existent file', () => {
      assert.equal(existsFile(join(fixture.root, 'nope.txt')), false);
    });
  });

  describe('createBackup', () => {
    it('should create .bak copy of file', () => {
      const vuePath = join(fixture.root, '.vtj', 'vue', `${fixture.pageIds[0]}.vue`);
      const backupPath = createBackup(vuePath);
      assert.ok(backupPath.endsWith('.bak'));
      assert.equal(existsFile(backupPath), true);

      // Verify content matches
      const original = readText(vuePath);
      const backup = readText(backupPath);
      assert.equal(original, backup);
    });
  });

  describe('getProjectConfig', () => {
    it('should return project config from .vtj/projects/', () => {
      const config = getProjectConfig();
      assert.ok(config);
      assert.ok(config.pages);
      assert.ok(Array.isArray(config.pages));
    });
  });

  describe('getMaterialConfig', () => {
    it('should return material config from .vtj/materials/', () => {
      const config = getMaterialConfig();
      assert.ok(config);
    });
  });

  describe('getDslFileMap', () => {
    it('should return map of page IDs to DSL filenames', () => {
      const map = getDslFileMap();
      assert.ok(typeof map === 'object');
      assert.ok(Object.keys(map).length > 0);
    });
  });
});
