import { describe, expect, it } from 'vitest';
import {
  injectedMaterialTypes,
  shouldInjectAdminMaterialTypes
} from '../adminMaterialTypes';
import {
  MATERIAL_TYPES,
  isDualFormatMaterialType,
  isKnownMaterialType,
  isVideoMaterialType,
  materialTypeLabel
} from '@/modules/library/materialTypes';

/**
 * A1（资料管理 v3.1）：类型登记表 + 管理页注入条件。
 *
 * 断言两件事：
 * ① 6 类齐全且与后端 TYPES 同集（新增/改名只改登记表）；
 * ② 注入只在 `#/admin/materials` + admin 角色下发生，别把管理页的东西漏到学生端。
 */
describe('MATERIAL_TYPES 登记表', () => {
  it('6 类齐全且顺序稳定', () => {
    expect(MATERIAL_TYPES.map((t) => t.key)).toEqual([
      'video_intro',
      'video_advanced',
      'article',
      'card',
      'lecture',
      'paper'
    ]);
  });

  it('key 不重复、中文名非空', () => {
    const keys = MATERIAL_TYPES.map((t) => t.key);
    expect(new Set(keys).size).toBe(keys.length);
    for (const t of MATERIAL_TYPES) expect(t.label.trim().length).toBeGreaterThan(0);
  });

  it('中文名与既有页面文案一致（知识卡片，不是"卡片"）', () => {
    expect(materialTypeLabel('card')).toBe('知识卡片');
    expect(materialTypeLabel('lecture')).toBe('讲义');
    expect(materialTypeLabel('paper')).toBe('试卷');
  });

  it('未知 / 空 key：原样返回空串，不抛错', () => {
    expect(materialTypeLabel('unknown')).toBe('unknown');
    expect(materialTypeLabel(null)).toBe('');
    expect(materialTypeLabel(undefined)).toBe('');
  });

  it('合法类型判定与后端白名单同集', () => {
    for (const k of ['video_intro', 'video_advanced', 'article', 'card', 'lecture', 'paper']) {
      expect(isKnownMaterialType(k)).toBe(true);
    }
    expect(isKnownMaterialType('pdf')).toBe(false);
    expect(isKnownMaterialType('')).toBe(false);
  });

  it('视频类 / 双格式类标记正确', () => {
    expect(isVideoMaterialType('video_intro')).toBe(true);
    expect(isVideoMaterialType('video_advanced')).toBe(true);
    expect(isVideoMaterialType('lecture')).toBe(false);
    expect(isDualFormatMaterialType('lecture')).toBe(true);
    expect(isDualFormatMaterialType('paper')).toBe(true);
    expect(isDualFormatMaterialType('card')).toBe(false);
  });
});

describe('injectedMaterialTypes', () => {
  it('只返回新增的讲义与试卷，且顺序与登记表一致', () => {
    expect(injectedMaterialTypes().map((t) => t.key)).toEqual(['lecture', 'paper']);
    expect(injectedMaterialTypes().map((t) => t.label)).toEqual(['讲义', '试卷']);
  });
});

describe('shouldInjectAdminMaterialTypes', () => {
  it('管理页注入', () => {
    expect(
      shouldInjectAdminMaterialTypes({ hash: '#/admin/materials', role: 'admin' })
    ).toBe(true);
  });

  it('带查询参数 / 子路径也注入', () => {
    expect(
      shouldInjectAdminMaterialTypes({ hash: '#/admin/materials?type=paper', role: 'admin' })
    ).toBe(true);
    expect(
      shouldInjectAdminMaterialTypes({ hash: '#/admin/materials/detail', role: 'admin' })
    ).toBe(true);
  });

  it('非管理员不注入（教师 / 学生 / 空角色 / 游客）', () => {
    for (const role of ['teacher', 'student', '', 'guest']) {
      expect(shouldInjectAdminMaterialTypes({ hash: '#/admin/materials', role })).toBe(false);
    }
  });

  it('其它页面不注入', () => {
    for (const hash of [
      '#/materials/xingce',
      '#/admin/users',
      '#/admin',
      '#/home',
      ''
    ]) {
      expect(shouldInjectAdminMaterialTypes({ hash, role: 'admin' })).toBe(false);
    }
  });
});
