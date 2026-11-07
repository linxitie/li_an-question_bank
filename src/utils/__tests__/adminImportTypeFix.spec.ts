// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  applyImportTypeFix,
  LECTURE_OPTION,
  findTypeSelect,
  forceLectureOnce,
  injectLectureOption,
  localizeTypeTags,
  resolveRole,
  shouldInjectImportTypeFix
} from '../adminImportTypeFix';

/**
 * B3 前端一半：旧版导入向导里「文档类型」下拉必须能选到「作为讲义」，且默认就是它。
 * 用 jsdom 复刻旧页 `.meta-form` 的真实结构（只有 `<option value="article">作为文章</option>`）。
 */
function mountWizardHtml(): void {
  document.body.innerHTML = `
    <div class="imp-dlg">
      <div class="meta-form">
        <select id="impSubject"><option value="xingce">入行测</option></select>
        <select id="impType"><option value="article">作为文章</option></select>
        <input id="impCategory" />
      </div>
    </div>`;
}

describe('shouldInjectImportTypeFix', () => {
  it('只在旧版资料页 + 管理员时注入', () => {
    expect(shouldInjectImportTypeFix({ hash: '#/admin/materials/legacy', role: 'admin' })).toBe(true);
    expect(shouldInjectImportTypeFix({ hash: '#/admin/materials/legacy?x=1', role: 'admin' })).toBe(true);
  });

  it('新页 / 其他角色 / 其他页都不注入', () => {
    expect(shouldInjectImportTypeFix({ hash: '#/admin/materials', role: 'admin' })).toBe(false);
    expect(shouldInjectImportTypeFix({ hash: '#/admin/materials/legacy', role: 'teacher' })).toBe(false);
    expect(shouldInjectImportTypeFix({ hash: '#/admin/logs', role: 'admin' })).toBe(false);
  });
});

describe('resolveRole（角色来源）', () => {
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__VTJ_AUTH__;
    localStorage.clear();
  });

  it('优先用 __VTJ_AUTH__.getUserRole()（localStorage 里常常没有 role）', () => {
    (window as unknown as Record<string, unknown>).__VTJ_AUTH__ = { getUserRole: () => 'admin' };
    expect(resolveRole(window)).toBe('admin');
  });

  it('认证模块缺失时回退 localStorage', () => {
    localStorage.setItem('__VTJ_AUTH_STATE__', JSON.stringify({ role: 'teacher' }));
    expect(resolveRole(window)).toBe('teacher');
  });

  it('两边都没有 → 空串（不注入）', () => {
    expect(resolveRole(window)).toBe('');
  });

  it('认证模块抛错不影响兜底', () => {
    (window as unknown as Record<string, unknown>).__VTJ_AUTH__ = {
      getUserRole: () => {
        throw new Error('boom');
      }
    };
    localStorage.setItem('__VTJ_AUTH_STATE__', JSON.stringify({ userInfo: { role: 'admin' } }));
    expect(resolveRole(window)).toBe('admin');
  });
});

describe('注入「作为讲义」选项', () => {
  beforeEach(mountWizardHtml);
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('找到文档类型下拉并补入选项（幂等）', () => {
    const select = findTypeSelect(document)!;
    expect(select.id).toBe('impType');

    expect(injectLectureOption(document, select)).toBe(true);
    expect(injectLectureOption(document, select)).toBe(false);

    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(['article', LECTURE_OPTION.value]);
    expect(select.options[1].textContent).toBe('作为讲义');
  });

  it('把默认值从 article 改成 lecture，并触发 change 让 v-model 回写', () => {
    const select = findTypeSelect(document)!;
    let changed = 0;
    select.addEventListener('change', () => { changed += 1; });

    injectLectureOption(document, select);
    expect(forceLectureOnce(select)).toBe(true);
    expect(select.value).toBe('lecture');
    expect(changed).toBe(1);

    // 只强制一次：之后再跑不会覆盖管理员手选
    select.value = 'article';
    expect(forceLectureOnce(select)).toBe(false);
    expect(select.value).toBe('article');
  });

  it('管理员已经选了别的值时不动他', () => {
    const select = findTypeSelect(document)!;
    injectLectureOption(document, select);
    select.value = 'article';
    select.setAttribute('data-b3-forced', '1');   // 模拟已强制过一次
    expect(forceLectureOnce(select)).toBe(false);
    expect(select.value).toBe('article');
  });

  it('xlsx 卡片流（无 article 选项）不注入也不改值', () => {
    document.body.innerHTML = `
      <div class="meta-form">
        <select id="impTypeCard"><option value="card">作为卡片</option></select>
      </div>`;
    // 没有 article 选项 → 找不到"文档类型"下拉
    expect(findTypeSelect(document)).toBeNull();
    expect(applyImportTypeFix(document)).toEqual({ injected: false, forced: false });
    expect(document.querySelector('#impTypeCard')!.querySelectorAll('option').length).toBe(1);
  });

  it('applyImportTypeFix 一次完成注入 + 纠默认值', () => {
    expect(applyImportTypeFix(document)).toEqual({ injected: true, forced: true });
    const select = document.querySelector<HTMLSelectElement>('#impType')!;
    expect(select.value).toBe('lecture');
  });

  it('页面上没有向导时不报错', () => {
    document.body.innerHTML = '<div class="adm-page"></div>';
    expect(applyImportTypeFix(document)).toEqual({ injected: false, forced: false });
  });
});

describe('旧页类型徽标中文化', () => {
  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('lecture / paper 显示成「讲义 / 试卷」', () => {
    document.body.innerHTML = `
      <table><tbody>
        <tr><td><b>某个讲义</b><span class="type-tag">lecture</span></td></tr>
        <tr><td><b>某套卷</b><span class="type-tag">paper</span></td></tr>
        <tr><td><b>老卡片</b><span class="type-tag">知识卡片</span></td></tr>
      </tbody></table>`;
    expect(localizeTypeTags(document)).toBe(2);
    const texts = Array.from(document.querySelectorAll('.type-tag')).map((e) => e.textContent);
    expect(texts).toEqual(['讲义', '试卷', '知识卡片']);
  });

  it('标题里的同名单词不受影响', () => {
    document.body.innerHTML = `<div class="t-title"><b>lecture 笔记</b><span class="type-tag">lecture</span></div>`;
    localizeTypeTags(document);
    expect(document.querySelector('.t-title b')!.textContent).toBe('lecture 笔记');
    expect(document.querySelector('.type-tag')!.textContent).toBe('讲义');
  });
});
