import { describe, expect, it } from 'vitest';

import {
  buildMaterialPayload,
  editorBlocks,
  emptyForm,
  validateEditor,
  type EditorForm
} from '../materialEditor';

function form(over: Partial<EditorForm> = {}): EditorForm {
  return { ...emptyForm('gongzhuan'), title: '标题', ...over };
}

describe('editorBlocks', () => {
  it('卡片只显示卡片块，其余显示富文本块', () => {
    expect(editorBlocks('card')).toEqual({ richText: false, card: true });
    expect(editorBlocks('article')).toEqual({ richText: true, card: false });
    expect(editorBlocks('lecture')).toEqual({ richText: true, card: false });
  });
});

describe('validateEditor', () => {
  it('标题必填；新建时科目必选', () => {
    expect(validateEditor(form({ title: '   ' }))).toContain('标题必填');
  });

  it('卡片正面必填且不超过 120 字', () => {
    const errs = validateEditor(form({ type: 'card', cardFront: '' }));
    expect(errs).toContain('卡片正面必填');
    const long = validateEditor(form({ type: 'card', cardFront: '字'.repeat(121) }));
    expect(long.some((e) => e.includes('120'))).toBe(true);
  });

  it('文章正文不能是空壳 HTML', () => {
    expect(validateEditor(form({ type: 'article', content: '<p><br></p>' })))
      .toContain('正文不能为空（富文本里至少要有一段文字）');
    expect(validateEditor(form({ type: 'article', content: '<p>有内容</p>' }))).toEqual([]);
  });
});

describe('buildMaterialPayload', () => {
  it('文章：带 content/summary，绝不带卡片三列', () => {
    const p = buildMaterialPayload(
      form({ type: 'article', content: '<p>正文</p>', summary: '摘要', cardFront: '不该出现' })
    );
    expect(p).toEqual({
      title: '标题',
      subject: 'gongzhuan',
      type: 'article',
      content: '<p>正文</p>',
      summary: '摘要'
    });
    expect(p.card_front).toBeUndefined();
  });

  it('卡片：只带正/背/封面，绝不带 content/summary', () => {
    const p = buildMaterialPayload(
      form({
        type: 'card',
        cardFront: '传唤对象',
        cardBack: '犯罪嫌疑人等',
        cover: 'https://x/1.png',
        content: '<p>残留</p>',
        summary: '残留摘要'
      })
    );
    expect(p).toEqual({
      title: '标题',
      subject: 'gongzhuan',
      type: 'card',
      card_front: '传唤对象',
      card_back: '犯罪嫌疑人等',
      cover_image: 'https://x/1.png'
    });
  });

  it('编辑：不带 subject / type（避免顺手改类型）', () => {
    const p = buildMaterialPayload(form({ type: 'lecture', content: '<p>x</p>' }), 'edit');
    expect(p.subject).toBeUndefined();
    expect(p.type).toBeUndefined();
    expect(p.title).toBe('标题');
  });

  it('空的摘要/分类/封面/标记一律不提交', () => {
    const p = buildMaterialPayload(form({ type: 'article', content: '<p>x</p>', summary: '  ', category: '', badge: '' }));
    expect(p.summary).toBeUndefined();
    expect(p.category).toBeUndefined();
    expect(p.badge).toBeUndefined();
  });
});
