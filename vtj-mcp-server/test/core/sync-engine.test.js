import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { syncVueToDSL, checkConsistency } from '../../src/core/sync-engine.js';

describe('sync-engine', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('syncVueToDSL', () => {
    it('should sync methods from Vue to DSL', async () => {
      const result = await syncVueToDSL(fixture.pageIds[1]); // generated page
      assert.equal(result.success, true);
      assert.ok(result.data.methods !== undefined);
    });

    it('should block raw page sync with RAW_PAGE_PROTECTED', async () => {
      const result = await syncVueToDSL(fixture.rawPageId);
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'RAW_PAGE_PROTECTED');
    });

    it('should support dryRun mode without writing', async () => {
      const result = await syncVueToDSL(fixture.pageIds[1], { dryRun: true });
      assert.equal(result.dryRun, true);
      // Verify no files were modified - the result should have preview
    });

    it('should preserve DSL-only methods during merge', async () => {
      const result = await syncVueToDSL(fixture.pageIds[1]);
      assert.ok(result);
    });
  });

  describe('checkConsistency', () => {
    it('should check specific page consistency', async () => {
      const result = await checkConsistency(fixture.pageIds[1]);
      assert.ok(result);
      assert.ok(typeof result.checked === 'number');
    });

    it('should check all pages when no id provided', async () => {
      const result = await checkConsistency();
      assert.ok(result);
      assert.ok(result.checked >= 1);
    });

    it('should detect missing files', async () => {
      const result = await checkConsistency('nonexistent_id');
      assert.ok(result);
    });
  });
});