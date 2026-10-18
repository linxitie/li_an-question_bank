import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useNotesStore, validateNoteDraft, validateNoteText } from '../store';
import {
  createNote,
  deleteNote,
  fetchNewsFavorites,
  fetchNotes,
  fetchQuestionFavorites,
  removeFavorite,
  updateNote
} from '../api';
import type { NoteItem } from '../api';

vi.mock('../api', () => ({
  createNote: vi.fn(),
  deleteNote: vi.fn(),
  fetchCollectionStats: vi.fn(),
  fetchNewsFavorites: vi.fn(),
  fetchNotes: vi.fn(),
  fetchNotesStats: vi.fn(),
  fetchQuestionFavorites: vi.fn(),
  fetchQuestionNoteDetail: vi.fn(),
  removeFavorite: vi.fn(),
  toggleFavorite: vi.fn(),
  updateNote: vi.fn()
}));

const mockedCreateNote = vi.mocked(createNote);
const mockedDeleteNote = vi.mocked(deleteNote);
const mockedFetchNotes = vi.mocked(fetchNotes);
const mockedUpdateNote = vi.mocked(updateNote);
const mockedFetchNewsFavorites = vi.mocked(fetchNewsFavorites);
const mockedFetchQuestionFavorites = vi.mocked(fetchQuestionFavorites);
const mockedRemoveFavorite = vi.mocked(removeFavorite);

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const noteItem: NoteItem = {
  note_id: 'q_1',
  type: 'question',
  note_text: '原始笔记',
  title: '题干',
  update_time: '2026-10-18T10:00:00'
};

beforeEach(() => {
  setActivePinia(createPinia());
  vi.clearAllMocks();
});

describe('notes 表单校验规则', () => {
  it('空内容与全空白内容被拒绝', () => {
    expect(validateNoteText('')).toBe('笔记内容不能为空');
    expect(validateNoteText('   ')).toBe('笔记内容不能为空');
  });

  it('超过 2000 字被拒绝，边界值通过', () => {
    expect(validateNoteText('a'.repeat(2001))).toBe('笔记内容不能超过 2000 字');
    expect(validateNoteText('a'.repeat(2000))).toBeNull();
  });

  it('草稿的资源类型与资源 ID 必须合法', () => {
    expect(
      validateNoteDraft({
        noteType: 'question',
        resourceId: 0,
        noteText: '内容'
      })
    ).toBe('笔记关联的资源 ID 无效');
    expect(
      validateNoteDraft({
        noteType: 'news',
        resourceId: 1,
        noteText: '内容'
      })
    ).toBeNull();
  });
});

describe('notes store 加载状态', () => {
  it('加载成功后写入列表与总数', async () => {
    mockedFetchNotes.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 20,
      items: [noteItem]
    });

    const store = useNotesStore();
    await store.load({ noteType: 'question' });

    expect(mockedFetchNotes).toHaveBeenCalledWith({
      noteType: 'question',
      page: 1,
      pageSize: 20
    });
    expect(store.notes).toHaveLength(1);
    expect(store.notesTotal).toBe(1);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.isEmpty).toBe(false);
  });

  it('空态：加载完成但无数据', async () => {
    mockedFetchNotes.mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 20,
      items: []
    });

    const store = useNotesStore();
    await store.load();

    expect(store.notes).toEqual([]);
    expect(store.initialized).toBe(true);
    expect(store.isEmpty).toBe(true);
  });

  it('加载失败进入错误态并清空列表', async () => {
    mockedFetchNotes.mockRejectedValue(new Error('网络连接失败'));

    const store = useNotesStore();
    await store.load();

    expect(store.error).toBe('网络连接失败');
    expect(store.loading).toBe(false);
    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(false);
    expect(store.notes).toEqual([]);
  });
});

describe('notes store 提交防护与回滚', () => {
  it('创建中重复提交被拒绝，只发一次请求', async () => {
    const pending = deferred<Awaited<ReturnType<typeof createNote>>>();
    mockedCreateNote.mockReturnValue(pending.promise);
    mockedFetchNotes.mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 20,
      items: []
    });

    const store = useNotesStore();
    const first = store.saveNote({
      noteType: 'question',
      resourceId: 1,
      noteText: '第一条'
    });
    const second = await store.saveNote({
      noteType: 'question',
      resourceId: 1,
      noteText: '重复提交'
    });

    expect(second).toBeNull();
    expect(mockedCreateNote).toHaveBeenCalledTimes(1);
    expect(store.submitting).toBe(true);

    pending.resolve({ note_id: 'q_1', message: '笔记已创建' });
    await first;
    expect(store.submitting).toBe(false);
  });

  it('非法草稿不调用接口并写入 error', async () => {
    const store = useNotesStore();

    await expect(
      store.saveNote({ noteType: 'question', resourceId: 1, noteText: '   ' })
    ).rejects.toThrow('笔记内容不能为空');

    expect(mockedCreateNote).not.toHaveBeenCalled();
    expect(store.error).toBe('笔记内容不能为空');
  });

  it('编辑失败回滚为原始内容并抛出错误', async () => {
    mockedFetchNotes.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 20,
      items: [noteItem]
    });
    mockedUpdateNote.mockRejectedValue(new Error('保存失败'));

    const store = useNotesStore();
    await store.load();

    await expect(store.updateNote('q_1', '修改后的笔记')).rejects.toThrow('保存失败');

    expect(store.notes[0].note_text).toBe('原始笔记');
    expect(store.error).toBe('保存失败');
    expect(store.submitting).toBe(false);
  });

  it('删除失败回滚列表与总数', async () => {
    mockedFetchNotes.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 20,
      items: [noteItem]
    });
    mockedDeleteNote.mockRejectedValue(new Error('删除失败'));

    const store = useNotesStore();
    await store.load();

    await expect(store.deleteNote('q_1')).rejects.toThrow('删除失败');

    expect(store.notes).toHaveLength(1);
    expect(store.notesTotal).toBe(1);
    expect(store.error).toBe('删除失败');
  });

  it('取消收藏失败回滚对应类型的列表', async () => {
    mockedFetchNewsFavorites.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 100,
      items: [
        {
          fav_type: 'news',
          fav_id: 9,
          news_id: 3,
          content: '新闻标题',
          title: '新闻标题',
          create_time: '2026-10-18T09:00:00'
        }
      ]
    });
    mockedFetchQuestionFavorites.mockResolvedValue({
      total: 0,
      page: 1,
      page_size: 100,
      items: []
    });
    mockedRemoveFavorite.mockRejectedValue(new Error('取消收藏失败'));

    const store = useNotesStore();
    await store.loadFavorites();

    expect(store.favoriteTotal).toBe(1);
    await expect(store.removeFavorite(9, 'news')).rejects.toThrow('取消收藏失败');

    expect(store.newsFavorites).toHaveLength(1);
    expect(store.favoriteTotal).toBe(1);
    expect(store.error).toBe('取消收藏失败');
  });
});

describe('notes store 重置', () => {
  it('reset 清空业务状态', async () => {
    mockedFetchNotes.mockResolvedValue({
      total: 1,
      page: 1,
      page_size: 20,
      items: [noteItem]
    });

    const store = useNotesStore();
    await store.load();
    store.reset();

    expect(store.notes).toEqual([]);
    expect(store.notesTotal).toBe(0);
    expect(store.noteType).toBe('all');
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.submitting).toBe(false);
  });
});
