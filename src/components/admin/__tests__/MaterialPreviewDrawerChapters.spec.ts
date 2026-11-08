// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

/**
 * C1（2026-11-08）：抽屉的讲义目录 + 元信息里的字数。
 * 删除原件的交互放在 `MaterialMetaDialog` 的用例里（那里才是入口）。
 */
vi.mock('element-plus', async (orig) => {
  const actual = await orig<typeof import('element-plus')>();
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
    ElMessageBox: { confirm: vi.fn() }
  };
});

import MaterialPreviewDrawer from '../MaterialPreviewDrawer.vue';
import type { MaterialPreview } from '@/modules/library/api';

function base(over: Partial<MaterialPreview> = {}): MaterialPreview {
  return {
    id: 121,
    type: 'lecture',
    type_label: '讲义',
    title: '04_讲义_正常',
    summary: null,
    subject: 'gongzhuan',
    subject_label: '公专',
    category: null,
    status: 0,
    badge: null,
    difficulty: 1,
    read_time: 0,
    duration: 0,
    view_count: 0,
    study_count: 0,
    publisher: null,
    created_at: null,
    uploaded_at: null,
    content_html: '<p>正文</p>',
    card: null,
    video: null,
    chapters: [],
    doc: { word_count: null, word_count_label: '—', chapter_count: 0 },
    files: [],
    paper: null,
    ...over
  } as MaterialPreview;
}

const body = () => document.body;

function mountDrawer(preview: MaterialPreview) {
  return mount(MaterialPreviewDrawer, {
    props: { open: true, preview },
    attachTo: document.body
  });
}

beforeEach(() => {
  document.body.innerHTML = '';
});

afterEach(() => {
  document.body.innerHTML = '';
});

describe('C1 讲义目录', () => {
  it('章节按层级渲染，一级加粗、二级缩进；标签显示章节数与字数', async () => {
    const wrapper = mountDrawer(
      base({
        chapters: [
          { level: 1, title: '第一章 治安管理处罚法' },
          { level: 2, title: '1.1 传唤' },
          { level: 2, title: '1.2 询问查证' }
        ],
        doc: { word_count: 12000, word_count_label: '1.2 万字', chapter_count: 3 }
      })
    );
    await nextTick();

    const label = [...body().querySelectorAll('.mpd-block__label')]
      .map((e) => e.textContent?.replace(/\s+/g, ' ').trim());
    expect(label.some((t) => t?.includes('章节（3）'))).toBe(true);

    const items = [...body().querySelectorAll('.mpd-toc li')];
    expect(items).toHaveLength(3);
    expect(items[0].className).toContain('is-lv1');
    expect(items[1].className).toContain('is-lv2');
    expect(items[1].textContent).toContain('1.1 传唤');
    // 元信息行显示字数
    expect(body().textContent).toContain('1.2 万字');
    wrapper.unmount();
  });

  it('没有章节时不渲染目录区（PDF / 老资料）', async () => {
    const wrapper = mountDrawer(base());
    await nextTick();
    expect(body().querySelector('.mpd-toc')).toBeNull();
    wrapper.unmount();
  });
});
