import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers } from '../../src/tools/file-operations.js';

describe('file-operations tools', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('TOOLS definitions', () => {
    it('should export 7 tool definitions', () => {
      assert.equal(TOOLS.length, 7);
    });

    it('should have all expected tool names', () => {
      const names = TOOLS.map(t => t.name);
      assert.ok(names.includes('vtj_read_vue_file'));
      assert.ok(names.includes('vtj_write_vue_script'));
      assert.ok(names.includes('vtj_read_dsl_file'));
      assert.ok(names.includes('vtj_write_vue_template'));
      assert.ok(names.includes('vtj_write_vue_style'));
      assert.ok(names.includes('vtj_write_dsl_file'));
      assert.ok(names.includes('vtj_write_vue_full'));
    });

    it('write tools should have dryRun param', () => {
      const writeTools = TOOLS.filter(t => t.name.startsWith('vtj_write'));
      for (const tool of writeTools) {
        assert.ok(tool.inputSchema.properties.dryRun, `${tool.name} missing dryRun`);
      }
    });
  });

  describe('vtj_read_vue_file handler', () => {
    it('should read full vue file', async () => {
      const result = await handlers.vtj_read_vue_file({ id: fixture.pageIds[0], section: 'full' });
      assert.equal(result.success, true);
      assert.ok(result.data.includes('template'));
    });

    it('should return FILE_NOT_FOUND for missing id', async () => {
      const result = await handlers.vtj_read_vue_file({ id: 'nonexistent' });
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'FILE_NOT_FOUND');
    });
  });

  describe('vtj_write_vue_script handler', () => {
    it('should support dryRun without writing', async () => {
      const result = await handlers.vtj_write_vue_script({
        id: fixture.pageIds[1],
        scriptContent: '<script>test</script>',
        mode: 'replace',
        dryRun: true
      });
      assert.equal(result.dryRun, true);
    });

    it('should return error for invalid mode', async () => {
      const result = await handlers.vtj_write_vue_script({
        id: fixture.pageIds[1],
        scriptContent: 'test',
        mode: 'invalid'
      });
      assert.equal(result.success, false);
    });
  });

  describe('vtj_read_dsl_file handler', () => {
    it('should read DSL file', async () => {
      const result = await handlers.vtj_read_dsl_file({ id: fixture.pageIds[0] });
      assert.equal(result.success, true);
    });
  });

  describe('vtj_write_vue_template with dryRun', () => {
    it('should preview without writing when dryRun=true', async () => {
      const result = await handlers.vtj_write_vue_template({
        id: fixture.pageIds[1],
        templateContent: '<template><div>test</div></template>',
        dryRun: true
      });
      assert.equal(result.dryRun, true);
    });
  });

  describe('vtj_write_dsl_file with dryRun', () => {
    it('should preview without writing when dryRun=true', async () => {
      const result = await handlers.vtj_write_dsl_file({
        id: fixture.pageIds[1],
        section: 'methods',
        content: '{}',
        dryRun: true
      });
      assert.equal(result.dryRun, true);
    });
  });

  describe('vtj_write_vue_full with dryRun', () => {
    it('should preview without writing when dryRun=true', async () => {
      const result = await handlers.vtj_write_vue_full({
        id: fixture.pageIds[1],
        content: '<template></template><script></script>',
        dryRun: true
      });
      assert.equal(result.dryRun, true);
    });
  });
});
