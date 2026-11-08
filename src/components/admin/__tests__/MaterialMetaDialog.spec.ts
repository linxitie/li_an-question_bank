// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

/**
 * C2b「改信息」弹窗：只验"回填 / 提交 / 错误提示"三条主干，
 * 字段语义与范围校验由后端 pytest 覆盖（14 例）。
 */
vi.mock('@/modules/library/api', async (orig) => {
  const actual = await orig<typeof import('@/modules/library/api')>();
  return {
    ...actual,
    fetchMaterialPreview: vi.fn(),
    updateMaterialMeta: vi.fn(),
    uploadMaterialFile: vi.fn(),
    deleteMaterialFile: vi.fn()
  };
});

vi.mock('element-plus', async (orig) => {
  const actual = await orig<typeof import('element-plus')>();
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
    // 默认确认（用例里可改）；返回 Promise 以免组件 .catch 报错
    ElMessageBox: { confirm: vi.fn(async () => 'confirm') }
  };
});

import {
  deleteMaterialFile,
  fetchMaterialPreview,
  updateMaterialMeta,
  uploadMaterialFile,
  type MaterialPreview
} from '@/modules/library/api';
import MaterialMetaDialog from '../MaterialMetaDialog.vue';

function preview(over: Partial<MaterialPreview> = {}): MaterialPreview {
  return {
    id: 125,
    type: 'paper',
    type_label: '试卷',
    title: '2019年北京市公务员考试《公安专业科目》真题',
    summary: null,
    subject: 'gongzhuan',
    subject_label: '公专',
    category: '基础知识',
    status: 1,
    badge: 'GZ-2019-BJ-T',
    difficulty: 1,
    read_time: 0,
    duration: 0,
    view_count: 0,
    study_count: 0,
    publisher: null,
    created_at: null,
    uploaded_at: null,
    content_html: '',
    card: null,
    video: null,
    chapters: [],
    files: [],
    paper: {
      paper_code: 'GZ-2019-BJ-T',
      year: 2019,
      region_name: '北京',
      region_code: 'BJ',
      book_kind_label: '题本',
      volume: null,
      meta_label: '2019 · 北京 · 题本',
      exam_paper_id: 2,
      question_count: 100,
      total_score: 100,
      duration: 120,
      source: { question_count: 'exam', total_score: 'exam', duration: 'exam' },
      override: {},
      paper_type: 'PUBLISHED',
      answerable: true
    },
    ...over
  } as MaterialPreview;
}

const body = () => document.body;

async function mountDialog() {
  const wrapper = mount(MaterialMetaDialog, {
    props: { open: true, materialId: 125, typeLabel: '试卷' },
    attachTo: document.body
  });
  await vi.waitFor(() => {
    expect(body().querySelector('.mmd-grid')).toBeTruthy();
  });
  await nextTick();
  return wrapper;
}

function field(label: string): HTMLInputElement | HTMLSelectElement {
  const blocks = [...body().querySelectorAll('.mmd-field')] as HTMLElement[];
  const hit = blocks.find((b) => b.querySelector('span')?.textContent?.trim() === label);
  if (!hit) throw new Error(`找不到字段 ${label}`);
  return hit.querySelector('input, select') as HTMLInputElement | HTMLSelectElement;
}

function button(text: string): HTMLButtonElement {
  const btn = [...body().querySelectorAll('button')].find((b) => b.textContent?.includes(text));
  if (!btn) throw new Error(`找不到按钮 ${text}`);
  return btn as HTMLButtonElement;
}

afterEach(() => {
  document.body.innerHTML = '';
  vi.mocked(fetchMaterialPreview).mockReset();
  vi.mocked(updateMaterialMeta).mockReset();
  vi.mocked(uploadMaterialFile).mockReset();
  vi.mocked(deleteMaterialFile).mockReset();
});

describe('改信息：回填', () => {
  it('标题/分类/编号回填，题量占位符提示来自可作答卷', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview());
    const wrapper = await mountDialog();

    expect((field('标题') as HTMLInputElement).value).toContain('2019年北京市');
    expect((field('分类（可空）') as HTMLInputElement).value).toBe('基础知识');
    expect((field('编号') as HTMLInputElement).value).toBe('GZ-2019-BJ-T');
    expect((field('题量') as HTMLInputElement).value).toBe('');
    expect((field('题量') as HTMLInputElement).placeholder).toBe('可作答卷：100');
    expect(body().textContent).toContain('已发布，学生可考');
    wrapper.unmount();
  });

  it('只回填人工订正过的值（override）', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(
      preview({
        paper: {
          ...preview().paper!,
          year: 2020,
          override: { year: 2020, question_count: 80 }
        }
      })
    );
    const wrapper = await mountDialog();
    expect((field('年份') as HTMLInputElement).value).toBe('2020');
    expect((field('题量') as HTMLInputElement).value).toBe('80');
    // 没订正过的地区不回填（解析值不该被固化成订正）
    expect((field('地区') as HTMLSelectElement).value).toBe('');
    wrapper.unmount();
  });
});

describe('改信息：提交', () => {
  it('保存时把标题/分类/试卷字段一起提交，成功后发 saved', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview());
    vi.mocked(updateMaterialMeta).mockResolvedValue({
      ok: true,
      changed: ['title', 'question_count'],
      material: { id: 125, title: '新标题', category: '基础知识', paper_code: 'GZ-2019-BJ-T', status: 1, type: 'paper' },
      paper: preview().paper
    });
    const wrapper = await mountDialog();

    (field('标题') as HTMLInputElement).value = '新标题';
    field('标题').dispatchEvent(new Event('input'));
    (field('题量') as HTMLInputElement).value = '80';
    field('题量').dispatchEvent(new Event('input'));
    await nextTick();

    button('保存').click();
    await vi.waitFor(() => {
      expect(vi.mocked(updateMaterialMeta)).toHaveBeenCalledTimes(1);
    });

    const [id, payload] = vi.mocked(updateMaterialMeta).mock.calls[0];
    expect(id).toBe(125);
    expect(payload).toMatchObject({
      title: '新标题',
      category: '基础知识',
      question_count: 80,
      paper_code: 'GZ-2019-BJ-T'
    });
    expect(wrapper.emitted('saved')?.[0]?.[0]).toMatchObject({ id: 125, title: '新标题' });
    wrapper.unmount();
  });

  it('后端 400 时把原因显示在弹窗里，不发 saved', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview());
    vi.mocked(updateMaterialMeta).mockRejectedValue(new Error('year 需在 1990–2100 之间，收到 1800'));
    const wrapper = await mountDialog();

    button('保存').click();
    await vi.waitFor(() => {
      expect(body().querySelector('.mmd-error')?.textContent).toContain('1990–2100');
    });
    expect(wrapper.emitted('saved')).toBeUndefined();
    wrapper.unmount();
  });

  it('非试卷资料不显示试卷字段，也不提交它们', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(
      preview({ type: 'lecture', type_label: '讲义', paper: null })
    );
    vi.mocked(updateMaterialMeta).mockResolvedValue({
      ok: true, changed: [], material: { id: 125, title: 'x', category: null, paper_code: null, status: 0, type: 'lecture' }, paper: null
    });
    const wrapper = await mountDialog();

    const labels = [...body().querySelectorAll('.mmd-field span')].map((s) => s.textContent?.trim());
    expect(labels).not.toContain('年份');
    button('保存').click();
    await vi.waitFor(() => {
      expect(vi.mocked(updateMaterialMeta)).toHaveBeenCalled();
    });
    const payload = vi.mocked(updateMaterialMeta).mock.calls[0][1];
    expect(payload).not.toHaveProperty('year');
    expect(payload).not.toHaveProperty('question_count');
    wrapper.unmount();
  });
});

describe('改信息：补原件', () => {
  it('选文件后带 materialId 上传，成功后重新拉预览', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview());
    vi.mocked(uploadMaterialFile).mockResolvedValue({
      duplicate: false, created: false, material_id: 125, title: 'x'
    });
    const wrapper = await mountDialog();

    const input = body().querySelector('.mmd-file-input') as HTMLInputElement;
    Object.defineProperty(input, 'files', {
      value: [new File([new Uint8Array(16)], '2019北京公专真题.pdf')],
      configurable: true
    });
    input.dispatchEvent(new Event('change'));

    await vi.waitFor(() => {
      expect(vi.mocked(uploadMaterialFile)).toHaveBeenCalledTimes(1);
    });
    const call = vi.mocked(uploadMaterialFile).mock.calls[0][0];
    expect(call.materialId).toBe(125);
    expect(call.type).toBe('paper');
    await vi.waitFor(() => {
      expect(vi.mocked(fetchMaterialPreview)).toHaveBeenCalledTimes(2);
    });
    wrapper.unmount();
  });
});

describe('C1 删除原件', () => {
  const fileItem = {
    file_id: 7,
    file_name: '单独一份试卷·模拟卷.pdf',
    file_ext: 'pdf',
    mime_type: 'application/pdf',
    size: 2850,
    size_label: '3 KB',
    sha256_short: '604cf9d22f6a',
    role: 'primary' as const,
    role_label: '主文件',
    source: 'upload',
    download_url: '/api/materials/files/7/download',
    uploaded_at: '2026-11-08 10:57'
  };

  it('点「删除」→ 二次确认 → 调接口并刷新原件列表', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview({ files: [fileItem] }));
    vi.mocked(deleteMaterialFile).mockResolvedValue({
      ok: true,
      files: [],
      deleted: { physical_deleted: true }
    });
    const wrapper = await mountDialog();

    const del = [...body().querySelectorAll('.mmd-file__del')][0] as HTMLButtonElement;
    expect(del).toBeTruthy();
    del.click();

    await vi.waitFor(() => {
      expect(vi.mocked(deleteMaterialFile)).toHaveBeenCalledWith(125, 7);
    });
    await vi.waitFor(() => {
      expect(body().querySelectorAll('.mmd-file__del')).toHaveLength(0);
    });
    wrapper.unmount();
  });

  it('确认框取消时不调接口', async () => {
    const { ElMessageBox } = await import('element-plus');
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview({ files: [fileItem] }));
    // 真实 Element Plus 在"取消"时是 reject，不是 resolve('cancel')
    vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce(new Error('cancel'));
    const wrapper = await mountDialog();

    (body().querySelector('.mmd-file__del') as HTMLButtonElement).click();
    await new Promise((r) => setTimeout(r, 30));
    expect(vi.mocked(deleteMaterialFile)).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('删除失败时把后端原因提示出来', async () => {
    vi.mocked(fetchMaterialPreview).mockResolvedValue(preview({ files: [fileItem] }));
    vi.mocked(deleteMaterialFile).mockRejectedValue({ message: '原件不存在或不属于该资料' });
    const wrapper = await mountDialog();

    (body().querySelector('.mmd-file__del') as HTMLButtonElement).click();
    const { ElMessage } = await import('element-plus');
    await vi.waitFor(() => {
      expect(vi.mocked(ElMessage.error)).toHaveBeenCalledWith('原件不存在或不属于该资料');
    });
    wrapper.unmount();
  });
});
