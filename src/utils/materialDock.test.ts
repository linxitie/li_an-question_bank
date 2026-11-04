// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
// @ts-expect-error materialDock 是纯 JS 工具，无独立类型声明
import { formatMaterialHtml } from './materialDock';

describe('formatMaterialHtml', () => {
  it('把材料N切成高亮标签并插入分隔线，原文字不丢', function () {
    const html = '<p>材料1 甲内容</p><p>材料2 乙内容</p>';
    const out = formatMaterialHtml(html);
    expect(out.match(/qm-label/g)?.length).toBe(2);
    expect(out.match(/qm-material-sep/g)?.length).toBe(1);
    expect(out).toContain('甲内容');
    expect(out).toContain('乙内容');
    expect(out).toContain('材料1');
    expect(out).toContain('材料2');
  });

  it('没有材料序号时原样返回', function () {
    const html = '<p>普通材料，没有编号</p>';
    expect(formatMaterialHtml(html)).toBe(html);
  });

  it('已格式化过的内容不重复包裹', function () {
    const first = formatMaterialHtml('<p>材料1 甲</p><p>材料2 乙</p>');
    expect(formatMaterialHtml(first)).toBe(first);
  });
});
