import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers } from '../../src/tools/project-info.js';

describe('project-info tools', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('TOOLS definitions', () => {
    it('should export 4 tool definitions', () => {
      assert.equal(TOOLS.length, 4);
    });

    it('should have correct tool names', () => {
      const names = TOOLS.map(t => t.name);
      assert.ok(names.includes('vtj_get_project_info'));
      assert.ok(names.includes('vtj_list_pages'));
      assert.ok(names.includes('vtj_list_blocks'));
      assert.ok(names.includes('vtj_list_apis'));
    });

    it('vtj_list_pages should have filter param', () => {
      const tool = TOOLS.find(t => t.name === 'vtj_list_pages');
      assert.ok(tool.inputSchema.properties.filter);
    });

    it('vtj_list_blocks should have category param', () => {
      const tool = TOOLS.find(t => t.name === 'vtj_list_blocks');
      assert.ok(tool.inputSchema.properties.category);
    });
  });

  describe('vtj_get_project_info handler', () => {
    it('should return success with project data', async () => {
      const result = await handlers.vtj_get_project_info({});
      assert.equal(result.success, true);
      assert.ok(result.data);
      assert.equal(result.data.name, 'Fixture Project');
      assert.ok(Array.isArray(result.data.pages));
      assert.equal(result.data.pages.length, 2);
    });

    it('should include blocks, apis and counts', async () => {
      const result = await handlers.vtj_get_project_info({});
      assert.ok(Array.isArray(result.data.blocks));
      assert.equal(result.data.blocks.length, 1);
      assert.ok(Array.isArray(result.data.apis));
      assert.equal(result.data.apis.length, 1);
      assert.equal(result.data.pagesCount, 2);
      assert.equal(result.data.blocksCount, 1);
      assert.equal(result.data.apisCount, 1);
      assert.equal(result.data.dependenciesCount, 1);
    });
  });

  describe('vtj_list_pages handler', () => {
    it('should return all pages by default', async () => {
      const result = await handlers.vtj_list_pages({});
      assert.equal(result.success, true);
      assert.ok(Array.isArray(result.data));
      assert.equal(result.data.length, 2);
      for (const page of result.data) {
        assert.ok(page.id);
        assert.ok(page.name);
        assert.ok(page.title);
        assert.equal(typeof page.raw, 'boolean');
        assert.ok(Array.isArray(page.routes));
      }
    });

    it('should filter raw pages', async () => {
      const result = await handlers.vtj_list_pages({ filter: 'raw' });
      assert.equal(result.success, true);
      assert.ok(result.data.length >= 1);
      assert.ok(result.data.every(p => p.raw === true));
    });

    it('should filter generated pages', async () => {
      const result = await handlers.vtj_list_pages({ filter: 'generated' });
      assert.equal(result.success, true);
      assert.ok(result.data.length >= 1);
      assert.ok(result.data.every(p => p.raw === false));
    });
  });

  describe('vtj_list_blocks handler', () => {
    it('should return blocks', async () => {
      const result = await handlers.vtj_list_blocks({});
      assert.equal(result.success, true);
      assert.ok(Array.isArray(result.data));
      assert.ok(result.data.length >= 1);
    });

    it('should filter blocks by category', async () => {
      const result = await handlers.vtj_list_blocks({ category: 'custom' });
      assert.equal(result.success, true);
      assert.ok(result.data.length >= 1);
      assert.ok(result.data.every(b => b.category === 'custom'));
    });

    it('should return empty list for unknown category', async () => {
      const result = await handlers.vtj_list_blocks({ category: 'nonexistent' });
      assert.equal(result.success, true);
      assert.equal(result.data.length, 0);
    });
  });

  describe('vtj_list_apis handler', () => {
    it('should return APIs', async () => {
      const result = await handlers.vtj_list_apis({});
      assert.equal(result.success, true);
      assert.ok(Array.isArray(result.data));
      assert.ok(result.data.length >= 1);
      const api = result.data[0];
      assert.ok(api.id);
      assert.ok(api.name);
      assert.ok(api.method);
      assert.ok(api.url);
    });
  });

  describe('error handling', () => {
    it('should return PROJECT_NOT_FOUND when no project config', async () => {
      const emptyRoot = mkdtempSync(join(tmpdir(), 'vtj-empty-'));
      mkdirSync(join(emptyRoot, '.vtj', 'projects'), { recursive: true });
      try {
        configure(emptyRoot);
        const result = await handlers.vtj_get_project_info({});
        assert.equal(result.success, false);
        assert.equal(result.error.code, 'PROJECT_NOT_FOUND');
      } finally {
        rmSync(emptyRoot, { recursive: true, force: true });
        configure(fixture.root);
      }
    });
  });
});
