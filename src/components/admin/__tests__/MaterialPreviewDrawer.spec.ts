// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import MaterialPreviewDrawer from '../MaterialPreviewDrawer.vue';
import type { MaterialPreview } from '@/modules/library/api';

/**
 * A3 预览抽屉的渲染契约。
 *
 * 组件用 `<Teleport to="body">` 挂载，所以断言一律查 `document.body`（而不是 wrapper.find）。
 * 只测"类型分支对不对 / 关闭事件发没发"，像素交给 `/admin/dev/style` 走查。
 */
function base(over: Partial<MaterialPreview> = {}): MaterialPreview {
  return {
    id: 115,
    type: 'card',
    type_label: '知识卡片',
    title: '继续盘问的适用对象？',
    summary: null,
    subject: 'gongzhuan',
    subject_label: '公专',
    category: '基础知识',
    status: 0,
    badge: null,
    difficulty: 1,
    read_time: 2,
    duration: 0,
    view_count: 12,
    study_count: 0,
    publisher: { id: 2, name: 'cbrycc', role: 'admin', role_label: '管理员' },
    created_at: '2026-11-05T21:12:37+08:00',
    uploaded_at: null,
    content_html: null,
    card: { front: '继续盘问的适用对象？', back: '四类人员', images: [] },
    video: null,
    chapters: [],
    files: [],
    paper: null,
    ...over
  };
}

const body = () => document.body;

function mountDrawer(props: Record<string, unknown>) {
  return mount(MaterialPreviewDrawer, { props: { open: true, ...props }, attachTo: document.body });
}

describe('MaterialPreviewDrawer', () => {
  it('关闭时什么都不渲染', () => {
    mount(MaterialPreviewDrawer, { props: { open: false }, attachTo: document.body });
    expect(body().querySelector('.mpd-panel')).toBeNull();
  });

  it('头部：标题 / 类型徽标 / 科目 / 分类 / 上下架状态', () => {
    const w = mountDrawer({ preview: base() });
    const text = body().textContent || '';
    expect(body().querySelector('.mpd-title')?.textContent).toBe('继续盘问的适用对象？');
    expect(text).toContain('知识卡片');
    expect(text).toContain('公专');
    expect(text).toContain('基础知识');
    expect(text).toContain('未上架'); // status=0
    w.unmount();
  });

  it('元信息：发布者带角色、时间格式化成 yyyy-MM-dd HH:mm', () => {
    const w = mountDrawer({ preview: base() });
    const text = body().textContent || '';
    expect(text).toContain('cbrycc（管理员）');
    expect(text).toContain('2026-11-05 21:12');
    expect(text).not.toContain('T21:12:37'); // 没有裸 ISO
    w.unmount();
  });

  it('卡片：正面 / 背面 / 配图', () => {
    const w = mountDrawer({
      preview: base({ card: { front: '正面内容', back: '背面内容', images: ['/u/a.png', '/u/b.png'] } })
    });
    const faces = Array.from(body().querySelectorAll('.mpd-face')).map((el) => el.textContent);
    expect(faces).toEqual(['正面内容', '背面内容']);
    expect(body().querySelectorAll('.mpd-imgs img').length).toBe(2);
    w.unmount();
  });

  it('文章：渲染正文 HTML（服务端已 sanitize），不渲染卡片块', () => {
    const w = mountDrawer({
      preview: base({ type: 'article', type_label: '文章', card: null, content_html: '<p>四步法</p>' })
    });
    expect(body().querySelector('.mpd-html')?.innerHTML).toContain('四步法');
    expect(body().querySelector('.mpd-face')).toBeNull();
    w.unmount();
  });

  it('视频：有 url 出 video 标签；无 url 给空态', () => {
    const a = mountDrawer({
      preview: base({ type: 'video_intro', type_label: '入门视频', card: null, video: { url: '/api/video/7/stream' } })
    });
    expect(body().querySelector('.mpd-video')?.getAttribute('src')).toBe('/api/video/7/stream');
    a.unmount();

    const b = mountDrawer({
      preview: base({ type: 'video_intro', type_label: '入门视频', card: null, video: { url: '' } })
    });
    expect((body().textContent || '')).toContain('未绑定视频文件');
    b.unmount();
  });

  it('无任何内容时给空态（不白屏）', () => {
    const w = mountDrawer({
      preview: base({ type: 'lecture', type_label: '讲义', card: null, content_html: null })
    });
    expect((body().textContent || '')).toContain('该类型暂无预览内容');
    w.unmount();
  });

  it('loading / error 优先于内容', () => {
    const a = mountDrawer({ preview: null, loading: true });
    expect((body().textContent || '')).toContain('加载中');
    a.unmount();

    const b = mountDrawer({ preview: null, error: '资料不存在' });
    expect(body().querySelector('.mpd-error')?.textContent).toBe('资料不存在');
    b.unmount();
  });

  it('点关闭按钮 / 点遮罩 / 按 ESC 都会 emit close', async () => {
    const w = mountDrawer({ preview: base() });
    (body().querySelector('.mpd-x') as HTMLElement).click();
    (body().querySelector('.mpd-mask') as HTMLElement).click();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await w.vm.$nextTick();
    expect(w.emitted('close')?.length).toBe(3);
    w.unmount();
  });

  it('后续批次字段为空时不渲染章节/原件块（契约稳定、UI 不空转）', () => {
    const w = mountDrawer({ preview: base() });
    const labels = Array.from(body().querySelectorAll('.mpd-block__label')).map((el) => el.textContent);
    expect(labels).not.toContain('章节');
    expect(labels).not.toContain('原件');
    w.unmount();
  });
});

// 让 vi 参与编译期检查（本文件未直接使用 mock，但保持与其他 spec 一致的导入风格）
void vi;
