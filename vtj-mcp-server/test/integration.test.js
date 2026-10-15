/**
 * 集成测试 — E2E 覆盖 19 工具 + 3 资源
 * 使用 handleToolCall / readResource 直接调用，验证全模块联动
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from './fixtures/buildFixture.js';
import { configure } from '../src/core/file-system.js';
import { handleToolCall, readResource, ALL_TOOLS, RESOURCES } from '../src/server.js';

function parse(text) {
  return JSON.parse(text);
}

describe('integration — E2E across all modules', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('metadata', () => {
    it('should export 19 tool definitions', () => {
      assert.equal(ALL_TOOLS.length, 19);
    });

    it('should export 3 resource definitions', () => {
      assert.equal(RESOURCES.length, 3);
    });

    it('should have all 19 tool names', () => {
      const names = ALL_TOOLS.map(t => t.name);
      const expected = [
        'vtj_get_project_info', 'vtj_list_pages', 'vtj_list_blocks', 'vtj_list_apis',
        'vtj_read_vue_file', 'vtj_write_vue_script', 'vtj_read_dsl_file',
        'vtj_write_vue_template', 'vtj_write_vue_style', 'vtj_write_dsl_file',
        'vtj_write_vue_full',
        'vtj_sync_vue_to_dsl', 'vtj_check_consistency',
        'vtj_get_page_structure',
        'vtj_get_routing_info', 'vtj_add_route',
        'vtj_get_material_catalog', 'vtj_get_component_detail',
        'vtj_create_page_scaffold'
      ];
      for (const name of expected) {
        assert.ok(names.includes(name), `missing tool: ${name}`);
      }
    });
  });

  describe('workflow: read -> write -> sync', () => {
    it('step 1: read vue file', async () => {
      const result = parse((await handleToolCall('vtj_read_vue_file', { id: fixture.pageIds[0] })).content[0].text);
      // Returns {success: true, data: "<full vue content string>"}
      assert.ok(result.success !== false, JSON.stringify(result).slice(0, 300));
      assert.ok(typeof result.data === 'string' || result.data?.content, `expected string or content, got: ${typeof result.data}`);
    });

    it('step 2: read dsl file', async () => {
      const result = parse((await handleToolCall('vtj_read_dsl_file', { id: fixture.pageIds[0] })).content[0].text);
      // Returns {success: true, data: {id, path, name, dsl: {...}, ...}}
      assert.ok(result.success !== false, JSON.stringify(result).slice(0, 300));
      assert.ok(result.data?.dsl || result.data?.id, `expected dsl data, got: ${JSON.stringify(result).slice(0, 300)}`);
    });

    it('step 3: write vue script (dryRun)', async () => {
      const result = parse((await handleToolCall('vtj_write_vue_script', {
        id: fixture.pageIds[1],
        content: '// dry run test',
        dryRun: true
      })).content[0].text);
      assert.equal(result.dryRun, true);
    });

    it('step 4: sync vue to dsl', async () => {
      const result = parse((await handleToolCall('vtj_sync_vue_to_dsl', { id: fixture.pageIds[1] })).content[0].text);
      assert.equal(result.success, true);
    });

    it('step 5: check consistency', async () => {
      const result = parse((await handleToolCall('vtj_check_consistency', { id: fixture.pageIds[1] })).content[0].text);
      assert.ok(typeof result.checked === 'number');
    });
  });

  describe('workflow: scaffold -> route -> query', () => {
    it('step 1: create scaffold (dryRun)', async () => {
      const result = parse((await handleToolCall('vtj_create_page_scaffold', {
        id: 'e2e_test_page',
        name: 'E2ETestPage',
        title: 'E2E 测试页面',
        dryRun: true
      })).content[0].text);
      assert.equal(result.dryRun, true);
    });

    it('step 2: add route (dryRun)', async () => {
      const result = parse((await handleToolCall('vtj_add_route', {
        path: '/e2e-test',
        name: 'E2ETestPage',
        dryRun: true
      })).content[0].text);
      assert.equal(result.dryRun, true);
    });

    it('step 3: query material catalog', async () => {
      const result = parse((await handleToolCall('vtj_get_material_catalog', {})).content[0].text);
      assert.ok(result);
    });
  });

  describe('workflow: project exploration', () => {
    it('get project info', async () => {
      const result = parse((await handleToolCall('vtj_get_project_info', {})).content[0].text);
      assert.equal(result.success, true);
    });

    it('list pages with raw filter', async () => {
      const result = parse((await handleToolCall('vtj_list_pages', { filter: 'raw' })).content[0].text);
      // Returns {success, data: [...]} where data is directly the pages array
      const pages = Array.isArray(result.data) ? result.data : (result.data?.pages ?? result.pages);
      assert.ok(Array.isArray(pages), `expected array, got: ${JSON.stringify(result).slice(0, 200)}`);
    });

    it('list pages with generated filter', async () => {
      const result = parse((await handleToolCall('vtj_list_pages', { filter: 'generated' })).content[0].text);
      const pages = Array.isArray(result.data) ? result.data : (result.data?.pages ?? result.pages);
      assert.ok(Array.isArray(pages), `expected array, got: ${JSON.stringify(result).slice(0, 200)}`);
    });

    it('list blocks', async () => {
      const result = parse((await handleToolCall('vtj_list_blocks', {})).content[0].text);
      const blocks = Array.isArray(result.data) ? result.data : (result.data?.blocks ?? result.blocks);
      assert.ok(Array.isArray(blocks), `expected array, got: ${JSON.stringify(result).slice(0, 200)}`);
    });

    it('list apis', async () => {
      const result = parse((await handleToolCall('vtj_list_apis', {})).content[0].text);
      const apis = Array.isArray(result.data) ? result.data : (result.data?.apis ?? result.apis);
      assert.ok(Array.isArray(apis), `expected array, got: ${JSON.stringify(result).slice(0, 200)}`);
    });

    it('get routing info', async () => {
      const result = parse((await handleToolCall('vtj_get_routing_info', {})).content[0].text);
      assert.ok(result);
    });

    it('get page structure', async () => {
      const result = parse((await handleToolCall('vtj_get_page_structure', { id: fixture.pageIds[0] })).content[0].text);
      assert.ok(result);
    });

    it('get component detail', async () => {
      const result = parse((await handleToolCall('vtj_get_component_detail', { name: 'ElButton' })).content[0].text);
      assert.ok(result);
    });
  });

  describe('resource reads', () => {
    it('vtj://project/config', async () => {
      const result = await readResource('vtj://project/config');
      assert.ok(result.contents[0].text);
    });

    it('vtj://project/routing', async () => {
      const result = await readResource('vtj://project/routing');
      assert.ok(result.contents[0].text);
    });

    it('vtj://materials/catalog', async () => {
      const result = await readResource('vtj://materials/catalog');
      assert.ok(result.contents[0].text);
    });
  });

  describe('error handling', () => {
    it('unknown tool returns error', async () => {
      const result = parse((await handleToolCall('nonexistent_tool', {})).content[0].text);
      assert.ok(result.error);
    });

    it('unknown resource throws', async () => {
      try {
        await readResource('unknown://resource');
        assert.fail('should have thrown');
      } catch (e) {
        assert.ok(e.message.includes('未知资源'));
      }
    });

    it('read missing vue file returns error', async () => {
      const result = parse((await handleToolCall('vtj_read_vue_file', { id: 'nonexistent_id' })).content[0].text);
      assert.equal(result.success, false);
    });

    it('read missing dsl file returns error', async () => {
      const result = parse((await handleToolCall('vtj_read_dsl_file', { id: 'nonexistent_id' })).content[0].text);
      assert.equal(result.success, false);
    });

    it('create scaffold duplicate id returns error', async () => {
      await handleToolCall('vtj_create_page_scaffold', {
        id: 'dup_test', name: 'DupTest', title: '重复测试'
      });
      const result = parse((await handleToolCall('vtj_create_page_scaffold', {
        id: 'dup_test', name: 'DupTest2', title: '重复测试2'
      })).content[0].text);
      assert.equal(result.success, false);
    });
  });

  describe('write operations with actual file changes', () => {
    it('write vue script replace mode', async () => {
      const result = parse((await handleToolCall('vtj_write_vue_script', {
        id: fixture.pageIds[1],
        scriptContent: 'console.log("integration test");',
        mode: 'replace'
      })).content[0].text);
      assert.equal(result.success, true);
    });

    it('verify written content', async () => {
      const result = parse((await handleToolCall('vtj_read_vue_file', {
        id: fixture.pageIds[1]
      })).content[0].text);
      // data is either a string (full vue) or an object with content
      const raw = typeof result.data === 'string' ? result.data : (result.data?.content ?? '');
      assert.ok(raw.includes('integration test'), `expected integration test in response, got: ${String(raw).slice(0, 200)}`);
    });

    it('write dsl state section', async () => {
      const result = parse((await handleToolCall('vtj_write_dsl_file', {
        id: fixture.pageIds[1],
        section: 'state',
        content: { counter: { type: 'JSExpression', value: '0' } }
      })).content[0].text);
      const success = result.data?.success ?? result.success;
      assert.ok(success !== false, `expected success, got: ${JSON.stringify(result).slice(0, 200)}`);
    });
  });
});
