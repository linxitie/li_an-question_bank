import { describe, expect, it } from 'vitest';
// @ts-ignore TS7016: richText 为无声明文件的纯 JS 模块（按任务要求只提交四个新文件，不额外落 .d.ts）
import { renderRichText, sanitizeRichText, stripRichText } from './richText';

describe('sanitizeRichText - links (RT-A1)', () => {
  it('keeps href and forces target/rel on external links', () => {
    const html = sanitizeRichText('<a href="https://example.com/a">示例</a>');
    expect(html).toContain('href="https://example.com/a"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('示例');
  });

  it('preserves mailto links', () => {
    const html = sanitizeRichText('<a href="mailto:a@b.com">邮件</a>');
    expect(html).toContain('href="mailto:a@b.com"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it('strips javascript: links but keeps their text', () => {
    const html = sanitizeRichText('<a href="javascript:alert(1)">点我</a>');
    expect(html).not.toContain('javascript:');
    expect(html).not.toContain('<a');
    expect(html).toBe('点我');
  });

  it('strips data:text/html links', () => {
    const html = sanitizeRichText(
      '<a href="data:text/html,<script>alert(1)</script>">x</a>'
    );
    expect(html).not.toContain('data:text/html');
    expect(html).not.toContain('<a');
    expect(html).toBe('x');
  });

  it('blocks entity-obfuscated javascript protocol', () => {
    const html = sanitizeRichText('<a href="java&#115;cript:alert(1)">x</a>');
    expect(html).not.toContain('javascript');
    expect(html).not.toContain('<a');
  });
});

describe('sanitizeRichText - images (RT-A2)', () => {
  it('preserves static image src and adds lazy loading', () => {
    const html = sanitizeRichText('<img src="/static/x.png">');
    expect(html).toContain('src="/static/x.png"');
    expect(html).toContain('loading="lazy"');
  });
});

describe('sanitizeRichText - XSS (RT-A3)', () => {
  it('strips script/iframe tags and event handlers', () => {
    const html = sanitizeRichText(
      '<p>安全</p><script>alert(1)</script><iframe src="https://evil"></iframe>' +
        '<img src="/static/x.png" onerror="alert(1)">'
    );
    expect(html).not.toContain('<script');
    expect(html).not.toContain('<iframe');
    expect(html).not.toContain('onerror');
    expect(html).toContain('<p>安全</p>');
    expect(html).toContain('src="/static/x.png"');
  });

  it('keeps safe semantic tags', () => {
    const input =
      '<table><tbody><tr><td>单元格</td></tr></tbody></table>' +
      '<ul><li>列表</li></ul><p><strong>加粗</strong></p>';
    const html = sanitizeRichText(input);
    expect(html).toContain('<table>');
    expect(html).toContain('<ul>');
    expect(html).toContain('<li>列表</li>');
    expect(html).toContain('<p>');
    expect(html).toContain('<strong>加粗</strong>');
  });
});

describe('sanitizeRichText - plain text', () => {
  it('leaves plain text unchanged', () => {
    const text = '这是一段纯文本，含 1 < 2 与 A&B。';
    expect(sanitizeRichText(text)).toBe(text);
  });

  it('renderRichText delegates to sanitizeRichText', () => {
    const input = '<a href="https://x.test">x</a>';
    expect(renderRichText(input)).toBe(sanitizeRichText(input));
  });
});

describe('stripRichText', () => {
  it('returns plain text for summaries and marks images', () => {
    const text = stripRichText('<p>题干 <strong>重点</strong></p><img src="/static/a.png">');
    expect(text).toBe('题干 重点 [图片]');
    expect(text).not.toContain('<');
  });

  it('decodes entities', () => {
    expect(stripRichText('<p>A&amp;B&nbsp;C</p>')).toBe('A&B C');
  });
});
