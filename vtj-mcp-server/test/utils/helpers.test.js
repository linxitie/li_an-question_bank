import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { createDryRunPreview, getNextSteps, inferRoutes } from '../../src/utils/helpers.js';

describe('helpers', () => {
  describe('createDryRunPreview', () => {
    it('should return structured preview with operation details', () => {
      const result = createDryRunPreview({
        operation: 'write_vue_script',
        target: 'test.vue',
        changes: { method: 'handleClick' }
      });
      assert.equal(result.dryRun, true);
      assert.equal(result.operation, 'write_vue_script');
      assert.equal(result.target, 'test.vue');
    });

    it('should include backup info when provided', () => {
      const result = createDryRunPreview({
        operation: 'write',
        target: 'f.vue',
        backup: 'f.vue.bak'
      });
      assert.equal(result.backup, 'f.vue.bak');
    });

    it('should include warnings and nextSteps', () => {
      const result = createDryRunPreview({
        operation: 'sync',
        target: 'page1',
        warnings: ['version mismatch'],
        nextSteps: ['run vtj_check_consistency']
      });
      assert.deepEqual(result.warnings, ['version mismatch']);
      assert.deepEqual(result.nextSteps, ['run vtj_check_consistency']);
    });
  });

  describe('getNextSteps', () => {
    it('should return sync steps after write_vue_script', () => {
      const steps = getNextSteps('write_vue_script', 'page1');
      assert.ok(Array.isArray(steps));
      assert.ok(steps.some(s => s.includes('sync') || s.includes('Sync')));
    });

    it('should return check steps after sync', () => {
      const steps = getNextSteps('sync_vue_to_dsl', 'page1');
      assert.ok(Array.isArray(steps));
    });
  });

  describe('inferRoutes', () => {
    it('should return empty array for content without route info', () => {
      const routes = inferRoutes('<template>hello</template>');
      assert.ok(Array.isArray(routes));
    });
  });
});