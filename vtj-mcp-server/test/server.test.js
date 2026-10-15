/**
 * server 模块测试 — 期望 RED
 * 验证 createServer 注册 19 个工具 + 3 个资源
 */

import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from './fixtures/buildFixture.js';
import { configure } from '../src/core/file-system.js';
import { createServer, handleToolCall, readResource } from '../src/server.js';

describe('server', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('createServer', () => {
    it('should create a server instance', () => {
      const server = createServer({ projectRoot: fixture.root });
      assert.ok(server);
    });
  });

  describe('handleToolCall — 19 tools', () => {
    const ALL_19_TOOLS = [
      'vtj_get_project_info',
      'vtj_list_pages',
      'vtj_list_blocks',
      'vtj_list_apis',
      'vtj_read_vue_file',
      'vtj_write_vue_script',
      'vtj_read_dsl_file',
      'vtj_write_vue_template',
      'vtj_write_vue_style',
      'vtj_write_dsl_file',
      'vtj_write_vue_full',
      'vtj_sync_vue_to_dsl',
      'vtj_check_consistency',
      'vtj_get_page_structure',
      'vtj_get_routing_info',
      'vtj_add_route',
      'vtj_get_material_catalog',
      'vtj_get_component_detail',
      'vtj_create_page_scaffold'
    ];

    for (const toolName of ALL_19_TOOLS) {
      it(`should dispatch ${toolName}`, async () => {
        const result = await handleToolCall(toolName, {});
        assert.ok(result.content, `${toolName} must return content`);
        assert.ok(Array.isArray(result.content), 'content must be array');
        assert.ok(result.content.length > 0, 'content must not be empty');
      });
    }

    it('should return structured error for unknown tool', async () => {
      const result = await handleToolCall('unknown_tool_xyz', {});
      const data = JSON.parse(result.content[0].text);
      assert.ok(data.error, 'should have error field');
    });
  });

  describe('readResource — 3 resources', () => {
    const RESOURCES = [
      'vtj://project/config',
      'vtj://project/routing',
      'vtj://materials/catalog'
    ];

    for (const uri of RESOURCES) {
      it(`should read ${uri}`, async () => {
        const result = await readResource(uri);
        assert.ok(result.contents, 'must return contents array');
        assert.ok(result.contents.length > 0, 'contents must not be empty');
        assert.ok(result.contents[0].text, 'must have text');
      });
    }

    it('should throw for unknown resource', async () => {
      try {
        await readResource('unknown://resource');
        assert.fail('should have thrown');
      } catch (e) {
        assert.ok(e.message.includes('未知资源'));
      }
    });
  });
});
