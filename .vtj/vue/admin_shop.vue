<!-- 金币商城商品管理（管理员端） -->
<template>
  <div class="admin-shop-page">
    <div class="as-header">
      <h2>金币商城商品管理</h2>
      <button class="btn-primary" @click="openCreate">+ 新增商品</button>
    </div>

    <div class="as-table-wrap">
      <table class="as-table">
        <thead>
          <tr>
            <th>ID</th><th>名称</th><th>分类</th><th>金币价</th><th>库存</th><th>权益类型</th><th>状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in state.products" :key="p.id">
            <td>{{ p.id }}</td>
            <td>{{ p.name }}</td>
            <td>{{ p.category }}</td>
            <td>🪙 {{ p.coin_price }}</td>
            <td>{{ p.stock === -1 ? '不限' : p.stock }}</td>
            <td>{{ p.deliverable_type }}</td>
            <td>
              <span :class="['status-tag', p.status]">{{ p.status === 'on_sale' ? '上架' : '下架' }}</span>
            </td>
            <td>
              <button class="btn-sm" @click="openEdit(p)">编辑</button>
              <button class="btn-sm" @click="toggleStatus(p)">{{ p.status === 'on_sale' ? '下架' : '上架' }}</button>
              <button class="btn-sm btn-danger" @click="deleteProduct(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="!state.products.length" class="as-empty">暂无商品</div>
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
            <select v-model="state.form.category">
              <option value="限定称号">限定称号</option>
              <option value="专属头像框">专属头像框</option>
            </select>
          </div>
          <div class="form-row">
            <label>金币价</label>
            <input v-model.number="state.form.coin_price" type="number" />
          </div>
          <div class="form-row">
            <label>库存</label>
            <input v-model.number="state.form.stock" type="number" placeholder="-1 表示不限" />
          </div>
          <div class="form-row">
            <label>图标</label>
            <input v-model="state.form.image_url" placeholder="emoji 或图片 URL" />
          </div>
          <div class="form-row">
            <label>描述</label>
            <textarea v-model="state.form.description" rows="3"></textarea>
          </div>
          <div class="form-row">
            <label>权益类型</label>
            <select v-model="state.form.deliverable_type">
              <option value="title">称号(title)</option>
              <option value="avatar_frame">头像框(avatar_frame)</option>
            </select>
          </div>
          <div class="form-row">
            <label>权益参数JSON</label>
            <textarea v-model="state.form.deliverable_payload_text" rows="2" placeholder='如 {"title_id":1} 或 {"frame_id":"gold_badge"}'></textarea>
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
        formVisible: false,
        editingId: null,
        form: {
          name: '', category: '限定称号', coin_price: 0, stock: -1,
          image_url: '', description: '', deliverable_type: 'title', deliverable_payload_text: ''
        }
      });
      return { state, props, provider };
    },
    methods: {
      api(url, opt) { return window.__VTJ_AUTH__.apiFetch(url, opt); },
      async loadList() {
        try {
          const r = await this.api('/api/admin/shop/products?page_size=100');
          const d = await r.json();
          if (r.ok) this.state.products = d.items || [];
        } catch (e) { ElMessage.error(e.message); }
      },
      openCreate() {
        this.state.editingId = null;
        this.state.form = {
          name: '', category: '限定称号', coin_price: 0, stock: -1,
          image_url: '', description: '', deliverable_type: 'title', deliverable_payload_text: ''
        };
        this.state.formVisible = true;
      },
      openEdit(p) {
        this.state.editingId = p.id;
        this.state.form = {
          name: p.name, category: p.category, coin_price: p.coin_price, stock: p.stock,
          image_url: p.image_url || '', description: p.description || '',
          deliverable_type: p.deliverable_type || 'title',
          deliverable_payload_text: p.deliverable_payload ? JSON.stringify(p.deliverable_payload) : ''
        };
        this.state.formVisible = true;
      },
      closeForm() { this.state.formVisible = false; },
      async saveForm() {
        const f = this.state.form;
        if (!f.name) { ElMessage.warning('名称必填'); return; }
        let payload = null;
        if (f.deliverable_payload_text) {
          try { payload = JSON.parse(f.deliverable_payload_text); }
          catch (e) { ElMessage.warning('权益参数不是合法 JSON'); return; }
        }
        const body = {
          name: f.name, category: f.category, coin_price: f.coin_price, stock: f.stock,
          image_url: f.image_url, description: f.description,
          deliverable_type: f.deliverable_type, deliverable_payload: payload
        };
        try {
          const isEdit = this.state.editingId != null;
          const r = await this.api(isEdit ? '/api/admin/shop/products/' + this.state.editingId : '/api/admin/shop/products', {
            method: isEdit ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          const d = await r.json();
          if (r.ok) { ElMessage.success('已保存'); this.closeForm(); this.loadList(); }
          else ElMessage.error(d.detail || '保存失败');
        } catch (e) { ElMessage.error(e.message); }
      },
      async toggleStatus(p) {
        try {
          const r = await this.api('/api/admin/shop/products/' + p.id, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: p.status === 'on_sale' ? 'off_shelf' : 'on_sale' })
          });
          const d = await r.json();
          if (r.ok) { ElMessage.success('已更新'); this.loadList(); }
          else ElMessage.error(d.detail || '操作失败');
        } catch (e) { ElMessage.error(e.message); }
      },
      async deleteProduct(p) {
        if (!window.confirm('确认删除商品「' + p.name + '」？')) return;
        try {
          const r = await this.api('/api/admin/shop/products/' + p.id, { method: 'DELETE' });
          const d = await r.json();
          if (r.ok) { ElMessage.success('已删除'); this.loadList(); }
          else ElMessage.error(d.detail || '删除失败');
        } catch (e) { ElMessage.error(e.message); }
      }
    },
    mounted() { this.loadList(); }
  });
</script>

<style lang="css" scoped>
  .admin-shop-page { padding: 20px 24px; font-family: 'Noto Sans SC', sans-serif; background: #f5f6fa; min-height: 100vh; }
  .as-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .as-header h2 { margin: 0; font-size: 20px; color: #1a2b5f; }
  .btn-primary { padding: 8px 16px; background: #1a2b5f; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; }
  .btn-plain { padding: 8px 16px; background: #e5e7eb; color: #333; border: none; border-radius: 8px; cursor: pointer; }
  .btn-sm { padding: 4px 10px; background: #3b82f6; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; margin-right: 4px; }
  .btn-danger { background: #ef4444; }
  .as-table-wrap { background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.04); }
  .as-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .as-table th, .as-table td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #f0f0f0; }
  .as-table th { background: #fafafa; color: #6b7280; font-weight: 600; }
  .status-tag { padding: 3px 8px; border-radius: 6px; font-size: 12px; }
  .status-tag.on_sale { background: #dcfce7; color: #16a34a; }
  .status-tag.off_shelf { background: #f3f4f6; color: #9ca3af; }
  .as-empty { text-align: center; color: #9ca3af; padding: 40px 0; }
  .modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
  .modal { background: #fff; border-radius: 14px; width: 480px; max-width: 92vw; padding: 22px; max-height: 90vh; overflow-y: auto; }
  .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  .modal-header h3 { margin: 0; font-size: 17px; color: #1a2b5f; }
  .close-btn { background: none; border: none; font-size: 16px; cursor: pointer; color: #6b7280; }
  .form-row { display: flex; flex-direction: column; margin-bottom: 12px; }
  .form-row label { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
  .form-row input, .form-row select, .form-row textarea {
    padding: 8px 10px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 13px; font-family: inherit;
  }
  .modal-footer { display: flex; gap: 10px; margin-top: 16px; }
</style>
