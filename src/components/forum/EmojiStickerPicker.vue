<template>
  <div class="emoji-panel">
    <div class="emoji-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="emoji-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
      <button class="emoji-close" @click="$emit('close')">×</button>
    </div>

    <div v-if="activeTab === 'emoji'" class="emoji-grid">
      <button
        v-for="emoji in emojis"
        :key="emoji"
        class="emoji-cell"
        @click="$emit('select', { type: 'emoji', value: emoji })"
      >
        {{ emoji }}
      </button>
    </div>

    <div v-else class="sticker-area">
      <div v-if="loading" class="sticker-empty">加载中...</div>
      <div v-else-if="!stickers.length" class="sticker-empty">
        还没有自定义表情包，点下方上传
      </div>
      <div v-else class="sticker-grid">
        <div v-for="sticker in stickers" :key="sticker.id" class="sticker-cell">
          <button
            class="sticker-pick"
            :title="sticker.name"
            @click="$emit('select', { type: 'sticker', value: sticker.url, name: sticker.name })"
          >
            <img :src="sticker.url" :alt="sticker.name" />
          </button>
          <button
            v-if="sticker.ownerId === authStore.userId"
            class="sticker-delete"
            title="删除"
            @click="removeSticker(sticker.id)"
          >
            ×
          </button>
        </div>
      </div>

      <label class="sticker-upload">
        <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" @change="onUpload" />
        {{ uploading ? '上传中...' : '+ 上传自定义表情包' }}
      </label>
      <p v-if="error" class="sticker-error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  deleteForumSticker,
  fetchForumStickers,
  uploadForumSticker,
  type ForumSticker
} from '@/modules/community/api';
import { useAuthStore } from '@/stores/auth';

defineEmits<{
  (event: 'select', payload: { type: 'emoji' | 'sticker'; value: string; name?: string }): void;
  (event: 'close'): void;
}>();

const tabs = [
  { key: 'emoji', label: '表情' },
  { key: 'sticker', label: '表情包' }
] as const;

const EMOJIS = [
  '😀', '😄', '😁', '😆', '😅', '😂', '🤣', '😊',
  '😇', '🙂', '😉', '😍', '🥰', '😘', '😋', '😜',
  '🤪', '🤗', '🤔', '🤨', '😐', '😴', '😪', '😢',
  '😭', '😤', '😡', '🥺', '😱', '😳', '🤯', '😎',
  '👍', '👎', '👏', '🙏', '💪', '👌', '✌️', '🤝',
  '❤️', '💔', '🔥', '💯', '✨', '🎉', '🎓', '📚'
];

const emojis = EMOJIS;
const activeTab = ref<'emoji' | 'sticker'>('emoji');
const stickers = ref<ForumSticker[]>([]);
const loading = ref(false);
const uploading = ref(false);
const error = ref('');
const authStore = useAuthStore();

async function loadStickers() {
  loading.value = true;
  error.value = '';
  try {
    const result = await fetchForumStickers();
    stickers.value = result.stickers;
  } catch (e) {
    error.value = e instanceof Error ? e.message : '表情包加载失败';
  } finally {
    loading.value = false;
  }
}

async function onUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  error.value = '';
  try {
    const sticker = await uploadForumSticker(file);
    stickers.value = [...stickers.value, sticker];
  } catch (e) {
    error.value = e instanceof Error ? e.message : '上传失败';
  } finally {
    uploading.value = false;
    input.value = '';
  }
}

async function removeSticker(stickerId: number) {
  error.value = '';
  try {
    await deleteForumSticker(stickerId);
    stickers.value = stickers.value.filter((item) => item.id !== stickerId);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删除失败';
  }
}

onMounted(() => {
  authStore.refresh();
  loadStickers();
});
</script>

<style scoped>
.emoji-panel {
  width: 300px;
  max-width: calc(100vw - 24px);
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(26, 54, 95, 0.12);
  overflow: hidden;
}
.emoji-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border-bottom: 1px solid #f0f2f5;
}
.emoji-tab {
  background: none;
  border: none;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: #5a6488;
  cursor: pointer;
}
.emoji-tab.active {
  background: #eef2f8;
  color: #1a365d;
  font-weight: 600;
}
.emoji-close {
  margin-left: auto;
  background: none;
  border: none;
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
  line-height: 1;
}
.emoji-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  padding: 8px;
  max-height: 220px;
  overflow-y: auto;
}
.emoji-cell {
  background: none;
  border: none;
  font-size: 20px;
  line-height: 1;
  padding: 6px 0;
  border-radius: 6px;
  cursor: pointer;
}
.emoji-cell:hover {
  background: #f5f7fa;
}
.sticker-area {
  padding: 10px;
}
.sticker-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}
.sticker-cell {
  position: relative;
}
.sticker-pick {
  width: 100%;
  aspect-ratio: 1;
  border: 1px solid #f0f2f5;
  border-radius: 8px;
  background: #fafbfc;
  cursor: pointer;
  padding: 4px;
}
.sticker-pick img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.sticker-delete {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: #c91f37;
  color: #fff;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
}
.sticker-upload {
  display: block;
  margin-top: 10px;
  text-align: center;
  font-size: 12px;
  color: #1a365d;
  background: #eef2f8;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
}
.sticker-upload input {
  display: none;
}
.sticker-empty {
  text-align: center;
  color: #8899aa;
  font-size: 12px;
  padding: 24px 0;
}
.sticker-error {
  margin: 6px 0 0;
  color: #c91f37;
  font-size: 12px;
}
</style>
