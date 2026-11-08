import { describe, expect, it } from 'vitest';
import { errorMessage } from '../apiError';

/**
 * 回归（2026-11-08）：C2b 验收时「保存失败」看不到后端 400 原因。
 * 根因是 `apiClient` 的 rejection 是**普通对象**而不是 Error，`instanceof Error` 永远 false。
 */
describe('errorMessage', () => {
  it('归一化对象（不是 Error）也能取到 message', () => {
    expect(errorMessage({ type: 'validation', message: 'year 需在 1990–2100 之间，收到 1800' }, '保存失败'))
      .toBe('year 需在 1990–2100 之间，收到 1800');
  });

  it('Error 实例走 message', () => {
    expect(errorMessage(new Error('文件超过 20MB 上限'), '上传失败')).toBe('文件超过 20MB 上限');
  });

  it('后端原始错误体 { error: { message } }', () => {
    expect(errorMessage({ error: { code: 'CONFLICT', message: '该文件已导入过' } }, '未知'))
      .toBe('该文件已导入过');
  });

  it('details.detail 兜底', () => {
    expect(errorMessage({ message: '', details: { detail: '编号冲突' } }, '未知')).toBe('编号冲突');
  });

  it('字符串直传', () => {
    expect(errorMessage(' 网络异常 ', '未知')).toBe('网络异常');
  });

  it('都没有时用兜底文案', () => {
    expect(errorMessage(null, '保存失败')).toBe('保存失败');
    expect(errorMessage({}, '保存失败')).toBe('保存失败');
    expect(errorMessage({ message: '   ' }, '保存失败')).toBe('保存失败');
  });
});
