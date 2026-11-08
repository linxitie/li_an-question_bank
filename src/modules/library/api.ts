/**
 * 备考资料（library）域 API 封装（P2-37）。
 *
 * 后端端点挂在 `/api/materials`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 *
 * 学习行为：详情端点 `GET /api/materials/{id}` 本身即「打开」动作，
 * 登录用户首次打开由服务端发布一次 E8 `material.opened`（同资料幂等），
 * 列表 / 进度概览等只读端点不发布事件。
 */
import { apiClient } from '@/services/api/client';

/** 本域统一客户端引用 */
export const libraryClient = apiClient;

export type LibrarySubject = 'xingce' | 'shenlun' | 'gongzhuan';

export type LibraryMaterialType =
  | 'video_intro'
  | 'video_advanced'
  | 'article'
  | 'card'
  | 'lecture'
  | 'paper';

/** 发布者（A2：列表「发布者」列 + 「我发布的」筛选） */
export interface LibraryMaterialPublisher {
  id: number;
  /** 昵称优先，空则回退用户名 */
  name: string;
  role: 'admin' | 'teacher' | 'student';
  /** 角色中文（管理员/教师/学生） */
  role_label: string;
}

/** 列表条目 */
export interface LibraryMaterial {
  id: number;
  subject: LibrarySubject;
  type: LibraryMaterialType;
  category: string | null;
  title: string;
  summary: string | null;
  badge: string | null;
  cover_image: string | null;
  /** 全部配图（封面 + 正文附图），后端 _item_brief 直接算好 */
  image_urls?: string[];
  /** A 方案：技巧类卡片（分类有、考点空）标记，后端 _item_brief 返回 */
  is_generic?: boolean;
  /** 考点 ID（有则说明是正式考点卡） */
  point_id?: number | null;
  duration: number;
  read_time: number;
  difficulty: number;
  view_count: number;
  card_front: string | null;
  sort_order: number;
  /** A2：入库时间（对外叫「上传时间」），ISO-8601 带 +08:00；空表示无记录 */
  created_at?: string | null;
  /** A2：发布者；creator_id 为空时为 null（前端显示 —） */
  publisher?: LibraryMaterialPublisher | null;
  is_studied?: boolean;
  progress_percent?: number;
  is_favorite?: boolean;
}

/** 详情条目（在列表条目基础上多出正文与视频地址） */
export interface LibraryMaterialDetail extends LibraryMaterial {
  content: string;
  card_back: string;
  video_url: string;
}

export interface LibraryListQuery {
  subject: LibrarySubject;
  type?: LibraryMaterialType;
  page?: number;
  pageSize?: number;
}

export interface LibraryListResult {
  total: number;
  items: LibraryMaterial[];
}

export interface LibraryProgressSummary {
  studied: number;
  total: number;
  percentage: number;
}

export interface LibraryProgressResult {
  ok: boolean;
  completed: boolean;
  progress_percent: number;
}

export interface LibraryFavoriteResult {
  is_favorite: boolean;
}

interface LibraryRequestConfig {
  url: string;
  method: 'GET' | 'POST';
  params?: Record<string, unknown>;
  data?: Record<string, unknown>;
}

async function request<T>(config: LibraryRequestConfig): Promise<T> {
  const response = await libraryClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

/** 查询资料列表（只读，不上报打开行为） */
export function fetchLibraryList(
  query: LibraryListQuery
): Promise<LibraryListResult> {
  return request<LibraryListResult>({
    url: '/api/materials',
    method: 'GET',
    params: {
      subject: query.subject,
      type: query.type || undefined,
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20
    }
  });
}

/**
 * 查询资料详情。
 * 副作用：登录用户首次打开即由后端记录打开并发布一次 `material.opened`；
 * 同资料再次请求不会再发事件。
 */
export function fetchLibraryDetail(
  id: string | number
): Promise<LibraryMaterialDetail> {
  return request<LibraryMaterialDetail>({
    url: `/api/materials/${id}`,
    method: 'GET'
  });
}

/** 查询科目学习进度概览（登录） */
export function fetchLibraryProgressSummary(
  subject: LibrarySubject
): Promise<LibraryProgressSummary> {
  return request<LibraryProgressSummary>({
    url: '/api/materials/progress-summary',
    method: 'GET',
    params: { subject }
  });
}

/** 上报学习进度（后端 UPSERT 幂等；进度只存后端） */
export function reportLibraryProgress(payload: {
  materialId: number;
  progressPercent?: number;
  completed?: boolean;
}): Promise<LibraryProgressResult> {
  return request<LibraryProgressResult>({
    url: '/api/materials/progress',
    method: 'POST',
    data: {
      material_id: payload.materialId,
      progress_percent: payload.progressPercent ?? 0,
      completed: Boolean(payload.completed)
    }
  });
}

/** 我的收藏（登录） */
export function fetchLibraryFavorites(): Promise<LibraryListResult> {
  return request<LibraryListResult>({
    url: '/api/materials/favorites',
    method: 'GET'
  });
}

/** 收藏切换（登录） */
export function toggleLibraryFavorite(
  id: string | number
): Promise<LibraryFavoriteResult> {
  return request<LibraryFavoriteResult>({
    url: `/api/materials/${id}/favorite`,
    method: 'POST'
  });
}

/** 刷新资料列表（等同重新拉取） */
export function refreshLibrary(
  query: LibraryListQuery
): Promise<LibraryListResult> {
  return fetchLibraryList(query);
}

/** 管理端统计概览（`GET /api/materials/admin/stats`，需管理员登录态） */
export interface AdminMaterialStats {
  total: number;
  /** 按类型计数，键为 6 个类型：video_intro / video_advanced / article / card / lecture / paper */
  by_type: Record<string, number>;
  by_subject: Record<string, number>;
  by_status: Record<string, number>;
}

/**
 * 拉取管理端统计（资料管理 v3.1 A1：管理页统计卡要显示「讲义 / 试卷」两个新类型）。
 * 后端 `admin_stats` 已固定返回 6 个类型键，缺省补 0，故前端不会拿到 undefined。
 */
export function fetchAdminMaterialStats(): Promise<AdminMaterialStats> {
  return request<AdminMaterialStats>({
    url: '/api/materials/admin/stats',
    method: 'GET'
  });
}

/**
 * 资料原件（B1，2026-11-07）：`material_file` 的一行。
 *
 * 原件存在 `backend/data/material_files/`（**不在 `/uploads` 公开目录**），
 * 下载必须带 token 走 `/api/materials/files/{file_id}/download`，
 * 所以前端要用 `downloadMaterialFile()` 而不是裸 `<a href>`。
 */
export interface MaterialFileItem {
  file_id: number;
  file_name: string;
  file_ext: string;
  mime_type: string;
  /** 字节 */
  size: number;
  /** 人读大小，如 `35 KB` */
  size_label: string;
  sha256_short: string;
  role: 'primary' | 'attachment' | string;
  role_label: string;
  source: string;
  download_url: string;
  uploaded_at: string | null;
}

/**
 * 试卷元数据（C2/C4，2026-11-08）。
 *
 * 年份/地区/题本或答案来自**文件名解析**（后端 `paper_meta_parser`），解析不出就是 null（界面显示 `—`）；
 * `exam_paper_id` 非空表示这份资料已和题库里的可作答卷对上（`paper_code` 两侧相等）。
 */
export interface MaterialPaperMeta {
  paper_code: string | null;
  year: number | null;
  region_name: string | null;
  region_code: string | null;
  book_kind_label: string | null;
  volume: number | null;
  meta_label: string;
  exam_paper_id: number | null;
  question_count: number | null;
  total_score: number | null;
  duration: number | null;
  /** 人工订正过的原始键值（改信息表单只回填这些，不回填解析结果） */
  override?: Record<string, unknown>;
  /** 题量/总分/时长各自来自哪里：`edit` = 管理员订正，`exam` = 可作答卷兜底，null = 没值 */
  source?: { question_count: string | null; total_score: string | null; duration: string | null };
  paper_type: string | null;
  /** 学生当前能否考（`paper_type === 'PUBLISHED'`） */
  answerable: boolean;
}

/** C2b：改信息的提交体（全部非必填；null / 空串 = 清除该项） */
export interface MaterialMetaPayload {
  title?: string;
  category?: string | null;
  year?: number | null;
  region_code?: string | null;
  region_name?: string | null;
  book_kind?: string | null;
  volume?: number | null;
  question_count?: number | null;
  total_score?: number | null;
  duration?: number | null;
  paper_code?: string | null;
}

export interface MaterialMetaResult {
  ok: boolean;
  changed: string[];
  material: {
    id: number;
    title: string;
    category: string | null;
    paper_code: string | null;
    status: number;
    type: LibraryMaterialType;
  };
  paper: MaterialPaperMeta | null;
}

/**
 * 删除资料下的一份原件（C1 同期补的能力，2026-11-08）。
 *
 * 服务端只删登记行；同一内容没有别的资料引用时才删物理文件。
 * 返回删除结果 + 该资料剩余原件，前端可直接替换列表，不必再拉一次预览。
 */
export async function deleteMaterialFile(
  materialId: number,
  fileId: number
): Promise<{ ok: boolean; files: MaterialFileItem[]; deleted: { physical_deleted: boolean } }> {
  const response = await libraryClient.request<{
    ok: boolean;
    files: MaterialFileItem[];
    deleted: { physical_deleted: boolean };
  }>({
    url: `/api/materials/admin/${materialId}/files/${fileId}`,
    method: 'DELETE',
    baseURL: ''
  });
  return response.data;
}

/** 改试卷/讲义信息（C2b）：只写资料本身，不动题库里的可作答卷 */
export async function updateMaterialMeta(
  id: number,
  payload: MaterialMetaPayload
): Promise<MaterialMetaResult> {
  const response = await libraryClient.request<MaterialMetaResult>({
    url: `/api/materials/admin/${id}/meta`,
    method: 'PATCH',
    baseURL: '',
    data: payload
  });
  return response.data;
}

/**
 * 管理端统一预览契约（A3）。
 *
 * 6 类资料共用一个抽屉：卡片给 `card`，文章/讲义/试卷给 `content_html`（服务端已 sanitize），
 * 视频给 `video.url`。`chapters`（讲义章节，C 批）当前为空值；
 * `files` 从 B1 起为真实原件清单；`paper` 从 C2/C4 起为试卷元数据 + 可作答卷关联。
 */
export interface MaterialPreview {
  id: number;
  type: LibraryMaterialType;
  type_label: string;
  title: string;
  summary: string | null;
  subject: LibrarySubject;
  subject_label: string;
  category: string | null;
  status: number;
  badge: string | null;
  difficulty: number;
  read_time: number;
  duration: number;
  view_count: number;
  study_count: number;
  publisher: LibraryMaterialPublisher | null;
  /** 入库时间（ISO +08:00） */
  created_at: string | null;
  /** 文件上传时间；后端暂无可靠来源，恒为 null（B 批补） */
  uploaded_at: string | null;
  content_html: string | null;
  card: { front: string | null; back: string | null; images: string[] } | null;
  video: { url: string } | null;
  /** 讲义章节树（C1）；非讲义或未抽到大纲时为 [] */
  chapters: MaterialChapter[];
  /** 讲义规模（C1）：字数/章节数；非讲义时 word_count 为 null */
  doc?: { word_count: number | null; word_count_label: string; chapter_count: number };
  /** 原件清单（B1）：主文件在前、附件在后 */
  files: MaterialFileItem[];
  /** 试卷元数据（C2/C4）；非试卷类为 null */
  paper: MaterialPaperMeta | null;
}

/** 拉取单条资料的管理端预览数据（含未上架） */
export function fetchMaterialPreview(id: number): Promise<MaterialPreview> {
  return request<MaterialPreview>({
    url: `/api/materials/admin/${id}/preview`,
    method: 'GET'
  });
}

/**
 * 下载原件（B1）。
 *
 * 为什么要走 fetch + blob 而不是 `<a href>`：下载接口要求 `Authorization`，
 * 浏览器对 `<a>` 导航不会带自定义头，会直接 401。
 * 做成"先取 blob → 触发 <a download>"与论坛附件下载（`FileList.vue`）同一套路；
 * 服务端出错时把 JSON 错误体当文件存下来是最常见的坑，这里统一抛错交给调用方提示。
 *
 * 取 token 只走 `window.__VTJ_AUTH__.getJsonHeaders()`（与 `interceptors.ts` 同一来源），
 * 不自己解析 localStorage，避免多出第二套凭据逻辑。
 */
async function authHeadersForDownload(): Promise<Record<string, string>> {
  const auth = (window as unknown as {
    __VTJ_AUTH__?: { getJsonHeaders?: () => Record<string, string> };
  }).__VTJ_AUTH__;
  if (auth && typeof auth.getJsonHeaders === 'function') {
    const h = auth.getJsonHeaders();
    if (h && Object.keys(h).length) return h;
  }
  return {};
}

export async function downloadMaterialFile(file: MaterialFileItem): Promise<void> {
  const res = await fetch(file.download_url, {
    headers: await authHeadersForDownload(),
    cache: 'no-store'
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.error?.message || body?.detail || detail;
    } catch {
      /* 非 JSON 错误体，保留状态码 */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = file.file_name || 'download';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 4000);
}

/**
 * 批量导入：单个文件的上传结果（B2，2026-11-07）。
 *
 * 后端语义：不带 `materialId` → 建一条资料（未上架）+ 原件作主文件；
 * 带 `materialId` → 只挂附件（双格式配对）。同内容不重复建，返回 `duplicate=true`。
 */
export interface UploadFileResult {
  duplicate: boolean;
  created: boolean;
  material_id: number;
  title: string;
  file?: MaterialFileItem;
  /** duplicate=true 时：已存在的那份原件 */
  existing_file_id?: number;
  file_name?: string;
}

export interface UploadFileParams {
  file: File;
  subject: LibrarySubject;
  type: 'article' | 'lecture' | 'paper';
  category?: string;
  title?: string;
  /** 有值 = 挂到这条资料当附件（双格式配对的第二步） */
  materialId?: number;
  /** 上传进度 0–100（浏览器在本地算，服务端不参与） */
  onProgress?: (percent: number) => void;
}

/**
 * 上传一个原件（批量导入队列的最小单位）。
 *
 * 为什么逐文件请求而不是一次 50 个：进度、失败重试、跳过重复都能精确到行；
 * 后端按单文件 20MB 守上限，数量/总量由前端编排（`utils/batchUploadPlan.ts`）把关。
 * 超时单独放宽到 120s——20MB 文件在慢盘/弱网下远超 apiClient 默认的 15s。
 */
export async function uploadMaterialFile(params: UploadFileParams): Promise<UploadFileResult> {
  const form = new FormData();
  form.append('file', params.file, params.file.name);
  form.append('subject', params.subject);
  form.append('type', params.type);
  if (params.category) form.append('category', params.category);
  if (params.title) form.append('title', params.title);
  if (params.materialId != null) form.append('material_id', String(params.materialId));

  const response = await libraryClient.request<UploadFileResult>({
    url: '/api/materials/admin/files/upload',
    method: 'POST',
    baseURL: '',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    onUploadProgress: (e) => {
      if (!params.onProgress) return;
      const total = e.total || params.file.size || 0;
      if (!total) return;
      params.onProgress(Math.min(99, Math.round(((e.loaded || 0) / total) * 100)));
    }
  });
  params.onProgress?.(100);
  return response.data;
}

/**
 * 讲义章节（C1）：`level` 1=章 2=节，`title` 是标题原文。
 * 由后端在**上传/导入时**从 docx 样式或编号行抽取（`services/doc_outline.py`），存快照。
 */
export interface MaterialChapter {
  level: number;
  title: string;
}

/** 管理端列表条目：在列表条目上多出上下架/学习人数/发布者 */export interface AdminMaterialListItem extends LibraryMaterial {
  status: number;
  study_count: number;
  creator_id: number | null;
  /** 讲义章节数（C1）；未抽到大纲/非讲义为 null */
  chapter_count?: number | null;
  /** 讲义字数（C1） */
  word_count?: number | null;
  /** 试卷年份/地区/卷别（C3，订正优先）；非试卷为 null */
  paper_year?: number | null;
  paper_region?: string | null;
  paper_book_kind?: string | null;
}

/** 管理端列表查询（A2 新增 created_within / order / publisher_id） */
export interface AdminMaterialListQuery {
  subject?: LibrarySubject | '';
  type?: LibraryMaterialType | '';
  status?: number | null;
  keyword?: string;
  /** 最近 N 天（滚动窗口：create_time >= now - N 天） */
  created_within?: '7d' | '30d' | '';
  /** 默认 created_desc（最新在上） */
  order?: 'created_desc' | 'created_asc';
  /** 只看某个发布者 */
  publisher_id?: number | null;
  /** C3：试卷年份 */
  paper_year?: number | null;
  /** C3：试卷地区（地区代码或中文） */
  region?: string;
  /** C3：试卷卷别 T/A/J */
  book_kind?: string;
  page?: number;
  pageSize?: number;
}

export interface AdminMaterialListResult {
  total: number;
  items: AdminMaterialListItem[];
}

/**
 * 管理端资料列表（含下架；A2 起返回 `created_at` 与 `publisher`）。
 * 空字符串参数不下发，避免后端把 `created_within=` 当成非法值 422。
 */
export function fetchAdminMaterialList(
  query: AdminMaterialListQuery = {}
): Promise<AdminMaterialListResult> {
  return request<AdminMaterialListResult>({
    url: '/api/materials/admin/list',
    method: 'GET',
    params: {
      subject: query.subject || undefined,
      type: query.type || undefined,
      status: query.status ?? undefined,
      keyword: query.keyword || undefined,
      created_within: query.created_within || undefined,
      order: query.order ?? 'created_desc',
      publisher_id: query.publisher_id ?? undefined,
      // C3：试卷三维筛选。空值必须省略——后端 `region=''` 会被当成"不筛"，
      // 但 axios 会把 `region: undefined` 直接丢掉，语义更干净。
      paper_year: query.paper_year ?? undefined,
      region: query.region || undefined,
      book_kind: query.book_kind || undefined,
      page: query.page ?? 1,
      page_size: query.pageSize ?? 20
    }
  });
}
