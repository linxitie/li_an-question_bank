import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { configure, isRawPage } from '../../src/core/file-system.js';
import { syncAdvice } from '../../src/utils/helpers.js';

/**
 * raw 手写页面保护（勘误 2026-10-03）
 *
 * raw 页面由 ContextMode.Raw 直接加载 .vtj/vue/*.vue。对其做 DSL 同步是有损的：
 * 提取器读不到全部手写方法，同步会丢失它们，设计器回存再把丢失部分覆盖回去。
 * 见 CLAUDE.md/vtj.md「修改 .vue 后的同步步骤（勘误 2026-10-03）」。
 *
 * 该保护由三处共同构成，任何一处回退都会导致手写代码被破坏，因此在此锁定：
 *   1. isRawPage()   —— 判定本身，且在未配置时必须安全返回 false
 *   2. syncAdvice()  —— 写完 .vue 后的提示文案不得再劝诱同步
 *   3. syncVueToDSL()—— 实际执行前的硬拦截（由 sync-engine 测试覆盖）
 */
describe('raw page protection', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
    configure(fixture.root);
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('isRawPage', () => {
    it('should return true for a page flagged raw: true', () => {
      assert.equal(isRawPage(fixture.rawPageId), true);
    });

    it('should return false for a generated page', () => {
      assert.equal(isRawPage(fixture.pageIds[1]), false);
    });

    it('should return false for an unknown id', () => {
      assert.equal(isRawPage('nonexistent_id'), false);
    });

    it('should not throw when the project root is not configured', () => {
      // getNextSteps() 在未 configure() 的上下文里也会调用到 isRawPage()
      configure('');
      assert.doesNotThrow(() => isRawPage('anything'));
      assert.equal(isRawPage('anything'), false);
    });
  });

  describe('syncAdvice', () => {
    it('should refuse to advise syncing a raw page', () => {
      configure(fixture.root);
      const advice = syncAdvice(fixture.rawPageId);
      assert.match(advice, /禁止运行 vtj_sync_vue_to_dsl/);
      assert.match(advice, /设计器/);
    });

    it('should advise syncing a generated page', () => {
      configure(fixture.root);
      const advice = syncAdvice(fixture.pageIds[1]);
      assert.match(advice, /可同步/);
      assert.match(advice, /dryRun/);
    });

    it('should not throw when unconfigured', () => {
      configure('');
      assert.doesNotThrow(() => syncAdvice('anything'));
    });
  });
});
