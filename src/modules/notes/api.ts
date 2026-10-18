/**
 * 笔记与收藏（notes）域 API 封装。
 *
 * 后端端点挂在 `/api/notes`、`/api/collection`（api_surface.json 冻结口径），
 * 与客户端默认 baseURL `/api/v1` 不同，故请求层显式置空 baseURL。
 */
import { apiClient } from '@/services/api/client';

export const notesClient = apiClient;

export type NoteType = 'all' | 'question' | 'news';
export type NoteResourceType = 'question' | 'news';
export type FavoriteKind = 'question' | 'news';

export interface NoteListQuery {
  noteType?: NoteType;
  page?: number;
  pageSize?: number;
}

export interface NoteItem {
  note_id: string;
  type: NoteResourceType;
  note_text: string;
  title?: string;
  subject?: string;
  question_id?: number;
  news_id?: number;
  quote_text?: string;
  color?: string;
  line_style?: string;
  create_time?: string | null;
  update_time?: string | null;
}

export interface NoteListResult {
  total: number;
  page: number;
  page_size: number;
  items: NoteItem[];
}

export interface NotesStats {
  question_notes: number;
  news_notes: number;
  total: number;
}

export interface QuestionNoteDetailOption {
  text: string;
  letter: string;
  is_correct: boolean;
}

export interface QuestionNoteDetail {
  question_id: number;
  subject_name: string;
  question_type: string;
  question_content: string;
  options: QuestionNoteDetailOption[];
  answer: string;
  answer_analysis: string;
  knowledge_path: string;
  difficulty: number;
  correct_rate: number;
  source?: string;
  year?: number | null;
}

export interface NoteCreatePayload {
  type: NoteResourceType;
  id: number;
  note_text: string;
  quote_text?: string;
  color?: string;
  line_style?: string;
}

export interface NoteCreateResult {
  note_id: string;
  message: string;
  created?: boolean;
  updated?: boolean;
}

export interface FavoriteTogglePayload {
  type: FavoriteKind;
  id: number;
}

export interface FavoriteToggleResult {
  favorited: boolean;
  message: string;
  fav_id?: string;
}

export interface NewsFavoriteItem {
  fav_type: 'news' | 'quote';
  fav_id: number;
  news_id?: number;
  title?: string;
  content: string;
  source?: string;
  category?: string;
  summary?: string;
  create_time?: string;
  quote_id?: number;
  obsidian_source?: string;
}

export interface QuestionFavoriteItem {
  fav_id: number;
  question_id: number;
  question_content: string;
  options: unknown;
  answer: string;
  answer_analysis: string;
  difficulty: number;
  accuracy_rate: number;
  subject_id: number | null;
  subject_name: string;
  subcategory: string;
  create_time?: string;
}

export interface FavoritesListResult<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface CollectionStats {
  question_favorites: number;
  news_favorites: number;
  quote_favorites: number;
  news_quote_total: number;
  total: number;
}

interface NotesRequestConfig {
  url: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  params?: Record<string, unknown>;
  data?: unknown;
}

const DEFAULT_PAGE_SIZE = 20;
const MAX_PAGE_SIZE = 100;

async function request<T>(config: NotesRequestConfig): Promise<T> {
  const response = await notesClient.request<T>({ ...config, baseURL: '' });
  return response.data;
}

function normalizePage(page?: number): number {
  return page && page > 0 ? Math.floor(page) : 1;
}

function normalizePageSize(size?: number): number {
  if (!size || size < 1) return DEFAULT_PAGE_SIZE;
  return Math.min(Math.floor(size), MAX_PAGE_SIZE);
}

export async function fetchNotes(query: NoteListQuery = {}): Promise<NoteListResult> {
  const page = normalizePage(query.page);
  const pageSize = normalizePageSize(query.pageSize);
  const data = await request<Partial<NoteListResult>>({
    url: '/api/notes',
    method: 'GET',
    params: { note_type: query.noteType ?? 'all', page, page_size: pageSize }
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}

export async function fetchNotesStats(): Promise<NotesStats> {
  const data = await request<Partial<NotesStats>>({
    url: '/api/notes/stats',
    method: 'GET'
  });
  return {
    question_notes: data.question_notes ?? 0,
    news_notes: data.news_notes ?? 0,
    total: data.total ?? 0
  };
}

export function fetchQuestionNoteDetail(
  questionId: number
): Promise<QuestionNoteDetail> {
  return request<QuestionNoteDetail>({
    url: `/api/notes/question/${questionId}`,
    method: 'GET'
  });
}

export function createNote(payload: NoteCreatePayload): Promise<NoteCreateResult> {
  return request<NoteCreateResult>({
    url: '/api/notes',
    method: 'POST',
    data: payload
  });
}

export async function updateNote(
  noteId: string,
  noteText: string
): Promise<{ message: string }> {
  return request<{ message: string }>({
    url: `/api/notes/${noteId}`,
    method: 'PUT',
    data: { note_text: noteText }
  });
}

export async function deleteNote(noteId: string): Promise<{ message: string }> {
  return request<{ message: string }>({
    url: `/api/notes/${noteId}`,
    method: 'DELETE'
  });
}

export async function fetchNewsFavorites(
  page = 1,
  pageSize = DEFAULT_PAGE_SIZE
): Promise<FavoritesListResult<NewsFavoriteItem>> {
  const data = await request<Partial<FavoritesListResult<NewsFavoriteItem>>>({
    url: '/api/collection/news-favorites',
    method: 'GET',
    params: { type: 'news', page: normalizePage(page), page_size: normalizePageSize(pageSize) }
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}

export async function fetchQuestionFavorites(
  page = 1,
  pageSize = DEFAULT_PAGE_SIZE
): Promise<FavoritesListResult<QuestionFavoriteItem>> {
  const data = await request<Partial<FavoritesListResult<QuestionFavoriteItem>>>({
    url: '/api/collection/question-favorites',
    method: 'GET',
    params: { page: normalizePage(page), page_size: normalizePageSize(pageSize) }
  });
  return {
    total: data.total ?? 0,
    page: data.page ?? page,
    page_size: data.page_size ?? pageSize,
    items: data.items ?? []
  };
}

export function fetchCollectionStats(): Promise<CollectionStats> {
  return request<CollectionStats>({
    url: '/api/collection/stats',
    method: 'GET'
  });
}

export function toggleFavorite(
  payload: FavoriteTogglePayload
): Promise<FavoriteToggleResult> {
  return request<FavoriteToggleResult>({
    url: '/api/collection/favorite',
    method: 'POST',
    data: payload
  });
}

export async function removeFavorite(
  favId: string | number,
  kind: FavoriteKind
): Promise<{ message: string }> {
  const composite = `${kind === 'news' ? 'n' : 'q'}_${favId}`;
  return request<{ message: string }>({
    url: `/api/collection/${composite}`,
    method: 'DELETE'
  });
}

export async function refreshNotes(): Promise<NoteListResult> {
  return fetchNotes();
}
