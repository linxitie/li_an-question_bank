import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { ERROR_CODES, getSuggestion } from '../../src/utils/error-codes.js';

const EXPECTED_CODES = [
  'PROJECT_NOT_FOUND',
  'PAGE_NOT_FOUND',
  'DSL_FILE_NOT_FOUND',
  'VUE_FILE_NOT_FOUND',
  'MATERIAL_NOT_FOUND',
  'ROUTE_FILE_NOT_FOUND',
  'ROUTE_PARSE_ERROR',
  'ROUTE_DUPLICATE',
  'FILE_WRITE_ERROR',
  'VERSION_MISMATCH',
  'RAW_PAGE_PROTECTED',
  'NODES_NOT_FOUND',
  'EMPTY_TEMPLATE',
  'EMPTY_SCRIPT',
  'BACKUP_FAILED',
  'INVALID_MODE',
  'SECTION_NOT_FOUND'
];

describe('error-codes', () => {
  describe('ERROR_CODES', () => {
    it('should contain all expected error codes', () => {
      for (const code of EXPECTED_CODES) {
        assert.equal(typeof ERROR_CODES[code], 'string', `ERROR_CODES.${code} should be a string`);
        assert.ok(ERROR_CODES[code].length > 0, `ERROR_CODES.${code} should not be empty`);
      }
    });

    it('should have at least 17 error codes', () => {
      assert.ok(Object.keys(ERROR_CODES).length >= 17);
    });
  });

  describe('getSuggestion', () => {
    it('should return a suggestion string for each known error code', () => {
      for (const code of Object.values(ERROR_CODES)) {
        const suggestion = getSuggestion(code);
        assert.equal(typeof suggestion, 'string');
        assert.ok(suggestion.length > 0);
      }
    });

    it('should return empty string for unknown code', () => {
      assert.equal(getSuggestion('UNKNOWN_CODE'), '');
    });
  });
});
