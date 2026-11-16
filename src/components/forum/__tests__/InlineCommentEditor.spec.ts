// @vitest-environment jsdom
/**
 * 评论内联编辑器回填（2026-11-10）：
 * 全屏弹窗挂载时 v-model 已有内容，组件必须把文字与 [[file:]] / [[sticker:]]
 * 按原顺序还原成 DOM，否则全屏输入框看起来是空的。
 */
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import InlineCommentEditor from '../InlineCommentEditor.vue';

function tokenNodes(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.ice-attach');
}

describe('InlineCommentEditor 回填', () => {
  it('挂载时把 modelValue 的文字与附件按顺序还原', () => {
    const wrapper = mount(InlineCommentEditor, {
      props: {
        modelValue: '开头\n[[file:/static/a.png|图.png]]中间[[sticker:/static/s.gif]]结尾'
      }
    });
    const editor = wrapper.find('.ice-editor');
    const html = editor.element.innerHTML;
    expect(html).toContain('开头');
    expect(html).toContain('中间');
    expect(html).toContain('结尾');

    const tokens = tokenNodes(wrapper);
    expect(tokens).toHaveLength(2);
    expect(tokens[0].attributes('data-token')).toBe('[[file:/static/a.png|图.png]]');
    expect(tokens[1].attributes('data-token')).toBe('[[sticker:/static/s.gif]]');

    // 顺序：文件 token 必须出现在「中间」之前，表情 token 出现在「结尾」之前
    expect(html.indexOf('[[file:')).toBeLessThan(html.indexOf('中间'));
    expect(html.indexOf('[[sticker:')).toBeLessThan(html.indexOf('结尾'));
  });

  it('外部 v-model 变更时重绘（模拟打开全屏弹窗）', async () => {
    const wrapper = mount(InlineCommentEditor, { props: { modelValue: '' } });
    expect(wrapper.find('.ice-editor').element.innerHTML).toBe('');

    await wrapper.setProps({
      modelValue: '已经写了一半 \n[[file:/static/doc.pdf|讲义.pdf]]'
    });
    const html = wrapper.find('.ice-editor').element.innerHTML;
    expect(html).toContain('已经写了一半');
    expect(html).toContain('[[file:/static/doc.pdf|讲义.pdf]]');
  });

  it('清空 v-model 时同步清空 DOM', async () => {
    const wrapper = mount(InlineCommentEditor, {
      props: { modelValue: '待清空[[file:/static/x.png|x.png]]' }
    });
    expect(wrapper.findAll('.ice-attach')).toHaveLength(1);
    await wrapper.setProps({ modelValue: '' });
    expect(wrapper.find('.ice-editor').element.innerHTML).toBe('');
  });
});
