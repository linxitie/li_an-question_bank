/**
 * 笔记与收藏（notes）域 Store。
 *
 * 状态契约：loading / error / initialized / ready 为公共骨架；
 * notes / stats / favorites / submitting 为本域业务状态。
 * 不写 localStorage；事件只做增量刷新加速，页面 onMounted 仍须主动 load()。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  createNote,
  deleteNote as deleteNoteRequest,
  fetchCollectionStats,
  fetchNewsFavorites,
  fetchNotes,
  fetchNotesStats,
  fetchQuestionFavorites,
  fetchQuestionNoteDetail,
  removeFavorite as removeFavoriteRequest,
  toggleFavorite as toggleFavoriteRequest,
  updateNote as updateNoteRequest,
  type CollectionStats,
  type FavoriteKind,
  type FavoriteTogglePayload,
  type FavoriteToggleResult,
  type NewsFavoriteItem,
  type NoteCreatePayload,
  type NoteCreateResult,
  type NoteItem,
  type NoteListQuery,
  type NoteType,
  type NotesStats,
  type QuestionFavoriteItem,
  type QuestionNoteDetail
} from './api';

export interface NotesState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export interface NoteDraft {
  noteType: 'question' | 'news';
  resourceId: number;
  noteText: string;
}

export const MAX_NOTE_TEXT_LENGTH = 2000;

const FAVORITES_PAGE_SIZE = 100;

export function createNotesInitialState(): NotesState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export function validateNoteText(text: string): string | null {
  const value = (text ?? '').trim();
  if (!value) return '笔记内容不能为空';
  if (value.length > MAX_NOTE_TEXT_LENGTH) {
    return `笔记内容不能超过 ${MAX_NOTE_TEXT_LENGTH} 字`;
  }
  return null;
}

export function validateNoteDraft(draft: NoteDraft): string | null {
  if (draft.noteType !== 'question' && draft.noteType !== 'news') {
    return '不支持的笔记类型';
  }
  if (!Number.isInteger(draft.resourceId) || draft.resourceId <= 0) {
    return '笔记关联的资源 ID 无效';
  }
  return validateNoteText(draft.noteText);
}

export function buildNoteId(
  resourceType: 'question' | 'news',
  noteId: string | number
): string {
  const raw = String(noteId ?? '');
  if (raw.startsWith('q_') || raw.startsWith('n_')) return raw;
  return `${resourceType === 'question' ? 'q' : 'n'}_${raw}`;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '请求失败，请稍后重试';
}

export const useNotesStore = defineStore('notes', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const noteType = ref<NoteType>('all');
  const notes = ref<NoteItem[]>([]);
  const notesTotal = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const stats = ref<NotesStats | null>(null);

  const newsFavorites = ref<NewsFavoriteItem[]>([]);
  const questionFavorites = ref<QuestionFavoriteItem[]>([]);
  const collectionStats = ref<CollectionStats | null>(null);

  const submitting = ref(false);
  const pendingWrites = new Set<string>();

  const ready = computed(() => initialized.value && error.value === null);
  const isEmpty = computed(
    () => initialized.value && !loading.value && notes.value.length === 0
  );
  const favoriteTotal = computed(
    () => newsFavorites.value.length + questionFavorites.value.length
  );

  function clearError(): void {
    error.value = null;
  }

  function beginWrite(key: string): boolean {
    if (pendingWrites.has(key)) return false;
    pendingWrites.add(key);
    submitting.value = true;
    return true;
  }

  function endWrite(key: string): void {
    pendingWrites.delete(key);
    submitting.value = pendingWrites.size > 0;
  }

  async function load(query: NoteListQuery = {}): Promise<void> {
    if (query.noteType) noteType.value = query.noteType;
    if (query.page) page.value = query.page;
    if (query.pageSize) pageSize.value = query.pageSize;

    loading.value = true;
    error.value = null;
    try {
      const result = await fetchNotes({
        noteType: noteType.value,
        page: page.value,
        pageSize: pageSize.value
      });
      notes.value = result.items;
      notesTotal.value = result.total;
    } catch (e) {
      error.value = errorMessage(e);
      notes.value = [];
      notesTotal.value = 0;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadStats(): Promise<void> {
    try {
      stats.value = await fetchNotesStats();
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function loadQuestionDetail(questionId: number): Promise<QuestionNoteDetail> {
    return fetchQuestionNoteDetail(questionId);
  }

  async function saveNote(draft: NoteDraft): Promise<NoteCreateResult | null> {
    const validation = validateNoteDraft(draft);
    if (validation) {
      error.value = validation;
      throw new Error(validation);
    }

    const payload: NoteCreatePayload = {
      type: draft.noteType,
      id: draft.resourceId,
      note_text: draft.noteText.trim()
    };
    const key = `create:${draft.noteType}:${draft.resourceId}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      const result = await createNote(payload);
      await load();
      return result;
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function updateNote(noteId: string, noteText: string): Promise<void> {
    const validation = validateNoteText(noteText);
    if (validation) {
      error.value = validation;
      throw new Error(validation);
    }

    const key = `update:${noteId}`;
    if (!beginWrite(key)) return;

    const snapshot = notes.value.map((item) => ({ ...item }));
    const trimmed = noteText.trim();
    notes.value = notes.value.map((item) =>
      item.note_id === noteId ? { ...item, note_text: trimmed } : item
    );
    error.value = null;
    try {
      await updateNoteRequest(noteId, trimmed);
    } catch (e) {
      notes.value = snapshot;
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function deleteNote(noteId: string): Promise<void> {
    const key = `delete:${noteId}`;
    if (!beginWrite(key)) return;

    const snapshot = notes.value.map((item) => ({ ...item }));
    const snapshotTotal = notesTotal.value;
    notes.value = notes.value.filter((item) => item.note_id !== noteId);
    notesTotal.value = Math.max(0, snapshotTotal - 1);
    error.value = null;
    try {
      await deleteNoteRequest(noteId);
    } catch (e) {
      notes.value = snapshot;
      notesTotal.value = snapshotTotal;
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function loadNewsFavorites(pageNo = 1): Promise<void> {
    try {
      const result = await fetchNewsFavorites(pageNo, FAVORITES_PAGE_SIZE);
      newsFavorites.value = result.items;
    } catch (e) {
      error.value = errorMessage(e);
      newsFavorites.value = [];
    }
  }

  async function loadQuestionFavorites(pageNo = 1): Promise<void> {
    try {
      const result = await fetchQuestionFavorites(pageNo, FAVORITES_PAGE_SIZE);
      questionFavorites.value = result.items;
    } catch (e) {
      error.value = errorMessage(e);
      questionFavorites.value = [];
    }
  }

  async function loadFavorites(pageNo = 1): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      await Promise.all([loadNewsFavorites(pageNo), loadQuestionFavorites(pageNo)]);
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function loadCollectionStats(): Promise<void> {
    try {
      collectionStats.value = await fetchCollectionStats();
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function toggleFavorite(
    payload: FavoriteTogglePayload
  ): Promise<FavoriteToggleResult | null> {
    if (!payload.type || !payload.id) {
      error.value = '收藏对象无效';
      throw new Error('收藏对象无效');
    }

    const key = `favorite:${payload.type}:${payload.id}`;
    if (!beginWrite(key)) return null;

    error.value = null;
    try {
      return await toggleFavoriteRequest(payload);
    } catch (e) {
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  async function removeFavorite(
    favId: string | number,
    kind: FavoriteKind
  ): Promise<void> {
    const key = `favorite-remove:${kind}:${favId}`;
    if (!beginWrite(key)) return;

    const newsSnapshot = newsFavorites.value.slice();
    const questionSnapshot = questionFavorites.value.slice();
    if (kind === 'news') {
      newsFavorites.value = newsFavorites.value.filter((item) => item.fav_id !== favId);
    } else {
      questionFavorites.value = questionFavorites.value.filter(
        (item) => item.fav_id !== favId
      );
    }
    error.value = null;
    try {
      await removeFavoriteRequest(favId, kind);
    } catch (e) {
      newsFavorites.value = newsSnapshot;
      questionFavorites.value = questionSnapshot;
      error.value = errorMessage(e);
      throw e;
    } finally {
      endWrite(key);
    }
  }

  function setNoteType(type: NoteType): void {
    noteType.value = type;
    page.value = 1;
  }

  function reset(): void {
    const initial = createNotesInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    noteType.value = 'all';
    notes.value = [];
    notesTotal.value = 0;
    page.value = 1;
    stats.value = null;
    newsFavorites.value = [];
    questionFavorites.value = [];
    collectionStats.value = null;
    submitting.value = false;
    pendingWrites.clear();
  }

  return {
    loading,
    error,
    initialized,
    ready,
    isEmpty,
    noteType,
    notes,
    notesTotal,
    page,
    pageSize,
    stats,
    newsFavorites,
    questionFavorites,
    collectionStats,
    favoriteTotal,
    submitting,
    clearError,
    reset,
    load,
    loadStats,
    loadQuestionDetail,
    saveNote,
    updateNote,
    deleteNote,
    loadNewsFavorites,
    loadQuestionFavorites,
    loadFavorites,
    loadCollectionStats,
    toggleFavorite,
    removeFavorite,
    setNoteType
  };
});
