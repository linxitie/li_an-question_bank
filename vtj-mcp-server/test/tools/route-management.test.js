import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { rmSync } from 'node:fs';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure } from '../../src/core/file-system.js';
import { TOOLS, handlers, addStaticRoute } from '../../src/tools/route-management.js';

describe('route-management tools', () => {
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
      assert.equal(TOOLS[0].name, 'vtj_get_routing_info');
      assert.equal(TOOLS[1].name, 'vtj_add_route');
    });

    it('vtj_add_route should have dryRun param', () => {
      const tool = TOOLS.find(t => t.name === 'vtj_add_route');
      assert.ok(tool.inputSchema.properties.dryRun);
    });
  });

  describe('vtj_get_routing_info handler', () => {
    it('should return routing info', async () => {
      const result = await handlers.vtj_get_routing_info({});
      assert.equal(result.success, true);
      assert.ok(result.data.staticRoutes !== undefined);
      assert.ok(result.data.autoRoutes !== undefined);
      assert.ok(result.data.vtjRouterContent !== undefined);
    });
  });

  describe('vtj_add_route handler', () => {
    it('should support dryRun without writing', async () => {
      const result = await handlers.vtj_add_route({
        path: '/new-route',
        name: 'NewRoute',
        componentPath: '@/views/NewRoute.vue',
        dryRun: true
      });
      assert.equal(result.dryRun, true);
    });

    it('should return error for duplicate route', async () => {
      // First add
      await handlers.vtj_add_route({ path: '/dup-test', name: 'Dup', componentPath: '@/views/Dup.vue' });
      // Then add same path again
      const result = await handlers.vtj_add_route({ path: '/dup-test', name: 'Dup2', componentPath: '@/views/Dup2.vue' });
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'ROUTE_DUPLICATE');
    });

    describe('with missing router file', () => {
      let missingFixture;

      before(() => {
        missingFixture = buildFixture();
        rmSync(missingFixture.paths.srcRouter, { force: true });
        configure(missingFixture.root);
      });

      after(() => {
        configure(fixture.root);
        cleanupFixture(missingFixture);
      });

      it('should return ROUTE_FILE_NOT_FOUND error', async () => {
        const result = await handlers.vtj_add_route({
          path: '/missing-router',
          name: 'MissingRouter',
          componentPath: '@/views/MissingRouter.vue'
        });
        assert.equal(result.success, false);
        assert.equal(result.error.code, 'ROUTE_FILE_NOT_FOUND');
      });
    });
  });

  describe('addStaticRoute pure function', () => {
    it('should be a function', () => {
      assert.equal(typeof addStaticRoute, 'function');
    });
  });
});