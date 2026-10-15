/**
 * 日志与结构化响应封装模块
 */

import { getSuggestion } from './error-codes.js';

/**
 * 构造结构化错误响应
 * @param {string} code 错误码
 * @param {string} message 错误信息
 * @param {object} [extra] 附加字段（可包含 suggestion 覆盖默认建议）
 * @returns {{success: boolean, error: {code: string, message: string, suggestion: string}, [key: string]: any}}
 */
export function createErrorResponse(code, message, extra = {}) {
  const suggestion = extra.suggestion || getSuggestion(code);
  return {
    success: false,
    error: { code, message, suggestion },
    ...extra
  };
}

/**
 * 构造结构化成功响应
 * @param {any} data 返回数据
 * @returns {{success: boolean, data: any}}
 */
export function createSuccessResponse(data) {
  return { success: true, data };
}

/**
 * 按级别输出日志到 stderr
 * @param {string} level 日志级别
 * @param {...any} args 日志内容
 */
export function log(level, ...args) {
  const timestamp = new Date().toISOString();
  process.stderr.write(`[${timestamp}] [${level}] ${args.join(' ')}\n`);
}

/** 输出 info 级别日志 */
export function info(...args) {
  log('info', ...args);
}

/** 输出 warn 级别日志 */
export function warn(...args) {
  log('warn', ...args);
}

/** 输出 error 级别日志 */
export function error(...args) {
  log('error', ...args);
}