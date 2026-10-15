/**
 * project-actions 工具模块测试 — 期望 RED
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers } from '../../src/tools/project-actions.js';

describe('project-actions tools', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('TOOLS definitions', () => {
    it('should export 1 tool definition', () => {
      assert.equal(TOOLS.length, 1);
      assert.equal(TOOLS[0].name, 'vtj_create_page_scaffold');
    });

    it('should have required params', () => {
      const tool = TOOLS[0];
      assert.ok(tool.inputSchema.properties.id);
      assert.ok(tool.inputSchema.properties.name);
      assert.ok(tool.inputSchema.properties.title);
      assert.ok(tool.inputSchema.properties.addRoute);
    });
  });

  describe('vtj_create_page_scaffold handler', () => {
    it('should create page scaffold files', async () => {
      const result = await handlers.vtj_create_page_scaffold({
        id: 'test_scaffold_1',
        name: 'TestScaffold',
        title: '测试脚手架页面'
      });
      assert.equal(result.success, true);
      assert.ok(result.data.files);
      assert.ok(result.data.files.vue);
      assert.ok(result.data.files.dsl);
    });

    it('should support dryRun without creating files', async () => {
      const result = await handlers.vtj_create_page_scaffold({
        id: 'test_scaffold_dryrun',
        name: 'TestDryRun',
        title: '测试 dryRun',
        dryRun: true
      });
      assert.equal(result.dryRun, true);
    });

    it('should return error for duplicate ID', async () => {
      // First create
      await handlers.vtj_create_page_scaffold({
        id: 'test_dup_id',
        name: 'TestDup',
        title: '测试重复'
      });
      // Then try same ID
      const result = await handlers.vtj_create_page_scaffold({
        id: 'test_dup_id',
        name: 'TestDup2',
        title: '测试重复2'
      });
      assert.equal(result.success, false);
    });
  });
});
