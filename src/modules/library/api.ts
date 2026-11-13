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
  /** 卡片背面（列表就带，翻转卡直接可用） */
  card_back?: string | null;
  sort_order: number;
  /** A2：入库时间（对外叫「上传时间」），ISO-8601 带 +08:00；空表示无记录 */
  created_at?: string | null;
  /** A2：发布者；creator_id 为空时为 null（前端显示 —） */
  publisher?: LibraryMaterialPublisher | null;
  is_studied?: boolean;
  progress_percent?: number;
  is_favorite?: boolean;
  /** L1/L2（2026-11-08）：投放位（仅试卷有意义）；后端 NULL 会归一化成 library/both */
  placement?: 'exam' | 'library' | 'both';
  /** 有没有原件（列表直接给，免得逐条拉详情才知道能不能显示"下载"按钮） */
  has_files?: boolean;
  file_count?: number;
  /** L2：试卷行随列表返回的元数据（年份/地区/卷别/题量/总分/时长/编号/可考） */
  paper?: MaterialPaperMeta | null;
  /** L2：讲义大纲（列表直接给，用于「N 章 · M 字」那行） */
  chapter_count?: number | null;
  word_count?: number | null;
}

/** 详情条目（在列表条目基础上多出正文与视频地址） */
export interface LibraryMaterialDetail extends LibraryMaterial {
  content: string;
  card_back: string;
  video_url: string;
  /** L2：原件清单（含 download_url），讲义/试卷抽屉的"下载原件"用 */
  files?: MaterialFileItem[];
  /** L2：讲义大纲快照（字数/章节数/章节列表），没抽到大纲时为 null */
  doc_meta?: {
    word_count?: number;
    chapter_count?: number;
    chapters?: Array<{ level: number; title: string }>;
    format?: string;
  } | null;
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
  /** 学生当前能否考（P2 起 = 已发布 + 开关/时间窗放行 + 有题） */
  answerable: boolean;
  /** P2：完整考试状态（管理端/资料页共用），未知时为 null */
  exam?: LibraryExamState | null;
  /** P2：不能考时的一句话（后端已翻成人话；能考时为空串） */
  exam_hint?: string;
}

/**
 * 考试可进入状态（P2，2026-11-09）。
 *
 * `reason` 是后端给的原因码，前端只用它选文案，**不自己推算**：
 * `ready` 可进入 / `draft` 未发布 / `no_questions` 无题 / `closed` 手动关闭 /
 * `not_started` 未到开始时间 / `expired` 已结束 / `no_paper` 未建卷。
 */
export interface LibraryExamState {
  known: boolean;
  published: boolean;
  open: boolean;
  ready: boolean;
  reason:
    | 'ready'
    | 'draft'
    | 'no_questions'
    | 'closed'
    | 'not_started'
    | 'expired'
    | 'no_paper'
    | string;
  open_at: string | null;
  close_at: string | null;
  question_count: number;
  /** 服务器本地时间（判定口径；决策 S1 用服务器时间而非浏览器时区） */
  server_now?: string;
  /** 资料侧的人读编号（管理端列表行才有） */
  paper_code?: string | null;
  paper_id?: number | null;
  /** 手动总闸：1 开 / 0 关（管理端列表行才有） */
  manual_open?: number;
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
  /** L4：投放位（exam/library/both；非试卷恒 library） */
  placement?: 'exam' | 'library' | 'both';
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

// ==================== 手写资料（S2，2026-11-12）====================
//
// 为什么需要这两个：新版页只支持"上传文件"，短文/说明类内容以前只能进旧版页的
// 「＋新建资料」富文本弹窗。这两条是它的替代入口，**没有新端点**。

export interface MaterialSaveResult {
  id?: number;
  status?: number;
  ok?: boolean;
}

/** 新建资料（默认未上架；同内容重复会 409 并提示已存在的 id） */
export async function createMaterial(body: Record<string, unknown>): Promise<MaterialSaveResult> {
  const res = await libraryClient.request<MaterialSaveResult>({
    url: '/api/materials/admin',
    method: 'POST',
    baseURL: '',
    data: body
  });
  return res.data;
}

/** 改资料（partial；只传要改的字段，后端按白名单落库） */
export async function updateMaterial(
  id: number,
  body: Record<string, unknown>
): Promise<MaterialSaveResult> {
  const res = await libraryClient.request<MaterialSaveResult>({
    url: `/api/materials/admin/${id}`,
    method: 'PUT',
    baseURL: '',
    data: body
  });
  return res.data;
}

/** 上传封面/插图（返回可直接写进 `<img src>` 的 url） */
export async function uploadMaterialImage(file: File, purpose: 'cover' | 'inline' = 'inline'): Promise<string> {
  const form = new FormData();
  form.append('file', file, file.name);
  const res = await libraryClient.request<{ url: string }>({
    url: `/api/materials/admin/upload/image?purpose=${purpose}`,
    method: 'POST',
    baseURL: '',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  });
  return res.data.url;
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
  /**
   * P1（2026-11-09）上传即建卷的结果。
   *
   * 只有「试卷 + 投放位含考试页 + 本次新建资料」才有值：
   * `created=true` 表示已建好草稿卷；`created=false` 时 `reason`/`hint` 说明为什么没建
   * （最常见是文件名缺年份/地区 → 去「改信息」补编号后点「建卷」）。
   */
  paper?: {
    created: boolean;
    paper_id?: number;
    paper_code?: string;
    paper_name?: string;
    paper_type?: string;
    question_count?: number;
    reason?: string | null;
    hint?: string | null;
  } | null;
}

export interface UploadFileParams {
  file: File;
  subject: LibrarySubject;
  type: 'article' | 'lecture' | 'paper';
  category?: string;
  title?: string;
  /** 有值 = 挂到这条资料当附件（双格式配对的第二步） */
  materialId?: number;
  /** L4：投放位（仅试卷有意义；不传 = 后端默认：试卷 both、其它 library） */
  placement?: 'exam' | 'library' | 'both';
  /**
   * W2（2026-11-09）：上传时**立即上架**。
   * 默认 false = 未上架（与"上架即审批"一致）；传 true 后端会直接置 `status=1`
   * 并同步卷状态（试卷会走 P5 联动变 PUBLISHED）。
   */
  publish?: boolean;
  /** 解析原件里的题目（试卷 docx/pdf 默认 true；批量导入可关掉） */
  autoParse?: boolean;
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
  // L4：投放位（仅 type=paper 有意义；后端对非试卷传 exam/both 会 400，所以只在该传时传）
  if (params.placement) form.append('placement', params.placement);
  // W2：立即上架（默认不上架）；解析开关也一并下发，便于批量场景关掉
  if (params.publish) form.append('publish', '1');
  if (params.autoParse === false) form.append('auto_parse', '0');

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
  /**
   * 连续序号（ID 方案 A，2026-11-08）：按当前筛选结果的倒序名次，首行 = total。
   * 与 `id`（真实主键）不同：删除/恢复会让序号前移，`id` 永不变。
   */
  seq?: number;
  /** 讲义章节数（C1）；未抽到大纲/非讲义为 null */
  chapter_count?: number | null;
  /** 讲义字数（C1） */
  word_count?: number | null;
  /** 试卷年份/地区/卷别（C3，订正优先）；非试卷为 null */
  paper_year?: number | null;
  paper_region?: string | null;
  paper_book_kind?: string | null;
  /** P2：考试可进入状态（仅试卷行有；未建卷为 {known:false}） */
  exam?: LibraryExamState | null;
  /** P3：最近一条解析草稿（列表据此显示「待确认 N 题 / 解析失败 / 已入库」） */
  parse_draft?: ParseDraftBrief | null;
}

/**
 * 解析草稿摘要（P3，2026-11-09）。
 *
 * 状态机：`pending` 待确认 → `confirmed` 已入库 / `discarded` 已放弃 / `failed` 解析失败。
 * 关键点：拆题**不直接入库**，先在管理端给人看一眼（错位入库＝学生做错题）。
 */
export interface ParseDraftBrief {
  draft_id: number;
  material_id: number;
  paper_id: number | null;
  status: 'pending' | 'confirmed' | 'discarded' | 'failed' | string;
  source_ext: string | null;
  item_count: number;
  message: string | null;
  created_at: string | null;
  expires_at: string | null;
  title?: string | null;
  warnings?: string[];
  paper_code?: string | null;
}

/** 草稿里的一道题（确认页可改题号/题型、删误拆） */
export interface ParseDraftItem {
  no: number;
  type: '单选' | '多选' | '判断' | string;
  stem: string;
  options: { A: string; B: string; C: string; D: string };
  /** 情境材料（组内共享；只挂在组里第一题上也行，入库时会带给同组每题） */
  shared: string;
  section: number;
  images: Array<{ name: string; width?: number | null; height?: number | null }>;
  flags: string[];
}

export interface ParseDraftDetail extends ParseDraftBrief {
  items: ParseDraftItem[];
  can_edit: boolean;
}

/** 管理端列表查询（A2 新增 created_within / order / publisher_id） */
export interface AdminMaterialListQuery {
  subject?: LibrarySubject | '';
  type?: LibraryMaterialType | '';
  status?: number | null;
  keyword?: string;
  /** 最近 N 天（滚动窗口：create_time >= now - N 天） */
  created_within?: '7d' | '30d' | '';
  /**
   * 默认 `id_desc`（按列表时间倒序 = 恢复的置顶，2026-11-08 ID 方案 A）。
   * `created_*` 只给「上传时间」列排序用（真实上传时间，NULL 排最后）。
   */
  order?: 'id_desc' | 'id_asc' | 'created_desc' | 'created_asc';
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
      order: query.order ?? 'id_desc',
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

// ==================== 解析导入链路（L4 文章批量上传用）====================

export interface MaterialImportUploadResult {
  import_id: number;
  parse_status: 'success' | 'failed' | 'processing' | string;
  error_message?: string;
}

/**
 * 上传素材并解析（管理端「智能导入」第 1 步）。
 *
 * 为什么文章批量要走这条而不是 `uploadMaterialFile`：后者只留档不解析，
 * 文章详情页要读 `content` 正文，留档路径拿不到正文 → 学生点开是空白。
 * 本接口会同步解析 docx/文字版 pdf，正文可用；扫描版 pdf 会转异步 OCR。
 */
export async function importMaterialFile(file: File): Promise<MaterialImportUploadResult> {
  const form = new FormData();
  form.append('file', file, file.name);
  const response = await libraryClient.request<MaterialImportUploadResult>({
    url: '/api/materials/admin/import/upload',
    method: 'POST',
    baseURL: '',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  });
  return response.data;
}

export interface MaterialImportStatusResult {
  import_id: number;
  parse_status: 'success' | 'failed' | 'processing' | string;
  error_message?: string;
  result?: unknown;
  /** 已经过多少秒（后端按 create_time 算，前端用于"已用 1:36"） */
  elapsed_seconds?: number;
  /** P2（2026-11-12）：扫描件 OCR 页级进度；非扫描件/无进度时为 undefined */
  progress?: {
    done: number;
    total: number;
    percent: number;
    phase?: string;
    truncated?: boolean;
    failed_pages?: number[];
  };
}

/** 轮询解析状态（前端 3s 一次；扫描版 pdf 会经历 processing） */
export function fetchMaterialImportStatus(importId: number): Promise<MaterialImportStatusResult> {
  return request<MaterialImportStatusResult>({
    url: `/api/materials/admin/import/${importId}/status`,
    method: 'GET'
  });
}

/** xlsx 卡片导入的解析预览：表头 + 前 200 行（S3，2026-11-12） */
export interface MaterialImportPreviewResult {
  file_type: string;
  headers: string[];
  row_count: number;
  result?: { headers?: string[]; rows?: string[][]; [key: string]: unknown };
}

export function fetchMaterialImportPreview(importId: number): Promise<MaterialImportPreviewResult> {
  return request<MaterialImportPreviewResult>({
    url: `/api/materials/admin/import/${importId}/preview`,
    method: 'GET'
  });
}

export interface MaterialImportConfirmResult {
  created: number;
  material_ids: number[];
  type?: string;
  published?: boolean;
  skipped_count?: number;
  /** xlsx 卡片通道：内容重复被跳过的行 */
  skipped?: { row: number; reason: string }[];
  /** xlsx 卡片通道：正面/背面为空被丢弃的行号 */
  invalid_rows?: number[];
  /** xlsx 卡片通道：分类/考点列非法但已回退自动分类（两种形状：入库回退 kind/value；格式校验 code/message） */
  warnings?: {
    row: number;
    code?: string;
    column?: string;
    message?: string;
    kind?: string;
    value?: string;
    replaced_by?: string;
  }[];
}

/**
 * 确认入库。
 *
 * - 文档通道（文章/讲义）：`type='article' | 'lecture'`；
 * - **xlsx 卡片通道（S3）**：`type='card'` + `column_mapping`（0 基列号，
 *   `front`/`back` 必填），后端按表建 N 张卡，上限 500 行；
 * - 默认 `publish=false`（落未上架，等人工核对后再上架）。
 */
export function confirmMaterialImport(
  importId: number,
  body: {
    subject: LibrarySubject;
    type: 'article' | 'lecture' | 'card';
    title?: string;
    category?: string;
    publish?: boolean;
    /** xlsx 卡片：列映射（0 基列号），只传填了的字段 */
    column_mapping?: Record<string, number>;
  }
): Promise<MaterialImportConfirmResult> {
  return request<MaterialImportConfirmResult>({
    url: `/api/materials/admin/import/${importId}/confirm`,
    method: 'POST',
    data: body
  });
}

// ==================== 考试开关 / 定时（P2，2026-11-09）====================

/**
 * 开/关一场考试（管理端）。
 *
 * 语义（方案 §4）：与「资料上架」**独立** —— 上架只决定资料在不在库里，
 * 本开关只决定学生能不能进考试；关闭不动历史成绩，只禁止新开。
 * 0 题的卷服务端不拦（管理端可先关），但学生侧 `exam_ready` 本来就进不去。
 */
export async function setMaterialExamOpen(
  materialId: number,
  open: boolean
): Promise<LibraryExamState> {
  const res = await libraryClient.request<{ ok: boolean; exam: LibraryExamState }>({
    url: `/api/materials/admin/${materialId}/exam-open`,
    method: 'PUT',
    baseURL: '',
    data: { open }
  });
  return res.data.exam;
}

export interface ExamWindowPayload {
  /** `YYYY-MM-DD HH:MM`（服务器本地时间）；null / 空串 = 该侧不限 */
  open_at: string | null;
  close_at: string | null;
}

/** 设置/清空定时窗口（留空 = 不限；两端都空 = 取消定时） */
export async function setMaterialExamWindow(
  materialId: number,
  payload: ExamWindowPayload
): Promise<LibraryExamState> {
  const res = await libraryClient.request<{ ok: boolean; exam: LibraryExamState }>({
    url: `/api/materials/admin/${materialId}/exam-window`,
    method: 'PUT',
    baseURL: '',
    data: payload
  });
  return res.data.exam;
}

// ==================== 上传即导题（P3，2026-11-09）====================

/** 解析这条资料的主文件（docx/pdf）→ 生成「待确认」草稿；可重复调用（重试） */
export async function parseMaterialPaper(materialId: number): Promise<ParseDraftBrief> {
  const res = await libraryClient.request<ParseDraftBrief & { ok: boolean }>({
    url: `/api/materials/admin/${materialId}/parse`,
    method: 'POST',
    baseURL: '',
    timeout: 180000        // 大 PDF 拆题 + 抽图，放宽容超时
  });
  return res.data;
}

export function fetchParseDraft(draftId: number): Promise<ParseDraftDetail> {
  return request<ParseDraftDetail>({
    url: `/api/materials/admin/parse-drafts/${draftId}`,
    method: 'GET'
  });
}

export function fetchParseDrafts(status = 'pending'): Promise<{ total: number; items: ParseDraftBrief[] }> {
  return request<{ total: number; items: ParseDraftBrief[] }>({
    url: '/api/materials/admin/parse-drafts',
    method: 'GET',
    params: { status }
  });
}

/** 整表保存草稿题目（改题号/题型、删误拆）；后端会校验题号不重复、题干非空、题型合法 */
export async function saveParseDraftItems(
  draftId: number,
  items: ParseDraftItem[]
): Promise<ParseDraftBrief> {
  const res = await libraryClient.request<ParseDraftBrief>({
    url: `/api/materials/admin/parse-drafts/${draftId}/items`,
    method: 'PUT',
    baseURL: '',
    data: { items }
  });
  return res.data;
}

export interface ParseConfirmResult {
  ok: boolean;
  paper_id: number;
  created: number;
  replaced: number;
  question_ids: number[];
  warnings?: string[];
  paper_sync?: { before?: string | null; after?: string | null } | null;
}

/** 确认入库：题目写题库 + 挂卷 + 图片落地；卷里已有题时必须 replace=true */
export async function confirmParseDraft(
  draftId: number,
  body: { replace?: boolean; subject_id?: number } = {}
): Promise<ParseConfirmResult> {
  const res = await libraryClient.request<ParseConfirmResult>({
    url: `/api/materials/admin/parse-drafts/${draftId}/confirm`,
    method: 'POST',
    baseURL: '',
    data: body,
    timeout: 180000
  });
  return res.data;
}

/** 放弃草稿（删草稿图片；正式题目/图片目录不受影响） */
export async function discardParseDraft(draftId: number): Promise<{ ok: boolean; status: string }> {
  const res = await libraryClient.request<{ ok: boolean; status: string }>({
    url: `/api/materials/admin/parse-drafts/${draftId}`,
    method: 'DELETE',
    baseURL: ''
  });
  return res.data;
}

// ==================== 答案上传（P4，2026-11-09）====================

/**
 * 答案解析草稿里的一道题。
 *
 * `answer` 为空但 `suggestion` 有值 = 只有"推断建议"（实测该层会错，所以**不自动填**，
 * 界面显示「建议 ABCD → 采纳」，由人点一下）。
 */
export interface AnswerDraftItem {
  no: number;
  answer: string;
  tier: string;
  suggestion: string;
  evidence: string;
  analysis: string;
  flags: string[];
  question_type?: string;
  current?: string;
}

export interface AnswerDraftDetail {
  draft_id: number;
  paper_id: number;
  paper_code: string | null;
  paper_name: string | null;
  /** `parsing` = 扫描件转后台 OCR 中（P4，2026-11-13）：此时 items 为空、can_edit=false */
  status: 'pending' | 'parsing' | 'applied' | 'discarded' | 'failed' | string;
  source_ext: string | null;
  source_name: string | null;
  item_count: number;
  conflict_count: number;
  empty_count: number;
  message: string | null;
  created_at: string | null;
  expires_at: string | null;
  items?: AnswerDraftItem[];
  can_edit?: boolean;
  ok?: boolean;
}

/** 上传答案文件（PDF 一等通道）→ 解析成「答案草稿」，此时**还没写库** */
export async function parseAnswerFile(
  paperId: number,
  file: File,
  onProgress?: (percent: number) => void
): Promise<AnswerDraftDetail> {
  const form = new FormData();
  form.append('file', file, file.name);
  const res = await libraryClient.request<AnswerDraftDetail>({
    url: `/api/materials/admin/papers/${paperId}/answers/parse`,
    method: 'POST',
    baseURL: '',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
    onUploadProgress: (e) => {
      const total = e.total || file.size || 0;
      if (!total) return;
      onProgress?.(Math.min(99, Math.round(((e.loaded || 0) / total) * 100)));
    }
  });
  onProgress?.(100);
  return res.data;
}

export function fetchAnswerDraft(draftId: number): Promise<AnswerDraftDetail> {
  return request<AnswerDraftDetail>({
    url: `/api/materials/admin/answers/drafts/${draftId}`,
    method: 'GET'
  });
}

/**
 * 取该卷**最近一份**答案草稿（抽屉打开时先看有没有未确认的）。
 *
 * 为什么需要：上传后若先关掉抽屉，草稿会留在库里；没有这个入口就成了"看不见的待办"。
 */
export async function fetchLatestAnswerDraft(
  paperId: number
): Promise<AnswerDraftDetail & { exists: boolean }> {
  const res = await libraryClient.request<AnswerDraftDetail & { exists: boolean }>({
    url: `/api/materials/admin/papers/${paperId}/answers/latest`,
    method: 'GET',
    baseURL: ''
  });
  return res.data;
}

/** 整表保存（补空 / 改冲突 / 采纳建议）；答案只允许 A–D，题号必须属于该卷 */
export async function saveAnswerDraftItems(
  draftId: number,
  items: AnswerDraftItem[]
): Promise<AnswerDraftDetail> {
  const res = await libraryClient.request<AnswerDraftDetail>({
    url: `/api/materials/admin/answers/drafts/${draftId}/items`,
    method: 'PUT',
    baseURL: '',
    data: { items }
  });
  return res.data;
}

export interface AnswerApplyResult {
  ok: boolean;
  filled: number;
  overwritten: number;
  kept: number;
  skipped: number;
  analysis_only: number;
  kept_numbers: number[];
}

/** 写入答案（只动 answer / answer_analysis；不重算历史成绩） */
export async function applyAnswerDraft(
  draftId: number,
  body: { overwrite?: boolean } = {}
): Promise<AnswerApplyResult> {
  const res = await libraryClient.request<AnswerApplyResult>({
    url: `/api/materials/admin/answers/drafts/${draftId}/apply`,
    method: 'POST',
    baseURL: '',
    data: body,
    timeout: 180000
  });
  return res.data;
}

export async function discardAnswerDraft(draftId: number): Promise<{ ok: boolean; status: string }> {
  const res = await libraryClient.request<{ ok: boolean; status: string }>({
    url: `/api/materials/admin/answers/drafts/${draftId}`,
    method: 'DELETE',
    baseURL: ''
  });
  return res.data;
}
