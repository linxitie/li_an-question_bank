/**
 * 论坛「问题反馈」附件上传器（2026-11-23）。
 *
 * 为什么用原生 DOM 注入而不是改 .vtj 模板：
 * R3 禁止 AI 改设计器页面的 <template>；反馈弹窗在 .vtj/vue/forum.vue 里，
 * 这里把上传控件挂到弹窗容器上，forum.vue 只在 <script> 内调用（允许范围）。
 */
export interface FeedbackAttachment {
  name: string;
  url: string;
  size?: number;
  type?: string;
  kind: 'image' | 'video';
}

const MAX_IMAGES = 5;
const MAX_VIDEOS = 1;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_VIDEO_BYTES = 50 * 1024 * 1024;

type AuthWindow = Window & {
  __VTJ_AUTH__?: { apiFetch?: (input: RequestInfo, init?: RequestInit) => Promise<Response> };
};

function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as AuthWindow).__VTJ_AUTH__;
  return auth?.apiFetch ? auth.apiFetch(url, init) : fetch(url, init);
}

export function countAttachments(items: FeedbackAttachment[]) {
  return {
    images: items.filter((i) => i.kind === 'image').length,
    videos: items.filter((i) => i.kind === 'video').length,
  };
}

function extOf(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx + 1).toLowerCase() : '';
}

export function mountFeedbackUploader(
  card: HTMLElement,
  onChange: (items: FeedbackAttachment[]) => void
): () => void {
  const state: FeedbackAttachment[] = [];

  const wrap = document.createElement('div');
  wrap.className = 'fb-uploads';
  wrap.setAttribute('data-feedback-uploads', '1');
  wrap.style.cssText = 'margin:10px 0 4px;font-size:12px;color:#5a6488;';

  const bar = document.createElement('div');
  bar.style.cssText = 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.textContent = '＋ 图片 / 视频';
  btn.style.cssText =
    'height:32px;padding:0 12px;border:1px dashed #c7cdda;border-radius:8px;background:#fff;' +
    'color:#1a2b5f;font-size:12px;cursor:pointer;';
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/quicktime';
  input.multiple = true;
  input.style.display = 'none';

  const hint = document.createElement('span');
  hint.textContent = '图片 ≤5 张（每张 5MB），视频 ≤1 个（50MB）';

  const list = document.createElement('div');
  list.style.cssText = 'display:flex;gap:6px;flex-wrap:wrap;margin-top:8px;';

  const error = document.createElement('div');
  error.style.cssText = 'color:#c41e3a;margin-top:4px;min-height:16px;';

  const render = () => {
    list.innerHTML = '';
    state.forEach((item, index) => {
      const chip = document.createElement('span');
      chip.style.cssText =
        'display:inline-flex;align-items:center;gap:6px;max-width:220px;padding:4px 8px;' +
        'border-radius:6px;background:#f4f6fb;border:1px solid #e3e7f0;';
      const label = document.createElement('span');
      label.textContent = (item.kind === 'video' ? '🎬 ' : '🖼️ ') + item.name;
      label.style.cssText = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
      const del = document.createElement('button');
      del.type = 'button';
      del.textContent = '×';
      del.style.cssText = 'border:none;background:transparent;color:#8a8faa;cursor:pointer;font-size:14px;';
      del.onclick = () => {
        state.splice(index, 1);
        render();
        onChange(state.slice());
      };
      chip.appendChild(label);
      chip.appendChild(del);
      list.appendChild(chip);
    });
  };

  const pick = () => input.click();
  btn.addEventListener('click', pick);

  input.addEventListener('change', async () => {
    error.textContent = '';
    const files = Array.from(input.files || []);
    input.value = '';
    for (const file of files) {
      const ext = extOf(file.name);
      const isVideo = ['mp4', 'mov', 'webm'].includes(ext);
      const kind: 'image' | 'video' = isVideo ? 'video' : 'image';
      const counts = countAttachments(state);
      if (kind === 'image' && counts.images >= MAX_IMAGES) {
        error.textContent = '图片最多 5 张';
        break;
      }
      if (kind === 'video' && counts.videos >= MAX_VIDEOS) {
        error.textContent = '视频最多 1 个';
        break;
      }
      if (kind === 'image' && file.size > MAX_IMAGE_BYTES) {
        error.textContent = '单张图片不能超过 5MB：' + file.name;
        continue;
      }
      if (kind === 'video' && file.size > MAX_VIDEO_BYTES) {
        error.textContent = '视频不能超过 50MB：' + file.name;
        continue;
      }
      const form = new FormData();
      form.append('file', file);
      btn.disabled = true;
      btn.textContent = '上传中…';
      try {
        const res = await authFetch(kind === 'video' ? '/api/media/video' : '/api/media/image', {
          method: 'POST',
          body: form,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          error.textContent = data.detail || '上传失败：' + file.name;
          continue;
        }
        state.push({
          name: data.name || file.name,
          url: data.url,
          size: data.size || file.size,
          type: data.type || file.type,
          kind,
        });
        render();
        onChange(state.slice());
      } catch {
        error.textContent = '上传失败：' + file.name;
      } finally {
        btn.disabled = false;
        btn.textContent = '＋ 图片 / 视频';
      }
    }
  });

  bar.appendChild(btn);
  bar.appendChild(hint);
  wrap.appendChild(bar);
  wrap.appendChild(list);
  wrap.appendChild(error);
  input.style.display = 'none';
  wrap.appendChild(input);

  const anchor = card.querySelector('.fb-anon, .tf-fb-anon, .m-fb-anon');
  if (anchor && anchor.parentNode === card) card.insertBefore(wrap, anchor);
  else card.appendChild(wrap);

  render();
  onChange([]);
  return () => {
    btn.removeEventListener('click', pick);
    wrap.remove();
  };
}
