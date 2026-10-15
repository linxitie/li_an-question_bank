import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers } from '../../src/tools/structure-analysis.js';

describe('structure-analysis tools', () => {
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
      assert.equal(TOOLS[0].name, 'vtj_get_page_structure');
    });

    it('should have id and depth params', () => {
      assert.ok(TOOLS[0].inputSchema.properties.id);
      assert.ok(TOOLS[0].inputSchema.properties.depth);
    });
  });

  describe('vtj_get_page_structure handler', () => {
    it('should return page structure', async () => {
      const result = await handlers.vtj_get_page_structure({ id: fixture.pageIds[0] });
      assert.equal(result.success, true);
      assert.ok(result.data.structure);
      assert.ok(typeof result.data.rootNodesCount === 'number');
    });

    it('should respect depth parameter', async () => {
      const result = await handlers.vtj_get_page_structure({ id: fixture.pageIds[0], depth: 1 });
      assert.equal(result.success, true);
    });

    it('should return FILE_NOT_FOUND for missing DSL', async () => {
      const result = await handlers.vtj_get_page_structure({ id: 'nonexistent' });
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'FILE_NOT_FOUND');
    });
  });
});
