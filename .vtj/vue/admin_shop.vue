<!-- 金币商城商品管理（管理员端） -->
<template>
  <div class="admin-shop-page">
    <div class="as-header">
      <h2>金币商城商品管理</h2>
      <div class="as-head-actions">
        <button class="btn-plain as-offshelf-btn" @click="openOffShelf">
          已下架 <span class="as-count">{{ offShelfProducts.length }}</span>
        </button>
        <button class="btn-primary" @click="openCreate">+ 新增商品</button>
      </div>
    </div>

    <!-- 在售商品 -->
    <div class="as-table-wrap">
      <table class="as-table">
        <thead>
          <tr>
            <th style="width:72px">图片</th>
            <th>名称</th>
            <th>分类</th>
            <th>金币价</th>
            <th>库存</th>
            <th>权益类型</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in onSaleProducts" :key="p.id">
            <td>
              <img v-if="isImageUrl(p.image_url)" :src="p.image_url" class="as-thumb" alt="" />
              <span v-else class="as-thumb-emoji">{{ p.image_url || '🎁' }}</span>
            </td>
            <td>{{ p.name }}</td>
            <td>{{ p.category }}</td>
            <td>🪙 {{ p.coin_price }}</td>
            <td>{{ p.stock === -1 ? '不限' : p.stock }}</td>
            <td>{{ deliverableLabel(p.deliverable_type) }}</td>
            <td><span class="status-tag on_sale">在售</span></td>
            <td>
              <button class="btn-sm" @click="openEdit(p)">编辑</button>
              <button class="btn-sm" @click="toggleStatus(p)">下架</button>
              <button class="btn-sm btn-danger" @click="deleteProduct(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!onSaleProducts.length" class="as-empty">暂无在售商品</div>
    </div>

    <!-- 已下架面板 -->
    <div v-if="state.showOffShelf" class="modal-mask" @click.self="state.showOffShelf = false">
      <div class="modal as-offshelf-modal">
        <div class="modal-header">
          <h3>已下架商品（{{ offShelfProducts.length }}）</h3>
          <button class="close-btn" @click="state.showOffShelf = false">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="!offShelfProducts.length" class="as-empty">没有已下架的商品</div>
          <table v-else class="as-table">
            <thead>
              <tr><th>图片</th><th>名称</th><th>分类</th><th>金币价</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="p in offShelfProducts" :key="p.id">
                <td>
                  <img v-if="isImageUrl(p.image_url)" :src="p.image_url" class="as-thumb" alt="" />
                  <span v-else class="as-thumb-emoji">{{ p.image_url || '🎁' }}</span>
                </td>
                <td>{{ p.name }}</td>
                <td>{{ p.category }}</td>
                <td>🪙 {{ p.coin_price }}</td>
                <td>
                  <button class="btn-sm" @click="toggleStatus(p)">重新上架</button>
                  <button class="btn-sm btn-danger" @click="deleteProduct(p)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="state.formVisible" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ state.editingId ? '编辑商品' : '新增商品' }}</h3>
          <button class="close-btn" @click="closeForm">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <label>名称</label>
            <input v-model="state.form.name" placeholder="商品名称" />
          </div>

          <div class="form-row">
            <label>分类</label>
            <div class="as-inline">
              <select v-model="state.form.category">
                <option v-for="c in state.categories" :key="c.value" :value="c.value">{{ c.label }}</option>
              </select>
              <button class="btn-sm" type="button" @click="addOption('category')">+ 新增类型</button>
            </div>
          </div>

          <div class="form-row">
            <label>金币价</label>
            <input v-model.number="state.form.coin_price" type="number" min="1" placeholder="管理员自定义" />
          </div>
          <div class="form-row">
            <label>库存</label>
            <input v-model.number="state.form.stock" type="number" placeholder="-1 表示不限" />
          </div>

          <div class="form-row">
            <label>商品图</label>
            <div class="as-upload">
              <img
                v-if="state.form.image_url && isImageUrl(state.form.image_url)"
                :src="state.form.image_url"
                class="as-upload-preview"
                alt=""
              />
              <div v-else class="as-upload-preview as-upload-empty">未上传</div>
              <div class="as-upload-side">
                <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onPickImage" />
                <button class="btn-sm" type="button" :disabled="state.uploading" @click="pickImage">
                  {{ state.uploading ? '处理中…' : '上传照片（自动抠像）' }}
                </button>
                <p class="as-hint">系统会自动抠像并合成白底；照片模糊或尺寸过小会被要求重传。</p>
              </div>
            </div>
          </div>

          <div class="form-row">
            <label>描述</label>
            <textarea v-model="state.form.description" rows="2"></textarea>
          </div>

          <div class="form-row">
            <label>权益类型</label>
            <div class="as-inline">
              <select v-model="state.form.deliverable_type">
                <option v-for="t in state.deliverableTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
              <button class="btn-sm" type="button" @click="addOption('deliverable_type')">+ 新增类型</button>
            </div>
            <p class="as-hint">
              权益类型决定兑换后系统怎么发东西：称号→写入我的称号；头像框→套在头像上；
              卡密→发一串兑换码；人工处理→订单进入待发货/待开通。
            </p>
          </div>

          <div class="form-row">
            <label>权益参数（选填）</label>
            <textarea
              v-model="state.form.deliverable_payload_text"
              rows="2"
              placeholder='例如 {"title_id": 12} 或 {"frame": "gold_badge"}'
            ></textarea>
            <p class="as-hint">
              这是一段 JSON，用来告诉系统"发哪一个"权益。称号填 <code>title_id</code>，
              头像框填 <code>frame</code>；卡密/人工处理类商品不需要填。
            </p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-primary" @click="saveForm">保存</button>
          <button class="btn-plain" @click="closeForm">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { ElMessage } from 'element-plus';
  import { useProvider } from '@vtj/renderer';

  export default defineComponent({
    name: 'AdminShop',
    setup(props) {
      const provider = useProvider({ id: 'admin_shop', version: '20260918001' });
      const state = reactive({
        products: [],
        categories: [],
        deliverableTypes: [],
        showOffShelf: false,
        formVisible: false,
        editingId: null,
        uploading: false,
        form: {
          name: '',
          category: '',
          coin_price: 0,
          stock: -1,
          image_url: '',
          description: '',
          deliverable_type: 'title',
          deliverable_payload_text: ''
        }
      });
      return { state, props, provider };
    },
    computed: {
      onSaleProducts() {
        return this.state.products.filter((p) => p.status === 'on_sale');
      },
      offShelfProducts() {
        return this.state.products.filter((p) => p.status !== 'on_sale');
      }
    },
    async mounted() {
      await this.loadOptions();
      await this.loadList();
    },
    methods: {
      api(url, opt) {
        return window.__VTJ_AUTH__.apiFetch(url, opt);
      },
      isImageUrl(v) {
        return typeof v === 'string' && /^(\/|https?:\/\/)/.test(v);
      },
      deliverableLabel(type) {
        const hit = this.state.deliverableTypes.find((t) => t.value === type);
        return hit ? hit.label : type || '—';
      },
      async loadOptions() {
        try {
          const [cat, dt] = await Promise.all([
            this.api('/api/admin/shop/options?kind=category'),
            this.api('/api/admin/shop/options?kind=deliverable_type')
          ]);
          const catBody = await cat.json();
          const dtBody = await dt.json();
          this.state.categories = catBody.items || [];
          this.state.deliverableTypes = dtBody.items || [];
        } catch (e) {
          ElMessage.error('加载选项失败');
        }
      },
      async addOption(kind) {
        const label = window.prompt(kind === 'category' ? '新增商品分类名称' : '新增权益类型名称');
        if (!label || !label.trim()) return;
        const r = await this.api('/api/admin/shop/options', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind, value: label.trim() })
        });
        const d = await r.json();
        if (!r.ok) {
          ElMessage.error(d.detail || '新增失败');
          return;
        }
        await this.loadOptions();
        if (kind === 'category') this.state.form.category = label.trim();
        else this.state.form.deliverable_type = label.trim();
        ElMessage.success('已新增');
      },
      async loadList() {
        try {
          const r = await this.api('/api/admin/shop/products?page_size=100');
          const d = await r.json();
          if (r.ok) this.state.products = d.items || [];
        } catch (e) {
          ElMessage.error(e.message);
        }
      },
      openCreate() {
        this.state.editingId = null;
        this.state.form = {
          name: '',
          category: this.state.categories[0] ? this.state.categories[0].value : '',
          coin_price: 0,
          stock: -1,
          image_url: '',
          description: '',
          deliverable_type: 'title',
          deliverable_payload_text: ''
        };
        this.state.formVisible = true;
      },
      openEdit(p) {
        this.state.editingId = p.id;
        this.state.form = {
          name: p.name,
          category: p.category,
          coin_price: p.coin_price,
          stock: p.stock,
          image_url: p.image_url || '',
          description: p.description || '',
          deliverable_type: p.deliverable_type || 'manual',
          deliverable_payload_text: p.deliverable_payload ? JSON.stringify(p.deliverable_payload) : ''
        };
        this.state.formVisible = true;
      },
      closeForm() {
        this.state.formVisible = false;
      },
      openOffShelf() {
        this.state.showOffShelf = true;
      },
      pickImage() {
        if (this.$refs.fileInput) this.$refs.fileInput.click();
      },
      async onPickImage(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        this.state.uploading = true;
        try {
          const fd = new FormData();
          fd.append('file', file);
          const r = await this.api('/api/admin/shop/upload-image', { method: 'POST', body: fd });
          const d = await r.json();
          if (!r.ok) {
            ElMessage.error(d.detail || '图片处理失败，请重新上传');
            return;
          }
          this.state.form.image_url = d.url;
          if (this.state.editingId) {
            await this.api('/api/admin/shop/products/' + this.state.editingId, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ image_url: d.url })
            });
            ElMessage.success('图片已抠像并保存（清晰度 ' + d.sharpness + '）');
          } else {
            ElMessage.success('图片已处理：自动抠像 + 白底（清晰度 ' + d.sharpness + '），请点击保存商品');
          }
        } catch (e) {
          ElMessage.error(e.message || '上传失败');
        } finally {
          this.state.uploading = false;
          ev.target.value = '';
        }
      },
      async saveForm() {
        const f = this.state.form;
        if (!f.name) {
          ElMessage.warning('名称必填');
          return;
        }
        if (!f.coin_price || f.coin_price < 1) {
          ElMessage.warning('请填写金币价');
          return;
        }
        let payload = null;
        if (f.deliverable_payload_text) {
          try {
            payload = JSON.parse(f.deliverable_payload_text);
          } catch (e) {
            ElMessage.warning('权益参数不是合法 JSON');
            return;
          }
        }
        const body = {
          name: f.name,
          category: f.category,
          coin_price: f.coin_price,
          stock: f.stock,
          image_url: f.image_url,
          description: f.description,
          deliverable_type: f.deliverable_type,
          deliverable_payload: payload
        };
        try {
          const isEdit = this.state.editingId != null;
          const url = isEdit
            ? '/api/admin/shop/products/' + this.state.editingId
            : '/api/admin/shop/products';
          const r = await this.api(url, {
            method: isEdit ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          const d = await r.json();
          if (r.ok) {
            ElMessage.success('已保存');
            this.closeForm();
            this.loadList();
          } else {
            ElMessage.error(d.detail || '保存失败');
          }
        } catch (e) {
          ElMessage.error(e.message);
        }
      },
      async toggleStatus(p) {
        try {
          const r = await this.api('/api/admin/shop/products/' + p.id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: p.status === 'on_sale' ? 'off_shelf' : 'on_sale' })
          });
          const d = await r.json();
          if (r.ok) {
            ElMessage.success('已更新');
            this.loadList();
          } else {
            ElMessage.error(d.detail || '操作失败');
          }
        } catch (e) {
          ElMessage.error(e.message);
        }
      },
      async deleteProduct(p) {
        if (!window.confirm('确认删除商品「' + p.name + '」？')) return;
        try {
          const r = await this.api('/api/admin/shop/products/' + p.id, { method: 'DELETE' });
          const d = await r.json();
          if (r.ok) {
            ElMessage.success('已删除');
            this.loadList();
          } else {
            ElMessage.error(d.detail || '删除失败');
          }
        } catch (e) {
          ElMessage.error(e.message);
        }
      }
    }
  });
</script>

<style scoped>
  .admin-shop-page {
    padding: 20px;
  }
  .as-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .as-header h2 {
    margin: 0;
    font-size: 20px;
    color: #1a2b5f;
  }
  .as-head-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .as-offshelf-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .as-count {
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    border-radius: 9px;
    background: #e5e7eb;
    color: #4b5563;
    font-size: 12px;
    line-height: 18px;
    text-align: center;
  }
  .as-table-wrap {
    background: #fff;
    border-radius: 12px;
    overflow: auto;
    padding: 8px;
  }
  .as-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  .as-table th,
  .as-table td {
    padding: 10px 8px;
    text-align: left;
    border-bottom: 1px solid #f0f2f5;
  }
  .as-table th {
    color: #6b7280;
    font-weight: 600;
  }
  .as-thumb {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    object-fit: cover;
    border: 1px solid #eef2f7;
    background: #fff;
  }
  .as-thumb-emoji {
    font-size: 22px;
  }
  .status-tag {
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 12px;
  }
  .status-tag.on_sale {
    background: #dcfce7;
    color: #16a34a;
  }
  .as-empty {
    padding: 32px;
    text-align: center;
    color: #9ca3af;
    font-size: 13px;
  }
  .btn-sm {
    padding: 5px 10px;
    margin-right: 6px;
    border-radius: 8px;
    border: 1px solid #dbeafe;
    background: #eff6ff;
    color: #1d4ed8;
    font-size: 12px;
    cursor: pointer;
  }
  .btn-danger {
    border-color: #fecaca;
    background: #fef2f2;
    color: #b91c1c;
  }
  .btn-primary {
    padding: 8px 16px;
    border-radius: 10px;
    border: none;
    background: #1a2b5f;
    color: #fff;
    cursor: pointer;
  }
  .btn-plain {
    padding: 8px 16px;
    border-radius: 10px;
    border: 1px solid #e5e7eb;
    background: #fff;
    cursor: pointer;
  }
  .modal-mask {
    position: fixed;
    inset: 0;
    background: rgba(17, 24, 39, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }
  .modal {
    width: min(680px, 94vw);
    max-height: 88vh;
    display: flex;
    flex-direction: column;
    background: #fff;
    border-radius: 14px;
    overflow: hidden;
  }
  .as-offshelf-modal {
    width: min(820px, 94vw);
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid #eef2f7;
  }
  .modal-header h3 {
    margin: 0;
    font-size: 16px;
  }
  .close-btn {
    border: none;
    background: #f3f4f6;
    border-radius: 8px;
    width: 28px;
    height: 28px;
    cursor: pointer;
  }
  .modal-body {
    padding: 14px 18px;
    overflow-y: auto;
  }
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 12px 18px;
    border-top: 1px solid #eef2f7;
  }
  .form-row {
    margin-bottom: 12px;
  }
  .form-row > label {
    display: block;
    margin-bottom: 6px;
    font-size: 13px;
    color: #4b5563;
  }
  .form-row input,
  .form-row select,
  .form-row textarea {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid #dfe3ea;
    border-radius: 8px;
    font-size: 13px;
  }
  .as-inline {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .as-inline select {
    flex: 1;
  }
  .as-hint {
    margin: 6px 0 0;
    font-size: 12px;
    color: #9ca3af;
    line-height: 1.6;
  }
  .as-upload {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }
  .as-upload-preview {
    width: 96px;
    height: 96px;
    border-radius: 10px;
    object-fit: cover;
    border: 1px solid #eef2f7;
    background: #fff;
  }
  .as-upload-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9ca3af;
    font-size: 12px;
  }
  .as-upload-side {
    flex: 1;
  }
</style>
