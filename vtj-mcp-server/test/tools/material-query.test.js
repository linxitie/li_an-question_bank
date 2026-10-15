import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers } from '../../src/tools/material-query.js';

describe('material-query tools', () => {
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
      assert.equal(TOOLS[0].name, 'vtj_get_material_catalog');
      assert.equal(TOOLS[1].name, 'vtj_get_component_detail');
    });
  });

  describe('vtj_get_material_catalog handler', () => {
    it('should return material catalog', async () => {
      const result = await handlers.vtj_get_material_catalog({});
      assert.equal(result.success, true);
      assert.ok(result.data);
    });

    it('should support category filter', async () => {
      const result = await handlers.vtj_get_material_catalog({ category: 'base' });
      assert.equal(result.success, true);
    });

    it('should support search', async () => {
      const result = await handlers.vtj_get_material_catalog({ search: 'button' });
      assert.equal(result.success, true);
    });
  });

  describe('vtj_get_component_detail handler', () => {
    it('should return component detail', async () => {
      const result = await handlers.vtj_get_component_detail({ name: 'el-button' });
      assert.equal(result.success, true);
      assert.ok(result.data.props !== undefined);
    });

    it('should return MATERIAL_NOT_FOUND for unknown component', async () => {
      const result = await handlers.vtj_get_component_detail({ name: 'nonexistent_xyz' });
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'MATERIAL_NOT_FOUND');
    });
  });
});
