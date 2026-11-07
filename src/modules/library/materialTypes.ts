/**
 * 备考资料类型登记表（资料管理 v3.1 · 裁定 D29）
 *
 * **单一真源**：与后端 `backend/app/api/v1/library/materials.py` 的 `TYPES` 白名单一一对应（6 类）。
 * 2026-11-06 新增 `lecture`（讲义）/ `paper`（试卷）——零迁移：`study_material.type` 仍是 String(20)，
 * 只在这张表和前端映射里出现，存量 119 行不受影响。
 *
 * 使用方：管理端类型下拉（A1 由 `@/utils/adminMaterialTypes` 注入；A4 手写页直接渲染）、
 * 列表类型徽标、统计卡文案。**新增类型只改这里 + 后端白名单两处**，避免像 v3 之前那样
 * 三处文案（下拉「知识卡片」/徽标「卡片」/统计「卡片」）各写各的。
 */
import type { LibraryMaterialType } from './api';

export interface MaterialTypeMeta {
  /** 存库值（= 后端 TYPES 成员） */
  key: LibraryMaterialType;
  /** 中文名：下拉、徽标、统计卡统一用它 */
  label: string;
  /** 徽标文字色 */
  color: string;
  /** 徽标底色 */
  bg: string;
  /** 视频类：表单要填 video_id */
  video?: boolean;
  /** 双格式类：一条资料可同时挂 pdf + docx（`material_file`），主文件优先 docx */
  dualFormat?: boolean;
}

export const MATERIAL_TYPES: readonly MaterialTypeMeta[] = [
  { key: 'video_intro', label: '入门视频', color: '#4a5266', bg: '#eef1f6', video: true },
  { key: 'video_advanced', label: '进阶视频', color: '#4a5266', bg: '#eef1f6', video: true },
  { key: 'article', label: '文章', color: '#2f49c4', bg: '#e8efff' },
  { key: 'card', label: '知识卡片', color: '#6b3fbf', bg: '#f3ecff' },
  { key: 'lecture', label: '讲义', color: '#0f7a86', bg: '#e6f7f9', dualFormat: true },
  { key: 'paper', label: '试卷', color: '#b35309', bg: '#fff2e3', dualFormat: true }
];

/** key → 中文名（未知 key 不在表内，由 materialTypeLabel 兜底原样返回） */
export const MATERIAL_TYPE_LABEL: Readonly<Record<string, string>> = MATERIAL_TYPES.reduce(
  (acc, t) => {
    acc[t.key] = t.label;
    return acc;
  },
  {} as Record<string, string>
);

/** 中文名；未登记的 key 原样返回（不吞掉脏数据，便于排查） */
export function materialTypeLabel(key?: string | null): string {
  if (!key) return '';
  return MATERIAL_TYPE_LABEL[key] || key;
}

/** 是否登记在册的合法类型（与后端 TYPES 同集） */
export function isKnownMaterialType(key?: string | null): boolean {
  return !!key && Object.prototype.hasOwnProperty.call(MATERIAL_TYPE_LABEL, key);
}

/** 视频类（决定表单是否要求 video_id） */
export function isVideoMaterialType(key?: string | null): boolean {
  return MATERIAL_TYPES.some((t) => t.key === key && t.video);
}

/** 双格式类（讲义 / 试卷：可挂 pdf + docx 两份文件） */
export function isDualFormatMaterialType(key?: string | null): boolean {
  return MATERIAL_TYPES.some((t) => t.key === key && t.dualFormat);
}
