/**
 * sync-operations 工具模块测试 — 期望 RED
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers } from '../../src/tools/sync-operations.js';

describe('sync-operations tools', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('TOOLS definitions', () => {
    it('should export 2 tool definitions', () => {
      assert.equal(TOOLS.length, 2);
      assert.equal(TOOLS[0].name, 'vtj_sync_vue_to_dsl');
      assert.equal(TOOLS[1].name, 'vtj_check_consistency');
    });

    it('vtj_sync_vue_to_dsl should have dryRun param', () => {
      const tool = TOOLS.find(t => t.name === 'vtj_sync_vue_to_dsl');
      assert.ok(tool.inputSchema.properties.dryRun);
    });
  });

  describe('vtj_sync_vue_to_dsl handler', () => {
    it('should sync methods from Vue to DSL', async () => {
      const result = await handlers.vtj_sync_vue_to_dsl({ id: fixture.pageIds[1] });
      assert.equal(result.success, true);
      assert.ok(result.data.methods !== undefined);
    });

    it('should block raw page sync', async () => {
      const result = await handlers.vtj_sync_vue_to_dsl({ id: fixture.rawPageId });
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'RAW_PAGE_PROTECTED');
    });

    it('should support dryRun without writing', async () => {
      const result = await handlers.vtj_sync_vue_to_dsl({ id: fixture.pageIds[1], dryRun: true });
      assert.equal(result.dryRun, true);
    });
  });

  describe('vtj_check_consistency handler', () => {
    it('should check specific page', async () => {
      const result = await handlers.vtj_check_consistency({ id: fixture.pageIds[1] });
      assert.ok(result);
      assert.ok(typeof result.checked === 'number');
    });

    it('should check all pages when no id', async () => {
      const result = await handlers.vtj_check_consistency({});
      assert.ok(result);
      assert.ok(result.checked >= 1);
    });
  });
});
