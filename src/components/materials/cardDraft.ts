/**
 * 学生「创建卡片」表单的纯逻辑（与组件解耦，便于单测）。
 *
 * 规则来源（与后台表格导入一致，见 docs/plans/备考资料_上传格式规范_v1.md）：
 * - 正面 ≤120 字、背面 ≤600 字；
 * - 背面为空时必须有配图（否则卡片没有可看的内容）；
 * - 配图最多 2 张，单张 ≤5MB，仅 png/jpg/webp。
 */
export const FRONT_MAX = 120;
export const BACK_MAX = 600;
export const IMG_MAX = 2;
export const IMG_MAX_MB = 5;
export const IMG_TYPES = ['image/png', 'image/jpeg', 'image/webp'] as const;

export interface DraftLike {
  front: string;
  back: string;
  imageCount: number;
}

export interface FileLike {
  type: string;
  size: number;
}

/** 校验单张图片；返回错误文案，空串表示通过。 */
export function checkImageFile(file: FileLike, currentCount: number): string {
  if (!IMG_TYPES.includes(file.type as (typeof IMG_TYPES)[number])) {
    return '仅支持 png / jpg / webp 图片';
  }
  if (file.size > IMG_MAX_MB * 1024 * 1024) {
    return `图片不能超过 ${IMG_MAX_MB}MB`;
  }
  if (currentCount >= IMG_MAX) {
    return `最多 ${IMG_MAX} 张配图`;
  }
  return '';
}

/** 提交前校验；返回错误文案，空串表示可以提交。 */
export function validateDraft(draft: DraftLike): string {
  if (!(draft.front || '').trim()) return '请填写卡片正面';
  if (!(draft.back || '').trim() && draft.imageCount <= 0) {
    return '背面和配图至少填一个';
  }
  if ((draft.front || '').trim().length > FRONT_MAX) {
    return `正面不能超过 ${FRONT_MAX} 字`;
  }
  if ((draft.back || '').trim().length > BACK_MAX) {
    return `背面不能超过 ${BACK_MAX} 字`;
  }
  return '';
}
