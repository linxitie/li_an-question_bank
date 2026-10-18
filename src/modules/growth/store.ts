/**
 * 成就成长（growth）域 Store（P2-54 / P2-55）。
 *
 * - 成就墙、学习目标、任务中心三块数据由 `load()` 并行拉取；
 * - 派生状态在本地完成：按分类分组、组内进度、任务进度百分比；
 * - 成就页增量刷新只重拉成就墙，避免任务/目标接口抖动影响成就展示；
 * - 成就解锁（earned 从无到有）广播 `growth:achievement-unlocked`；
 *   首次加载不广播，避免把历史成就当成新解锁。
 */
import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import {
  fetchAchievementWall,
  fetchGoals,
  fetchTaskOverview,
  type AchievementItem,
  type AchievementWall,
  type GoalItem,
  type GoalListQuery,
  type TaskItem,
  type TaskOverview
} from './api';
import { notifyAchievementUnlocked } from './events';

export interface GrowthState {
  loading: boolean;
  error: string | null;
  initialized: boolean;
}

export function createGrowthInitialState(): GrowthState {
  return {
    loading: false,
    error: null,
    initialized: false
  };
}

export interface AchievementGroupItem extends AchievementItem {
  progressPercent: number;
}

export interface AchievementGroup {
  category: string;
  label: string;
  items: AchievementGroupItem[];
  total: number;
  earnedCount: number;
  progressPercent: number;
}

export interface DecoratedTask extends TaskItem {
  progressPercent: number;
}

export interface TaskGroup {
  key: 'daily' | 'random' | 'weekly';
  label: string;
  items: DecoratedTask[];
}

export const CATEGORY_LABELS: Record<string, string> = {
  坚持: '🔥 学习坚持',
  数量: '📝 做题数量',
  正确率: '🎯 正确率',
  错题: '❌ 错题管理',
  社交: '💬 社交互动',
  综合: '🏆 综合成就',
  联考特色: '🎖️ 联考特色',
  隐藏: '🔒 隐藏成就',
  赛季限定: '🏅 赛季限定'
};

export const TIER_COLORS: Record<number, string> = {
  1: '#b87333',
  2: '#c0c0c0',
  3: '#ffd700',
  4: '#e5e4e2',
  5: '#b9f2ff'
};

export const TIER_LABELS: Record<number, string> = {
  1: '铜',
  2: '银',
  3: '金',
  4: '铂金',
  5: '钻石'
};

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] || category;
}

export function tierColor(tier: number): string {
  return TIER_COLORS[tier] || TIER_COLORS[1];
}

export function tierLabel(tier: number): string {
  return TIER_LABELS[tier] || TIER_LABELS[1];
}

export function clampPercent(current: number, threshold: number): number {
  if (!threshold || threshold <= 0) return 0;
  return Math.min(100, Math.max(0, Math.round((current / threshold) * 100)));
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return '加载失败，请稍后重试';
}

function decorateTask(task: TaskItem): DecoratedTask {
  return { ...task, progressPercent: clampPercent(task.current, task.threshold) };
}

function decorateGroup(category: string, items: AchievementItem[]): AchievementGroup {
  const decorated = items.map((item) => ({
    ...item,
    progressPercent: clampPercent(item.current, item.threshold)
  }));
  const earnedCount = decorated.filter((item) => item.earned).length;
  return {
    category,
    label: categoryLabel(category),
    items: decorated,
    total: decorated.length,
    earnedCount,
    progressPercent: clampPercent(earnedCount, decorated.length)
  };
}

export const useGrowthStore = defineStore('growth', () => {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const initialized = ref(false);

  const wall = ref<AchievementWall | null>(null);
  const goals = ref<GoalItem[]>([]);
  const taskOverview = ref<TaskOverview | null>(null);
  const lastUnlocked = ref<AchievementItem[]>([]);

  const ready = computed(() => initialized.value && error.value === null);
  const total = computed(() => wall.value?.total ?? 0);
  const earnedCount = computed(() => wall.value?.earned_count ?? 0);
  const overallProgress = computed(() => clampPercent(earnedCount.value, total.value));

  const achievementGroups = computed<AchievementGroup[]>(() => {
    const categories = wall.value?.categories ?? {};
    return Object.entries(categories).map(([category, items]) =>
      decorateGroup(category, items)
    );
  });

  const goalsWithProgress = computed(() =>
    goals.value.map((goal) => ({
      ...goal,
      progressPercent: clampPercent(goal.current_count, goal.target_count)
    }))
  );

  const dailyTasks = computed(() =>
    (taskOverview.value?.daily ?? []).map(decorateTask)
  );
  const randomTasks = computed(() =>
    (taskOverview.value?.random ?? []).map(decorateTask)
  );
  const weeklyTasks = computed(() =>
    (taskOverview.value?.weekly ?? []).map(decorateTask)
  );

  const taskGroups = computed<TaskGroup[]>(() => [
    { key: 'daily', label: '每日任务', items: dailyTasks.value },
    { key: 'random', label: '随机任务', items: randomTasks.value },
    { key: 'weekly', label: '周常任务', items: weeklyTasks.value }
  ]);

  const checkin = computed(() => taskOverview.value?.checkin ?? null);

  function applyWall(next: AchievementWall): void {
    const previousEarned = wall.value
      ? new Set(
          Object.values(wall.value.categories)
            .flat()
            .filter((item) => item.earned)
            .map((item) => item.achievement_id)
        )
      : null;

    wall.value = next;

    if (!previousEarned) return;

    const unlocked = Object.values(next.categories)
      .flat()
      .filter((item) => item.earned && !previousEarned.has(item.achievement_id));

    lastUnlocked.value = unlocked;
    for (const item of unlocked) {
      notifyAchievementUnlocked({
        achievementId: item.achievement_id,
        title: item.name,
        unlockedAt: Date.now()
      });
    }
  }

  async function loadAchievements(): Promise<void> {
    applyWall(await fetchAchievementWall());
  }

  async function refreshAchievements(): Promise<void> {
    try {
      await loadAchievements();
    } catch (e) {
      error.value = errorMessage(e);
    }
  }

  async function loadGoals(query: GoalListQuery = {}): Promise<void> {
    try {
      const result = await fetchGoals(query);
      goals.value = result.items;
    } catch (e) {
      error.value = errorMessage(e);
      goals.value = [];
    }
  }

  async function load(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [wallResult, goalsResult, tasksResult] = await Promise.allSettled([
        fetchAchievementWall(),
        fetchGoals(),
        fetchTaskOverview()
      ]);

      if (wallResult.status === 'fulfilled') {
        applyWall(wallResult.value);
      } else {
        error.value = errorMessage(wallResult.reason);
      }

      if (goalsResult.status === 'fulfilled') {
        goals.value = goalsResult.value.items;
      } else {
        goals.value = [];
        if (!error.value) error.value = errorMessage(goalsResult.reason);
      }

      if (tasksResult.status === 'fulfilled') {
        taskOverview.value = tasksResult.value;
      } else {
        taskOverview.value = null;
        if (!error.value) error.value = errorMessage(tasksResult.reason);
      }
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  function reset(): void {
    const initial = createGrowthInitialState();
    loading.value = initial.loading;
    error.value = initial.error;
    initialized.value = initial.initialized;
    wall.value = null;
    goals.value = [];
    taskOverview.value = null;
    lastUnlocked.value = [];
  }

  return {
    loading,
    error,
    initialized,
    wall,
    goals,
    taskOverview,
    lastUnlocked,
    ready,
    total,
    earnedCount,
    overallProgress,
    achievementGroups,
    goalsWithProgress,
    dailyTasks,
    randomTasks,
    weeklyTasks,
    taskGroups,
    checkin,
    reset,
    load,
    loadAchievements,
    refreshAchievements,
    loadGoals
  };
});
