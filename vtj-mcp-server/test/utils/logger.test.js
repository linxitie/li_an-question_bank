import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import { createErrorResponse, createSuccessResponse, log, info, warn, error } from '../../src/utils/logger.js';

describe('logger', () => {
  describe('createErrorResponse', () => {
    it('should return structured error with code and message', () => {
      const result = createErrorResponse('PAGE_NOT_FOUND', 'Page not found');
      assert.equal(result.success, false);
      assert.equal(result.error.code, 'PAGE_NOT_FOUND');
      assert.equal(result.error.message, 'Page not found');
    });

    it('should include suggestion when provided', () => {
      const result = createErrorResponse('PAGE_NOT_FOUND', 'Not found', { suggestion: 'Check page ID' });
      assert.equal(result.error.suggestion, 'Check page ID');
    });

    it('should include extra fields', () => {
      const result = createErrorResponse('ERR', 'msg', { extra: 'data' });
      assert.equal(result.extra, 'data');
    });
  });

  describe('createSuccessResponse', () => {
    it('should return success with data', () => {
      const result = createSuccessResponse({ id: '123' });
      assert.equal(result.success, true);
      assert.deepEqual(result.data, { id: '123' });
    });
  });

  describe('log', () => {
    it('should log to stderr', () => {
      const spy = mock.method(process.stderr, 'write');
      log('info', 'test message');
      assert.ok(spy.mock.calls.length > 0);
      spy.mock.restore();
    });
  });
});