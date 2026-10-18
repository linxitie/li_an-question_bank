import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import {
  fetchAchievementWall,
  fetchGoals,
  fetchTaskOverview,
  type AchievementItem,
  type AchievementWall,
  type GoalItem,
  type TaskItem,
  type TaskOverview
} from '../api';
import { useGrowthStore } from '../store';
import { clearAllEvents, EVENT_NAMES, onEvent } from '@/stores/event-bus';

vi.mock('../api', () => ({
  fetchAchievementWall: vi.fn(),
  fetchGoals: vi.fn(),
  fetchTaskOverview: vi.fn(),
  refreshGrowth: vi.fn()
}));

const mockedWall = vi.mocked(fetchAchievementWall);
const mockedGoals = vi.mocked(fetchGoals);
const mockedTasks = vi.mocked(fetchTaskOverview);

function makeAchievement(overrides: Partial<AchievementItem> = {}): AchievementItem {
  return {
    achievement_id: 1,
    category: '数量',
    name: '初试身手',
    icon: '📝',
    condition_desc: '累计做题10道',
    reward_coins: 10,
    condition_code: 'total_questions',
    threshold: 10,
    earned: false,
    tier: 0,
    is_hidden: 0,
    current: 5,
    ...overrides
  };
}

function makeWall(overrides: Partial<AchievementWall> = {}): AchievementWall {
  return {
    total: 2,
    earned_count: 1,
    progress: {},
    categories: {
      数量: [makeAchievement()],
      社交: [
        makeAchievement({
          achievement_id: 2,
          category: '社交',
          name: '初次发声',
          threshold: 1,
          current: 1,
          earned: true,
          tier: 1
        })
      ]
    },
    ...overrides
  };
}

function makeGoal(overrides: Partial<GoalItem> = {}): GoalItem {
  return {
    goal_id: 11,
    user_id: 1,
    title: '今日刷题',
    goal_type: 'DAILY',
    target_count: 10,
    current_count: 5,
    priority: 1,
    is_completed: false,
    progress_percent: 50,
    ...overrides
  };
}

function makeTask(overrides: Partial<TaskItem> = {}): TaskItem {
  return {
    task_id: 21,
    task_code: 'daily_questions',
    title: '每日10题',
    metric: 'today_questions',
    threshold: 2,
    reward_coins: 5,
    current: 1,
    completed: false,
    claimed: false,
    ...overrides
  };
}

function makeOverview(overrides: Partial<TaskOverview> = {}): TaskOverview {
  return {
    checkin: { checked_in: false, continuous_days: 0, today_reward: 0 },
    daily: [makeTask()],
    random: [],
    weekly: [],
    ...overrides
  };
}

beforeEach(() => {
  setActivePinia(createPinia());
  clearAllEvents();
  vi.clearAllMocks();
  mockedWall.mockResolvedValue(makeWall());
  mockedGoals.mockResolvedValue({ total: 1, items: [makeGoal()] });
  mockedTasks.mockResolvedValue(makeOverview());
});

describe('growth store 加载与派生', () => {
  it('并行加载成就墙/目标/任务并派生分组与进度', async () => {
    const store = useGrowthStore();
    await store.load();

    expect(mockedWall).toHaveBeenCalledTimes(1);
    expect(mockedGoals).toHaveBeenCalledTimes(1);
    expect(mockedTasks).toHaveBeenCalledTimes(1);

    expect(store.initialized).toBe(true);
    expect(store.ready).toBe(true);
    expect(store.total).toBe(2);
    expect(store.earnedCount).toBe(1);
    expect(store.overallProgress).toBe(50);

    expect(store.achievementGroups).toHaveLength(2);
    const quantity = store.achievementGroups[0];
    expect(quantity.category).toBe('数量');
    expect(quantity.label).toContain('做题数量');
    expect(quantity.items[0].progressPercent).toBe(50);
    expect(quantity.earnedCount).toBe(0);
    expect(quantity.progressPercent).toBe(0);

    expect(store.goalsWithProgress[0].progressPercent).toBe(50);
    expect(store.dailyTasks[0].progressPercent).toBe(50);
    expect(store.taskGroups.map((group) => group.key)).toEqual([
      'daily',
      'random',
      'weekly'
    ]);
  });

  it('成就墙失败时记录错误但目标/任务仍可展示', async () => {
    mockedWall.mockRejectedValue(new Error('成就服务不可用'));
    const store = useGrowthStore();
    await store.load();

    expect(store.error).toBe('成就服务不可用');
    expect(store.ready).toBe(false);
    expect(store.achievementGroups).toEqual([]);
    expect(store.goalsWithProgress).toHaveLength(1);
    expect(store.dailyTasks).toHaveLength(1);
  });

  it('reset 清空全部业务状态并回到初始契约', async () => {
    const store = useGrowthStore();
    await store.load();
    store.reset();

    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.ready).toBe(false);
    expect(store.achievementGroups).toEqual([]);
    expect(store.goalsWithProgress).toEqual([]);
    expect(store.taskGroups.every((group) => group.items.length === 0)).toBe(true);
  });
});

describe('growth store 成就解锁事件', () => {
  it('首次加载不为历史成就广播解锁事件', async () => {
    const events: unknown[] = [];
    onEvent(EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED, (payload) => events.push(payload));

    const store = useGrowthStore();
    await store.load();

    expect(events).toEqual([]);
  });

  it('增量刷新只重拉成就墙，新获得成就广播解锁事件', async () => {
    const store = useGrowthStore();
    await store.load();

    const events: Array<{ achievementId?: number | string; title?: string }> = [];
    onEvent(EVENT_NAMES.GROWTH_ACHIEVEMENT_UNLOCKED, (payload) => events.push(payload));

    mockedWall.mockResolvedValue(
      makeWall({
        earned_count: 2,
        categories: {
          数量: [
            makeAchievement({
              earned: true,
              tier: 1
            })
          ],
          社交: makeWall().categories['社交']
        }
      })
    );

    await store.refreshAchievements();

    expect(mockedWall).toHaveBeenCalledTimes(2);
    expect(mockedGoals).toHaveBeenCalledTimes(1);
    expect(mockedTasks).toHaveBeenCalledTimes(1);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ achievementId: 1, title: '初试身手' });
    expect(store.earnedCount).toBe(2);
  });
});
