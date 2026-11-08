// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';

/**
 * B2 批量导入对话框：只验"选文件 → 编排 → 队列跑完 → 汇总"这条主干，
 * 具体上传成败由 `uploadMaterialFile` 的 mock 控制（真实 HTTP 在 pytest 里覆盖）。
 */
vi.mock('@/modules/library/api', async (orig) => {
  const actual = await orig<typeof import('@/modules/library/api')>();
  return { ...actual, uploadMaterialFile: vi.fn() };
});

import { uploadMaterialFile } from '@/modules/library/api';
import MaterialBatchUpload from '../MaterialBatchUpload.vue';

function pickFiles(input: HTMLInputElement, files: File[]): void {
  Object.defineProperty(input, 'files', { value: files, configurable: true });
  input.dispatchEvent(new Event('change'));
}

function mkFile(name: string, size = 1024): File {
  return new File([new Uint8Array(size)], name, { type: 'application/octet-stream' });
}

function mountDialog(props: Record<string, unknown> = {}) {
  return mount(MaterialBatchUpload, { props: { open: true, ...props }, attachTo: document.body });
}

const body = () => document.body;

afterEach(() => {
  document.body.innerHTML = '';
  vi.mocked(uploadMaterialFile).mockReset();
});

describe('批量导入：编排展示', () => {
  it('同名 docx+pdf 显示为「合并 1 条」并汇总条数', async () => {
    const wrapper = mountDialog();
    const input = body().querySelector('.mbu-file') as HTMLInputElement;
    pickFiles(input, [mkFile('2024 国考.docx'), mkFile('2024 国考.pdf'), mkFile('另一份讲义.docx')]);
    await nextTick();

    const kinds = [...body().querySelectorAll('.mbu-group__kind')].map((e) => e.textContent?.trim());
    expect(kinds).toEqual(['合并 1 条', '1 条']);
    expect(body().querySelector('.mbu-summary')?.textContent).toContain('将创建 2 条资料');
    wrapper.unmount();
  });

  it('有非法扩展名时禁用「开始导入」并给出原因', async () => {
    const wrapper = mountDialog();
    const input = body().querySelector('.mbu-file') as HTMLInputElement;
    pickFiles(input, [mkFile('a.docx'), mkFile('b.zip')]);
    await nextTick();

    const startBtn = [...body().querySelectorAll('button')].find((b) =>
      b.textContent?.includes('开始导入')
    ) as HTMLButtonElement;
    expect(startBtn.disabled).toBe(true);
    expect(body().querySelector('.mbu-issues')?.textContent).toContain('格式不支持');
    wrapper.unmount();
  });
});

describe('批量导入：队列执行', () => {
  it('配对组先传主文件再挂附件，成功后汇总', async () => {
    vi.mocked(uploadMaterialFile).mockImplementation(async (p) => {
      if (p.materialId != null) {
        return { duplicate: false, created: false, material_id: p.materialId, title: 'x' };
      }
      return { duplicate: false, created: true, material_id: 501, title: 'x' };
    });

    const wrapper = mountDialog();
    const input = body().querySelector('.mbu-file') as HTMLInputElement;
    pickFiles(input, [mkFile('合并讲义.docx', 2048), mkFile('合并讲义.pdf', 1024)]);
    await nextTick();

    const startBtn = [...body().querySelectorAll('button')].find((b) =>
      b.textContent?.includes('开始导入')
    ) as HTMLButtonElement;
    expect(startBtn.disabled).toBe(false);
    startBtn.click();

    await vi.waitFor(() => {
      expect(body().querySelector('.mbu-row')?.className).toContain('is-ok');
    });

    const calls = vi.mocked(uploadMaterialFile).mock.calls;
    expect(calls).toHaveLength(2);
    expect(calls[0][0].file.name).toBe('合并讲义.docx');
    expect(calls[0][0].materialId).toBeUndefined();
    expect(calls[1][0].file.name).toBe('合并讲义.pdf');
    expect(calls[1][0].materialId).toBe(501);

    expect(wrapper.emitted('done')?.[0]?.[0]).toEqual({ created: 1, skipped: 0, failed: 0 });
    wrapper.unmount();
  });

  it('后端判重复时标「重复」并计入 skipped，不发第二次请求', async () => {
    vi.mocked(uploadMaterialFile).mockResolvedValue({
      duplicate: true, created: false, material_id: 88, title: '老资料', existing_file_id: 3
    });

    const wrapper = mountDialog();
    const input = body().querySelector('.mbu-file') as HTMLInputElement;
    pickFiles(input, [mkFile('重复讲义.docx')]);
    await nextTick();
    [...body().querySelectorAll('button')]
      .find((b) => b.textContent?.includes('开始导入'))!
      .click();

    await vi.waitFor(() => {
      expect(body().querySelector('.mbu-row')?.className).toContain('is-duplicate');
    });
    expect(vi.mocked(uploadMaterialFile)).toHaveBeenCalledTimes(1);
    expect(wrapper.emitted('done')?.[0]?.[0]).toEqual({ created: 0, skipped: 1, failed: 0 });
    wrapper.unmount();
  });

  it('单条失败不影响后续条目，并显示失败原因', async () => {
    vi.mocked(uploadMaterialFile)
      .mockRejectedValueOnce(new Error('文件超过 20MB 上限'))
      .mockResolvedValueOnce({ duplicate: false, created: true, material_id: 600, title: 'b' });

    const wrapper = mountDialog();
    const input = body().querySelector('.mbu-file') as HTMLInputElement;
    pickFiles(input, [mkFile('坏文件.docx'), mkFile('好文件.docx')]);
    await nextTick();
    [...body().querySelectorAll('button')]
      .find((b) => b.textContent?.includes('开始导入'))!
      .click();

    await vi.waitFor(() => {
      const rows = [...body().querySelectorAll('.mbu-row')];
      expect(rows[1]?.className).toContain('is-ok');
    });
    const rows = [...body().querySelectorAll('.mbu-row')];
    expect(rows[0].className).toContain('is-failed');
    expect(rows[0].textContent).toContain('超过 20MB');
    expect(wrapper.emitted('done')?.[0]?.[0]).toEqual({ created: 1, skipped: 0, failed: 1 });
    wrapper.unmount();
  });
});
