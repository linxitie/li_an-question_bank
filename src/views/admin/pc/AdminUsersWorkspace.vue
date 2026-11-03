<template>
  <div class="au-page">
    <header class="au-head">
      <div>
        <h1>用户与权限</h1>
        <p>用户生命周期、角色与权限覆盖在同一工作台完成；权限模板、授权审计与健康扫描保留为独立视图。</p>
      </div>
      <div class="au-head-actions">
        <button type="button" class="au-btn ghost" :disabled="loading" @click="loadAll">刷新</button>
        <button type="button" class="au-btn primary" @click="openCreate">+ 新建用户</button>
      </div>
    </header>

    <div v-if="error" class="au-alert" role="alert">
      <span>{{ error }}</span>
      <button type="button" @click="loadAll">重试</button>
    </div>

    <nav class="au-tabs" aria-label="用户与权限视图">
      <button v-for="item in tabs" :key="item.key" type="button"
              :class="{ active: tab === item.key }" @click="switchTab(item.key)">
        {{ item.label }}
        <span v-if="item.key === 'users' && stats.deleted" class="au-badge">{{ stats.deleted }}</span>
      </button>
    </nav>

    <!-- 用户列表 -->
    <section v-if="tab === 'users'" class="au-tab-body">
      <div class="au-stats">
        <article><span>有效用户</span><strong>{{ stats.total }}</strong><small>不含回收站</small></article>
        <article><span>学生</span><strong>{{ stats.student }}</strong><small>可登录账号</small></article>
        <article><span>教师</span><strong>{{ stats.teacher }}</strong><small>教学与阅卷</small></article>
        <article><span>管理员</span><strong>{{ stats.admin }}</strong><small>后台账号</small></article>
        <article><span>停用 / 回收站</span><strong>{{ stats.disabled }} / {{ stats.deleted }}</strong><small>覆盖授权 {{ stats.with_override }} 人</small></article>
      </div>

      <div class="au-toolbar">
        <input v-model.trim="keyword" class="au-input search" placeholder="搜索用户名 / 编号 / 手机号"
               @keyup.enter="reloadUsers" />
        <select v-model="filters.user_type" class="au-input" @change="reloadUsers">
          <option value="">全部角色</option>
          <option value="student">学生</option>
          <option value="teacher">教师</option>
          <option value="admin">管理员</option>
        </select>
        <select v-model="filters.role_level" class="au-input" @change="reloadUsers">
          <option value="">全部级别</option>
          <option value="0">0 学生</option>
          <option value="1">1 教师</option>
          <option value="2">2 管理员</option>
          <option value="3">3 超级管理员</option>
        </select>
        <select v-model="filters.is_disabled" class="au-input" @change="reloadUsers">
          <option value="">全部状态</option>
          <option value="0">正常</option>
          <option value="1">停用</option>
        </select>
        <select v-model="filters.has_override" class="au-input" @change="reloadUsers">
          <option value="">权限覆盖：全部</option>
          <option value="1">有个人覆盖</option>
          <option value="0">无个人覆盖</option>
        </select>
        <select v-model="filters.sort" class="au-input" @change="reloadUsers">
          <option value="register_time_desc">最新注册</option>
          <option value="last_login_desc">最近登录</option>
          <option value="username_asc">用户名 A→Z</option>
        </select>
        <button type="button" class="au-btn" @click="resetFilters">重置</button>
        <label class="au-switch">
          <input v-model="includeDeleted" type="checkbox" @change="reloadUsers" />
          <span>回收站</span>
        </label>
      </div>

      <div v-if="selectedIds.length" class="au-batchbar">
        <span>已选 <strong>{{ selectedIds.length }}</strong> 人</span>
        <template v-if="!includeDeleted">
          <button type="button" class="au-btn" @click="openBatch('disable')">批量停用</button>
          <button type="button" class="au-btn" @click="openBatch('enable')">批量启用</button>
          <button type="button" class="au-btn danger" @click="openBatch('delete')">批量移入回收站</button>
        </template>
        <template v-else>
          <button type="button" class="au-btn primary" @click="openBatch('restore')">批量恢复</button>
          <button v-if="isSuper" type="button" class="au-btn danger"
                  @click="openBatch('purge')">批量彻底删除</button>
        </template>
        <button type="button" class="au-link" @click="selectedIds = []">取消选择</button>
      </div>

      <div class="au-table-wrap">
        <table class="au-table">
          <thead>
            <tr>
              <th class="check"><input type="checkbox" :checked="allChecked" @change="toggleAll" /></th>
              <th>用户</th>
              <th>角色</th>
              <th>院系 / 班级</th>
              <th>联系方式</th>
              <th>状态</th>
              <th>个人覆盖</th>
              <th>最近登录</th>
              <th class="actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.user_id" :class="{ muted: user.is_deleted }">
              <td class="check">
                <input type="checkbox" :value="user.user_id" v-model="selectedIds" />
              </td>
              <td>
                <div class="au-user">
                  <button type="button" class="au-avatar"
                          :class="{ 'has-photo': user.avatar && !isAvatarBroken(user) }"
                          :aria-label="'查看 ' + (user.username || '用户') + ' 的资料'"
                          @click="openAvatar(user)">
                    <img v-if="user.avatar && !isAvatarBroken(user)" :src="user.avatar"
                         :alt="(user.username || '用户') + ' 头像'" loading="lazy"
                         @error="markAvatarBroken(user)" />
                    <span v-else>{{ avatarInitial(user) }}</span>
                  </button>
                  <div>
                    <strong>{{ user.username }}</strong>
                    <small>#{{ user.user_id }} · {{ user.user_no }}</small>
                  </div>
                </div>
              </td>
              <td>
                <span class="au-chip role" :class="user.user_type">{{ roleLabel(user) }}</span>
              </td>
              <td>
                <div class="au-two-line">
                  <span>{{ user.department || '—' }}</span>
                  <small>{{ user.class_name || user.school || '' }}</small>
                </div>
              </td>
              <td>
                <div class="au-two-line">
                  <span>{{ user.phone || '—' }}</span>
                  <small>{{ user.email || '' }}</small>
                </div>
              </td>
              <td>
                <span v-if="user.is_deleted" class="au-chip bad">回收站</span>
                <span v-else-if="user.is_disabled" class="au-chip warn">停用</span>
                <span v-else class="au-chip ok">正常</span>
              </td>
              <td>{{ user.override_count || 0 }} 项</td>
              <td class="au-time">{{ formatTime(user.last_login) }}</td>
              <td class="actions">
                <template v-if="!user.is_deleted">
                  <button type="button" class="au-link" @click="openEdit(user)">编辑</button>
                  <button type="button" class="au-link" @click="openPermissions(user)">权限</button>
                  <button v-if="user.user_id !== meId" type="button" class="au-link"
                          @click="toggleDisabled(user)">{{ user.is_disabled ? '启用' : '停用' }}</button>
                  <button v-if="isSuper && user.user_id !== meId" type="button" class="au-link"
                          @click="resetPassword(user)">重置密码</button>
                  <button v-if="user.user_id !== meId" type="button" class="au-link danger"
                          @click="deleteUser(user)">删除</button>
                </template>
                <template v-else>
                  <button type="button" class="au-link" @click="restoreUser(user)">恢复</button>
                  <button v-if="isSuper" type="button" class="au-link danger" @click="purgeUser(user)">彻底注销</button>
                </template>
              </td>
            </tr>
            <tr v-if="!users.length && !loading">
              <td colspan="9" class="au-empty">{{ includeDeleted ? '回收站为空' : '没有匹配的用户' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="au-pager">
        <span>共 {{ total }} 人</span>
        <button type="button" class="au-btn" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button type="button" class="au-btn" :disabled="page >= totalPages" @click="goPage(page + 1)">下一页</button>
      </footer>
    </section>

    <!-- 权限模板 -->
    <section v-if="tab === 'templates'" class="au-tab-body">
      <div class="au-template-head">
        <div class="au-segmented" role="group" aria-label="角色模板">
          <button v-for="role in roleOrder" :key="role" type="button"
                  :class="{ active: templateRole === role }" @click="selectTemplateRole(role)">
            {{ roleName(role) }}
          </button>
        </div>
        <p>模板决定角色默认权限；个人加授/拒绝仍优先于模板，权限覆盖见用户抽屉。</p>
      </div>
      <div class="au-template-grid">
        <article v-for="group in catalogGroups" :key="group.name" class="au-template-group">
          <h3>{{ group.name }} <small>{{ group.permissions.length }} 项</small></h3>
          <label v-for="perm in group.permissions" :key="perm.code" class="au-perm-check"
                 :class="{ locked: isProtected(perm.code) }">
            <input type="checkbox" :value="perm.code" v-model="templateCodes"
                   :disabled="isProtected(perm.code)" />
            <span>
              {{ perm.label }}
              <em v-if="perm.risk === 'critical'" class="risk">关键</em>
              <small>{{ perm.code }}</small>
            </span>
          </label>
        </article>
      </div>
      <div class="au-savebar">
        <input v-model.trim="templateReason" class="au-input" placeholder="变更原因（必填，至少 2 字）" />
        <button type="button" class="au-btn primary" :disabled="saving" @click="saveTemplate">
          {{ saving ? '保存中…' : '保存模板' }}
        </button>
      </div>
    </section>

    <!-- 授权审计 -->
    <section v-if="tab === 'audit'" class="au-tab-body">
      <div class="au-toolbar">
        <select v-model="auditAction" class="au-input" @change="loadAudit(1)">
          <option value="">全部动作</option>
          <option value="single_user_permissions">单用户权限</option>
          <option value="batch_user_permissions">批量权限</option>
          <option value="role_template_update">角色模板</option>
        </select>
        <button type="button" class="au-btn" @click="loadAudit(1)">刷新</button>
      </div>
      <div class="au-table-wrap">
        <table class="au-table">
          <thead><tr><th>时间</th><th>操作者</th><th>动作</th><th>目标</th><th>原因</th><th>批次</th><th>状态</th><th class="actions">操作</th></tr></thead>
          <tbody>
            <tr v-for="row in auditRows" :key="row.batch_id">
              <td class="au-time">{{ formatTime(row.created_at) }}</td>
              <td>{{ row.operator || ('#' + row.operator_id) }}</td>
              <td>{{ actionLabel(row.action) }}</td>
              <td>{{ row.target_count }}</td>
              <td class="au-reason">{{ row.reason }}</td>
              <td class="au-mono">{{ row.batch_id.slice(0, 8) }}</td>
              <td>
                <span v-if="row.undone_at" class="au-chip">已撤销</span>
                <span v-else-if="row.can_undo" class="au-chip ok">可撤销</span>
                <span v-else class="au-chip">已过期</span>
              </td>
              <td class="actions">
                <button v-if="row.can_undo" type="button" class="au-link danger" @click="undoBatch(row)">撤销</button>
              </td>
            </tr>
            <tr v-if="!auditRows.length"><td colspan="8" class="au-empty">暂无授权记录</td></tr>
          </tbody>
        </table>
      </div>
      <footer class="au-pager">
        <span>共 {{ auditTotal }} 条</span>
        <button type="button" class="au-btn" :disabled="auditPage <= 1" @click="loadAudit(auditPage - 1)">上一页</button>
        <span>{{ auditPage }}</span>
        <button type="button" class="au-btn" :disabled="auditRows.length < 20" @click="loadAudit(auditPage + 1)">下一页</button>
      </footer>
    </section>

    <!-- 权限健康 -->
    <section v-if="tab === 'health'" class="au-tab-body">
      <div class="au-health-head">
        <p>扫描最后超管、过期授权、孤儿覆盖与保护权限异常。</p>
        <button type="button" class="au-btn primary" :disabled="loading" @click="loadHealth">重新扫描</button>
      </div>
      <div class="au-stats health">
        <article><span>有效用户</span><strong>{{ health.stats.active_users }}</strong><small>未删除</small></article>
        <article><span>超级管理员</span><strong>{{ health.stats.super_admins }}</strong><small>可用账号</small></article>
        <article><span>生效覆盖</span><strong>{{ health.stats.active_overrides }}</strong><small>个人加授/拒绝</small></article>
        <article><span>7 天内到期</span><strong>{{ health.stats.expiring_7d }}</strong><small>需续期</small></article>
        <article><span>异常</span><strong>{{ health.alerts.length }}</strong><small>见下方提示</small></article>
      </div>
      <ul class="au-alerts">
        <li v-for="alert in health.alerts" :key="alert.code" :class="alert.level">
          <strong>{{ alert.message }}</strong>
          <small>{{ alert.code }}</small>
        </li>
        <li v-if="!health.alerts.length" class="ok">未发现异常。</li>
      </ul>
    </section>

    <!-- 用户编辑 -->
    <div v-if="editorVisible" class="au-modal-mask" @click.self="closeEditor">
      <section class="au-modal wide" role="dialog" aria-modal="true" aria-label="编辑用户">
        <header>
          <h2>{{ editorMode === 'create' ? '新建用户' : '编辑用户 · ' + editor.username }}</h2>
          <button type="button" class="au-close" aria-label="关闭" @click="closeEditor">×</button>
        </header>
        <div class="au-form-grid">
          <label>用户名<input v-model.trim="editor.username" class="au-input" /></label>
          <label>编号 / 学号<input v-model.trim="editor.user_no" class="au-input" :disabled="editorMode === 'edit'" /></label>
          <label v-if="editorMode === 'create'">初始密码<input v-model="editor.password" type="password" class="au-input" /></label>
          <label>用户类型
            <select v-model="editor.user_type" class="au-input" :disabled="!isSuper && editorMode === 'edit'">
              <option value="student">学生</option><option value="teacher">教师</option><option value="admin">管理员</option>
            </select>
          </label>
          <label>权限级别
            <select v-model.number="editor.role_level" class="au-input" :disabled="!isSuper && editorMode === 'edit'">
              <option :value="0">0 学生</option><option :value="1">1 教师</option>
              <option :value="2">2 管理员</option><option :value="3">3 超级管理员</option>
            </select>
          </label>
          <label>手机号<input v-model.trim="editor.phone" class="au-input" /></label>
          <label>邮箱<input v-model.trim="editor.email" class="au-input" /></label>
          <label>性别
            <select v-model="editor.gender" class="au-input"><option>未知</option><option>男</option><option>女</option></select>
          </label>
          <label>院系<input v-model.trim="editor.department" class="au-input" /></label>
          <label>班级<input v-model.trim="editor.class_name" class="au-input" /></label>
          <label class="span-2">学校<input v-model.trim="editor.school" class="au-input" /></label>
          <label v-if="editorMode === 'edit' && isSuper" class="span-2">角色变更原因
            <input v-model.trim="roleReason" class="au-input" placeholder="修改角色必须填写原因" />
          </label>
        </div>
        <footer>
          <button type="button" class="au-btn" @click="closeEditor">取消</button>
          <button type="button" class="au-btn primary" :disabled="saving" @click="saveEditor">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </footer>
      </section>
    </div>

    <!-- 权限矩阵 -->
    <div v-if="permissionVisible" class="au-modal-mask" @click.self="closePermissions">
      <section class="au-modal wide permission-modal" role="dialog" aria-modal="true" aria-label="用户权限">
        <header>
          <h2>权限矩阵 · {{ permissionUser.username }}</h2>
          <button type="button" class="au-close" aria-label="关闭" @click="closePermissions">×</button>
        </header>
        <div class="au-perm-summary">
          <span>角色基线 {{ permissionDetail.baseline_permissions.length }} 项</span>
          <span>能力包 {{ permissionDetail.capability_permissions.length }} 项</span>
          <span>个人加授 {{ permissionDetail.granted_permissions.length }} 项</span>
          <span>个人拒绝 {{ permissionDetail.denied_permissions.length }} 项</span>
          <span>有效 {{ permissionDetail.effective_permissions.length }} 项</span>
        </div>
        <div class="au-perm-body">
          <article v-for="group in catalogGroups" :key="group.name" class="au-perm-group">
            <h3>{{ group.name }}</h3>
            <div v-for="perm in group.permissions" :key="perm.code" class="au-perm-row">
              <div class="au-perm-name">
                <strong>{{ perm.label }}</strong>
                <small>{{ perm.code }}<em v-if="perm.risk === 'critical'" class="risk">关键</em></small>
              </div>
              <div class="au-tristate" role="group" :aria-label="perm.label">
                <button type="button" :class="{ on: permState(perm.code) === 'inherit' }"
                        @click="setPerm(perm.code, 'inherit')">继承</button>
                <button type="button" :class="{ on: permState(perm.code) === 'grant' }"
                        @click="setPerm(perm.code, 'grant')">加授</button>
                <button type="button" :class="{ on: permState(perm.code) === 'deny' }"
                        @click="setPerm(perm.code, 'deny')">拒绝</button>
              </div>
            </div>
          </article>
        </div>
        <footer>
          <input v-model.trim="permReason" class="au-input" placeholder="变更原因（必填，至少 2 字）" />
          <button type="button" class="au-btn" @click="closePermissions">取消</button>
          <button type="button" class="au-btn primary" :disabled="saving" @click="savePermissions">
            {{ saving ? '保存中…' : '保存权限' }}
          </button>
        </footer>
      </section>
    </div>

    <!-- 批量操作 -->
    <div v-if="batchVisible" class="au-modal-mask" @click.self="batchVisible = false">
      <section class="au-modal" role="dialog" aria-modal="true" aria-label="批量操作">
        <header><h2>批量{{ actionLabel(batchAction) }} · {{ selectedIds.length }} 人</h2>
          <button type="button" class="au-close" aria-label="关闭" @click="batchVisible = false">×</button>
        </header>
        <p v-if="batchAction === 'purge'" class="au-modal-hint danger-hint">
          彻底删除会匿名化账号并清除手机、邮箱、头像与权限，历史题目/考试记录保留但不可恢复。
        </p>
        <p v-else class="au-modal-hint">服务端会重新校验数量与越级关系；包含本人或同级账号时整批拒绝。</p>
        <div v-if="batchAction === 'purge'" class="au-impact" role="status">
          <span>已选 <strong>{{ selectedIds.length }}</strong> 人</span>
          <span>其中管理员 <strong>{{ selectedAdminCount }}</strong> 人</span>
          <span class="au-impact-danger">不可恢复</span>
        </div>
        <label v-if="batchAction !== 'restore'">原因
          <input v-model.trim="batchReason" class="au-input" placeholder="至少 2 字，将写入审计" />
        </label>
        <label v-if="batchAction === 'purge'">输入「彻底删除」确认
          <input v-model.trim="batchConfirm" class="au-input" autocomplete="off"
                 placeholder="彻底删除" />
        </label>
        <footer>
          <button type="button" class="au-btn" @click="batchVisible = false">取消</button>
          <button type="button" class="au-btn primary" :disabled="saving || !batchReady" @click="submitBatch">
            {{ saving ? '执行中…' : (batchAction === 'purge' ? '确认彻底删除' : '确认执行') }}
          </button>
        </footer>
      </section>
    </div>

    <!-- 头像资料卡 -->
    <div v-if="avatarUser" class="au-modal-mask" @click.self="avatarUser = null">
      <section class="au-modal au-avatar-modal" role="dialog" aria-modal="true"
               aria-label="用户资料卡">
        <header><h2>用户资料</h2>
          <button type="button" class="au-close" aria-label="关闭" @click="avatarUser = null">×</button>
        </header>
        <div class="au-avatar-card">
          <div class="au-avatar au-avatar-xl" :class="{ 'has-photo': avatarUser.avatar && !isAvatarBroken(avatarUser) }">
            <img v-if="avatarUser.avatar && !isAvatarBroken(avatarUser)" :src="avatarUser.avatar"
                 :alt="(avatarUser.username || '用户') + ' 头像'" @error="markAvatarBroken(avatarUser)" />
            <span v-else>{{ avatarInitial(avatarUser) }}</span>
          </div>
          <div class="au-avatar-meta">
            <h3>{{ avatarUser.username }}</h3>
            <p>#{{ avatarUser.user_id }} · {{ avatarUser.user_no }}</p>
            <div class="au-avatar-tags">
              <span class="au-chip role" :class="avatarUser.user_type">{{ roleLabel(avatarUser) }}</span>
              <span v-if="avatarUser.is_deleted" class="au-chip bad">回收站</span>
              <span v-else-if="avatarUser.is_disabled" class="au-chip warn">停用</span>
              <span v-else class="au-chip ok">正常</span>
            </div>
            <dl class="au-avatar-dl">
              <dt>院系</dt><dd>{{ avatarUser.department || '—' }}</dd>
              <dt>班级 / 学校</dt><dd>{{ avatarUser.class_name || avatarUser.school || '—' }}</dd>
              <dt>手机</dt><dd>{{ avatarUser.phone || '—' }}</dd>
              <dt>邮箱</dt><dd>{{ avatarUser.email || '—' }}</dd>
              <dt>最近登录</dt><dd>{{ formatTime(avatarUser.last_login) }}</dd>
            </dl>
          </div>
        </div>
        <footer>
          <button v-if="!avatarUser.is_deleted" type="button" class="au-btn"
                  @click="editFromAvatar">编辑资料</button>
          <button type="button" class="au-btn primary" @click="avatarUser = null">关闭</button>
        </footer>
      </section>
    </div>

    <!-- 结果 / 确认 -->
    <div v-if="resultVisible" class="au-modal-mask" @click.self="resultVisible = false">
      <section class="au-modal" role="dialog" aria-modal="true" aria-label="操作结果">
        <header><h2>{{ resultTitle }}</h2>
          <button type="button" class="au-close" aria-label="关闭" @click="resultVisible = false">×</button>
        </header>
        <p class="au-modal-hint">{{ resultMessage }}</p>
        <footer><button type="button" class="au-btn primary" @click="resultVisible = false">知道了</button></footer>
      </section>
    </div>

    <div v-if="toast" class="au-toast" role="status">{{ toast }}</div>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

type Dict = Record<string, any>;

function authFetch(url: string, options?: any) {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth || !auth.apiFetch) return Promise.reject(new Error('登录态失效，请重新登录'));
  return auth.apiFetch(url, options);
}

function jsonOrEmpty(res: any) {
  return res.json().catch(function () { return {}; });
}

async function requestJson(url: string, options?: any) {
  const res = await authFetch(url, options);
  const body = await jsonOrEmpty(res);
  if (!res.ok) {
    const detail = body.detail;
    if (typeof detail === 'string') throw new Error(detail);
    if (detail && detail.message) throw new Error(detail.message);
    throw new Error('请求失败（' + res.status + '）');
  }
  return body;
}

export default defineComponent({
  name: 'AdminUsersWorkspace',
  setup() {
    const route = useRoute();
    const router = useRouter();
    const tabs = [
      { key: 'users', label: '用户管理' },
      { key: 'templates', label: '权限模板' },
      { key: 'audit', label: '授权审计' },
      { key: 'health', label: '权限健康' },
    ];
    const tabKeys = tabs.map(function (item) { return item.key; });
    const initialTab = String(route.query.tab || 'users');
    const tab = ref(tabKeys.indexOf(initialTab) >= 0 ? initialTab : 'users');
    const roleOrder = ['student', 'teacher', 'admin'];
    const isSuper = ref(false);
    const meId = ref(0);
    const loading = ref(false);
    const saving = ref(false);
    const error = ref('');
    const toast = ref('');

    const stats = reactive<Dict>({ total: 0, student: 0, teacher: 0, admin: 0, disabled: 0, deleted: 0, with_override: 0 });
    const users = ref<Dict[]>([]);
    const total = ref(0);
    const page = ref(1);
    const pageSize = 20;
    const keyword = ref('');
    const includeDeleted = ref(false);
    const filters = reactive<Dict>({ user_type: '', role_level: '', is_disabled: '', has_override: '', sort: 'register_time_desc' });
    const selectedIds = ref<number[]>([]);
    const avatarErrors = reactive<Dict>({});
    const avatarUser = ref<Dict | null>(null);

    const catalogGroups = ref<Dict[]>([]);
    const rolesConfig = ref<Dict>({});
    const templateRole = ref('teacher');
    const templateCodes = ref<string[]>([]);
    const templateReason = ref('');

    const auditRows = ref<Dict[]>([]);
    const auditTotal = ref(0);
    const auditPage = ref(1);
    const auditAction = ref('');

    const health = reactive<Dict>({ stats: {}, alerts: [] });

    const editorVisible = ref(false);
    const editorMode = ref('edit');
    const editor = reactive<Dict>({});
    const roleReason = ref('');

    const permissionVisible = ref(false);
    const permissionUser = ref<Dict>({});
    const permissionDetail = ref<Dict>({ items: [] });
    const permissionStates = reactive<Dict>({});
    const permReason = ref('');

    const batchVisible = ref(false);
    const batchAction = ref('disable');
    const batchReason = ref('');
    const batchConfirm = ref('');

    const resultVisible = ref(false);
    const resultTitle = ref('');
    const resultMessage = ref('');

    const totalPages = computed(function () {
      return Math.max(1, Math.ceil(total.value / pageSize));
    });
    const allChecked = computed(function () {
      return users.value.length > 0 && selectedIds.value.length === users.value.length;
    });
    const selectedUsers = computed(function () {
      return users.value.filter(function (user) {
        return selectedIds.value.indexOf(user.user_id) >= 0;
      });
    });
    const selectedAdminCount = computed(function () {
      return selectedUsers.value.filter(function (user) {
        return user.user_type === 'admin';
      }).length;
    });
    const batchReady = computed(function () {
      if (batchAction.value === 'purge') {
        return batchReason.value.trim().length >= 2 && batchConfirm.value === '彻底删除';
      }
      if (['disable', 'delete', 'assign_role'].indexOf(batchAction.value) >= 0) {
        return batchReason.value.trim().length >= 2;
      }
      return true;
    });

    function showToast(message: string) {
      toast.value = message;
      window.setTimeout(function () { toast.value = ''; }, 2600);
    }

    function roleName(role: string) {
      return ({ student: '学生', teacher: '教师', admin: '管理员' } as Dict)[role] || role;
    }

    function roleLabel(user: Dict) {
      return (user.user_type === 'admin' ? '管理员 · L' : '') + (user.user_type === 'admin' ? user.role_level : roleName(user.user_type));
    }

    function actionLabel(action: string) {
      return ({
        disable: '停用', enable: '启用', delete: '移入回收站', restore: '恢复', purge: '彻底删除',
        'single_user_permissions': '单用户权限', 'batch_user_permissions': '批量权限',
        'role_template_update': '角色模板',
      } as Dict)[action] || action;
    }

    function formatTime(value: string) {
      if (!value) return '—';
      return String(value).replace('T', ' ').slice(0, 16);
    }

    function isProtected(code: string) {
      return ['user:manage', 'system:config', 'data:backup', 'log:audit'].indexOf(code) >= 0;
    }

    function avatarKey(user: Dict) {
      return String(user.user_id) + ':' + String(user.avatar || '');
    }

    function isAvatarBroken(user: Dict) {
      return !!avatarErrors[avatarKey(user)];
    }

    function markAvatarBroken(user: Dict) {
      avatarErrors[avatarKey(user)] = true;
    }

    function avatarInitial(user: Dict) {
      return (user.username || '?').slice(0, 1).toUpperCase();
    }

    function openAvatar(user: Dict) {
      avatarUser.value = user;
    }

    function editFromAvatar() {
      const user = avatarUser.value;
      avatarUser.value = null;
      if (user) openEdit(user);
    }

    async function loadBootstrap() {
      const auth = (window as any).__VTJ_AUTH__;
      const profile = auth && auth.parseUserInfo ? auth.parseUserInfo() : null;
      isSuper.value = !!profile && Number(profile.roleLevel) >= 3;
      meId.value = profile ? Number(profile.userId) || 0 : 0;
      const catalog = await requestJson('/api/admin/permissions/catalog');
      catalogGroups.value = catalog.groups || [];
      const perms = await requestJson('/api/admin/permissions');
      rolesConfig.value = perms.roles || {};
      selectTemplateRole(templateRole.value);
    }

    async function loadStats() {
      const data = await requestJson('/api/admin/users/stats');
      Object.assign(stats, data);
    }

    function buildUserQuery() {
      const params: string[] = ['page=' + page.value, 'page_size=' + pageSize, 'sort=' + filters.sort];
      if (keyword.value) params.push('keyword=' + encodeURIComponent(keyword.value));
      if (filters.user_type) params.push('user_type=' + filters.user_type);
      if (filters.role_level !== '') params.push('role_level=' + filters.role_level);
      if (filters.is_disabled !== '') params.push('is_disabled=' + filters.is_disabled);
      if (filters.has_override !== '') params.push('has_override=' + filters.has_override);
      if (includeDeleted.value) params.push('include_deleted=true');
      return '/api/admin/users?' + params.join('&');
    }

    async function loadUsers() {
      const data = await requestJson(buildUserQuery());
      users.value = data.items || [];
      total.value = data.total || 0;
      selectedIds.value = [];
    }

    async function loadAll() {
      loading.value = true;
      error.value = '';
      try {
        await Promise.all([loadStats(), loadUsers()]);
      } catch (err: any) {
        error.value = err.message || '加载失败';
      } finally {
        loading.value = false;
      }
    }

    function reloadUsers() {
      page.value = 1;
      loadAll();
    }

    function resetFilters() {
      keyword.value = '';
      filters.user_type = '';
      filters.role_level = '';
      filters.is_disabled = '';
      filters.has_override = '';
      filters.sort = 'register_time_desc';
      includeDeleted.value = false;
      reloadUsers();
    }

    function goPage(next: number) {
      page.value = Math.min(Math.max(1, next), totalPages.value);
      loadUsers();
    }

    function toggleAll(event: any) {
      selectedIds.value = event.target.checked ? users.value.map(function (u) { return u.user_id; }) : [];
    }

    function openCreate() {
      editorMode.value = 'create';
      Object.keys(editor).forEach(function (key) { delete editor[key]; });
      Object.assign(editor, {
        username: '', user_no: '', password: '', user_type: 'student', role_level: 0,
        phone: '', email: '', gender: '未知', department: '', class_name: '', school: '中国人民警察大学',
      });
      roleReason.value = '';
      editorVisible.value = true;
    }

    async function openEdit(user: Dict) {
      try {
        const data = await requestJson('/api/admin/users/' + user.user_id);
        editorMode.value = 'edit';
        Object.keys(editor).forEach(function (key) { delete editor[key]; });
        Object.assign(editor, data.user);
        roleReason.value = '';
        editorVisible.value = true;
      } catch (err: any) {
        showToast(err.message);
      }
    }

    function closeEditor() {
      editorVisible.value = false;
    }

    async function saveEditor() {
      saving.value = true;
      try {
        if (editorMode.value === 'create') {
          await requestJson('/api/admin/users', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: editor.username, user_no: editor.user_no, password: editor.password,
              user_type: editor.user_type, role_level: Number(editor.role_level),
              phone: editor.phone, email: editor.email, gender: editor.gender,
              department: editor.department, class_name: editor.class_name, school: editor.school,
            }),
          });
        } else {
          await requestJson('/api/admin/users/' + editor.user_id, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              username: editor.username, phone: editor.phone, email: editor.email,
              gender: editor.gender, department: editor.department,
              class_name: editor.class_name, school: editor.school,
            }),
          });
          const oldUser = users.value.find(function (u) { return u.user_id === editor.user_id; });
          if (isSuper.value && oldUser && (oldUser.user_type !== editor.user_type || oldUser.role_level !== editor.role_level)) {
            if (roleReason.value.trim().length < 2) throw new Error('修改角色必须填写原因');
            await requestJson('/api/admin/users/' + editor.user_id + '/role', {
              method: 'PUT', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                user_type: editor.user_type, role_level: Number(editor.role_level),
                reason: roleReason.value,
              }),
            });
          }
        }
        editorVisible.value = false;
        showToast('已保存');
        await loadAll();
      } catch (err: any) {
        showToast(err.message);
      } finally {
        saving.value = false;
      }
    }

    async function openPermissions(user: Dict) {
      try {
        const data = await requestJson('/api/admin/users/' + user.user_id + '/permissions');
        permissionUser.value = user;
        permissionDetail.value = data;
        Object.keys(permissionStates).forEach(function (key) { delete permissionStates[key]; });
        (data.items || []).forEach(function (item: Dict) { permissionStates[item.permission_code] = item.state; });
        permReason.value = '';
        permissionVisible.value = true;
      } catch (err: any) {
        showToast(err.message);
      }
    }

    function permState(code: string) {
      return permissionStates[code] || 'inherit';
    }

    function setPerm(code: string, state: string) {
      permissionStates[code] = state;
    }

    function closePermissions() {
      permissionVisible.value = false;
    }

    async function savePermissions() {
      if (permReason.value.trim().length < 2) {
        showToast('请填写至少 2 个字的变更原因');
        return;
      }
      saving.value = true;
      try {
        const changes: Dict[] = [];
        (permissionDetail.value.items || []).forEach(function (item: Dict) {
          const next = permState(item.permission_code);
          if (next !== item.state) changes.push({ permission_code: item.permission_code, effect: next });
        });
        if (!changes.length) {
          showToast('没有需要保存的变更');
          return;
        }
        await requestJson('/api/admin/users/' + permissionUser.value.user_id + '/permissions', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: permReason.value, changes: changes }),
        });
        permissionVisible.value = false;
        showToast('权限已保存，可在授权审计中撤销');
        await loadUsers();
      } catch (err: any) {
        showToast(err.message);
      } finally {
        saving.value = false;
      }
    }

    async function toggleDisabled(user: Dict) {
      try {
        await requestJson('/api/admin/users/' + user.user_id + '/disable', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_disabled: !user.is_disabled, reason: user.is_disabled ? '' : '管理员停用' }),
        });
        await loadAll();
        showToast(user.is_disabled ? '已启用' : '已停用');
      } catch (err: any) {
        showToast(err.message);
      }
    }

    async function resetPassword(user: Dict) {
      try {
        const data = await requestJson('/api/admin/users/' + user.user_id + '/reset-password', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        resultTitle.value = '密码已重置';
        resultMessage.value = user.username + ' 的新密码：' + (data.new_password || '（未返回）');
        resultVisible.value = true;
      } catch (err: any) {
        showToast(err.message);
      }
    }

    async function deleteUser(user: Dict) {
      const reason = window.prompt('移入回收站的原因（至少 2 字）', '账号清理');
      if (reason === null) return;
      try {
        await requestJson('/api/admin/users/' + user.user_id, {
          method: 'DELETE', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason }),
        });
        await loadAll();
        showToast('已移入回收站');
      } catch (err: any) {
        showToast(err.message);
      }
    }

    async function restoreUser(user: Dict) {
      try {
        await requestJson('/api/admin/users/' + user.user_id + '/restore', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        await loadAll();
        showToast('已恢复');
      } catch (err: any) {
        showToast(err.message);
      }
    }

    async function purgeUser(user: Dict) {
      const confirm = window.prompt('彻底注销将匿名化并不可恢复，输入用户名确认：' + user.username);
      if (confirm !== user.username) {
        if (confirm !== null) showToast('用户名不匹配');
        return;
      }
      const reason = window.prompt('注销原因（至少 2 字）', '用户申请注销');
      if (reason === null) return;
      try {
        await requestJson('/api/admin/users/' + user.user_id + '/purge', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: reason, confirm_username: confirm }),
        });
        await loadAll();
        showToast('已匿名化注销');
      } catch (err: any) {
        showToast(err.message);
      }
    }

    function openBatch(action: string) {
      batchAction.value = action;
      batchReason.value = action === 'restore' ? '回收站恢复' : '';
      batchConfirm.value = '';
      batchVisible.value = true;
    }

    async function submitBatch() {
      if (!batchReady.value) {
        showToast(batchAction.value === 'purge'
          ? '请填写原因并输入「彻底删除」确认'
          : '请填写至少 2 个字的操作原因');
        return;
      }
      saving.value = true;
      try {
        await requestJson('/api/admin/users/batch', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: batchAction.value,
            target: { mode: 'ids', user_ids: selectedIds.value, expected_count: selectedIds.value.length },
            payload: { reason: batchReason.value },
            expected_count: selectedIds.value.length,
          }),
        });
        batchVisible.value = false;
        batchConfirm.value = '';
        showToast(batchAction.value === 'purge' ? '已批量彻底删除并匿名化' : '批量操作完成');
        await loadAll();
      } catch (err: any) {
        showToast(err.message);
      } finally {
        saving.value = false;
      }
    }

    function selectTemplateRole(role: string) {
      templateRole.value = role;
      const config = rolesConfig.value[role];
      templateCodes.value = config ? (config.permissions || []).slice() : [];
      templateReason.value = '';
    }

    async function saveTemplate() {
      if (templateReason.value.trim().length < 2) {
        showToast('请填写至少 2 个字的变更原因');
        return;
      }
      saving.value = true;
      try {
        await requestJson('/api/admin/permissions', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: templateRole.value, permissions: templateCodes.value, reason: templateReason.value }),
        });
        showToast('模板已保存');
        const perms = await requestJson('/api/admin/permissions');
        rolesConfig.value = perms.roles || {};
        selectTemplateRole(templateRole.value);
      } catch (err: any) {
        showToast(err.message);
      } finally {
        saving.value = false;
      }
    }

    async function loadAudit(nextPage: number) {
      auditPage.value = nextPage;
      try {
        const params = '?page=' + auditPage.value + '&page_size=20' + (auditAction.value ? '&action=' + auditAction.value : '');
        const data = await requestJson('/api/admin/permission-audit' + params);
        auditRows.value = data.items || [];
        auditTotal.value = data.total || 0;
      } catch (err: any) {
        showToast(err.message);
      }
    }

    async function undoBatch(row: Dict) {
      if (!window.confirm('撤销该批次？撤销会逐条比对，若已被后续修改则整批拒绝。')) return;
      try {
        await requestJson('/api/admin/permission-batches/' + row.batch_id + '/undo', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: '管理员在审计页撤销' }),
        });
        showToast('批次已撤销');
        await loadAudit(auditPage.value);
        await loadUsers();
      } catch (err: any) {
        showToast(err.message);
      }
    }

    async function loadHealth() {
      try {
        const data = await requestJson('/api/admin/permission-health');
        health.stats = data.stats || {};
        health.alerts = data.alerts || [];
      } catch (err: any) {
        showToast(err.message);
      }
    }

    function activateTab(next: string) {
      if (tabKeys.indexOf(next) < 0) next = 'users';
      tab.value = next;
      if (next === 'audit') loadAudit(1);
      if (next === 'health') loadHealth();
      if (next === 'templates' && !catalogGroups.value.length) loadBootstrap();
    }

    function switchTab(next: string) {
      router.replace({ path: '/admin/users', query: next === 'users' ? {} : { tab: next } });
      activateTab(next);
    }

    // 旧书签 /admin/permissions 会带 tab=templates 跳入，前进后退时同步视图
    watch(function () { return route.query.tab; }, function (value) {
      if (route.path === '/admin/users') activateTab(String(value || 'users'));
    });

    onMounted(async function () {
      try {
        await loadBootstrap();
      } catch (err: any) {
        error.value = err.message;
      }
      await loadAll();
      // 旧书签或权限模板 redirect 直接落在非默认 Tab 时，进入页面即加载对应数据
      activateTab(tab.value);
    });

    return {
      tab, tabs, roleOrder, isSuper, meId, loading, saving, error, toast,
      stats, users, total, page, keyword, includeDeleted, filters, selectedIds,
      catalogGroups, rolesConfig, templateRole, templateCodes, templateReason,
      auditRows, auditTotal, auditPage, auditAction, health,
      editorVisible, editorMode, editor, roleReason,
      permissionVisible, permissionUser, permissionDetail, permissionStates, permReason,
      batchVisible, batchAction, batchReason, batchConfirm, resultVisible, resultTitle, resultMessage,
      avatarUser, avatarErrors, selectedUsers, selectedAdminCount, batchReady,
      totalPages, allChecked,
      roleName, roleLabel, actionLabel, formatTime, isProtected,
      avatarInitial, isAvatarBroken, markAvatarBroken, openAvatar, editFromAvatar,
      loadAll, reloadUsers, resetFilters, goPage, toggleAll,
      openCreate, openEdit, closeEditor, saveEditor,
      openPermissions, closePermissions, permState, setPerm, savePermissions,
      toggleDisabled, resetPassword, deleteUser, restoreUser, purgeUser,
      openBatch, submitBatch, selectTemplateRole, saveTemplate,
      loadAudit, undoBatch, loadHealth, switchTab,
    };
  },
});
</script>

<style scoped>
.au-page {
  --au-primary: #1a3c6d;
  --au-danger: #b42318;
  --au-border: #dbe3ee;
  --au-ink: #1f2937;
  --au-muted: #68758a;
  min-height: 100%;
  padding: 24px 28px 40px;
  background: #f5f7fb;
  color: var(--au-ink);
  font-size: 14px;
}
.au-head { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.au-head h1 { margin: 0 0 6px; font-size: 26px; letter-spacing: .5px; color: var(--au-primary); }
.au-head p { margin: 0; color: var(--au-muted); line-height: 1.7; max-width: 720px; }
.au-head-actions { display: flex; gap: 10px; flex: none; }
.au-btn {
  border: 1px solid var(--au-border); background: #fff; color: var(--au-primary);
  border-radius: 8px; padding: 8px 14px; cursor: pointer; font-size: 13px;
}
.au-btn:hover:not(:disabled) { border-color: var(--au-primary); }
.au-btn:disabled { opacity: .5; cursor: not-allowed; }
.au-btn.primary { background: var(--au-primary); color: #fff; border-color: var(--au-primary); }
.au-btn.danger { color: var(--au-danger); }
.au-btn:focus-visible, .au-link:focus-visible, .au-input:focus-visible,
.au-tabs button:focus-visible, .au-tristate button:focus-visible,
.au-segmented button:focus-visible, .au-close:focus-visible {
  outline: 2px solid #2f6feb; outline-offset: 2px;
}
.au-alert {
  margin-top: 16px; padding: 10px 14px; border-radius: 8px; background: #fff1f0;
  border: 1px solid #f3c1bd; color: var(--au-danger); display: flex; justify-content: space-between;
}
.au-tabs { display: flex; gap: 6px; margin: 22px 0 16px; border-bottom: 1px solid var(--au-border); }
.au-tabs button {
  border: 0; background: transparent; padding: 10px 16px; cursor: pointer; color: var(--au-muted);
  border-bottom: 2px solid transparent; font-size: 14px;
}
.au-tabs button.active { color: var(--au-primary); border-bottom-color: var(--au-primary); font-weight: 600; }
.au-badge { display: inline-block; margin-left: 6px; padding: 0 6px; border-radius: 10px; background: #e8eef8; font-size: 11px; }
.au-stats { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.au-stats article { background: #fff; border: 1px solid var(--au-border); border-radius: 10px; padding: 14px 16px; }
.au-stats span { color: var(--au-muted); font-size: 12px; }
.au-stats strong { display: block; margin: 6px 0 4px; font-size: 24px; color: var(--au-primary); }
.au-stats small { color: var(--au-muted); font-size: 11px; }
.au-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; background: #fff; border: 1px solid var(--au-border); border-radius: 10px; padding: 12px; }
.au-input {
  height: 34px; border: 1px solid var(--au-border); border-radius: 8px; padding: 0 10px;
  background: #fff; color: var(--au-ink); font-size: 13px; min-width: 110px;
}
.au-input.search { min-width: 220px; flex: 1 1 220px; }
.au-switch { display: flex; align-items: center; gap: 6px; color: var(--au-muted); cursor: pointer; }
.au-batchbar {
  margin-top: 12px; padding: 10px 14px; background: #eef4ff; border: 1px solid #cddcf7;
  border-radius: 8px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
}
.au-table-wrap { margin-top: 12px; background: #fff; border: 1px solid var(--au-border); border-radius: 10px; overflow: auto; }
.au-table { width: 100%; border-collapse: collapse; min-width: 1080px; }
.au-table th, .au-table td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #edf1f7; vertical-align: middle; }
.au-table th { background: #f8fafd; color: var(--au-muted); font-size: 12px; font-weight: 600; white-space: nowrap; }
.au-table tr.muted { background: #fbfcfe; color: var(--au-muted); }
.au-table .check { width: 36px; }
.au-table .actions { white-space: nowrap; text-align: right; }
.au-user { display: flex; align-items: center; gap: 10px; }
.au-avatar {
  width: 34px; height: 34px; flex: none; border-radius: 50%; background: #e8eef8;
  color: var(--au-primary); display: grid; place-items: center; font-weight: 700;
  border: 0; padding: 0; overflow: hidden; cursor: pointer; font-size: 13px;
}
.au-avatar img { width: 100%; height: 100%; object-fit: cover; display: block; }
.au-avatar:focus-visible { outline: 2px solid #2f6feb; outline-offset: 2px; }
.au-user strong { display: block; }
.au-user small, .au-two-line small, .au-perm-name small { color: var(--au-muted); font-size: 11px; display: block; }
.au-chip { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eef1f6; color: var(--au-muted); font-size: 11px; }
.au-chip.ok { background: #e8f7ee; color: #177245; }
.au-chip.warn { background: #fff5e6; color: #9a5b00; }
.au-chip.bad { background: #fdeceb; color: var(--au-danger); }
.au-chip.role.teacher { background: #eef4ff; color: #1a4b8f; }
.au-chip.role.admin { background: #f3ecff; color: #5b2ea6; }
.au-link { border: 0; background: transparent; color: #2f6feb; cursor: pointer; padding: 2px 6px; font-size: 13px; }
.au-link.danger { color: var(--au-danger); }
.au-empty { text-align: center; color: var(--au-muted); padding: 36px 0 !important; }
.au-pager { display: flex; justify-content: flex-end; gap: 12px; align-items: center; margin-top: 12px; color: var(--au-muted); }
.au-template-head { display: flex; justify-content: space-between; gap: 20px; align-items: center; flex-wrap: wrap; background: #fff; border: 1px solid var(--au-border); border-radius: 10px; padding: 14px 16px; }
.au-template-head p { margin: 0; color: var(--au-muted); }
.au-segmented { display: inline-flex; border: 1px solid var(--au-border); border-radius: 8px; overflow: hidden; }
.au-segmented button { border: 0; background: #fff; padding: 8px 18px; cursor: pointer; color: var(--au-muted); }
.au-segmented button.active { background: var(--au-primary); color: #fff; }
.au-template-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.au-template-group { background: #fff; border: 1px solid var(--au-border); border-radius: 10px; padding: 14px; }
.au-template-group h3 { margin: 0 0 10px; font-size: 14px; color: var(--au-primary); }
.au-template-group h3 small { color: var(--au-muted); font-weight: 400; }
.au-perm-check { display: flex; gap: 8px; align-items: flex-start; padding: 6px 0; border-top: 1px dashed #eef1f7; }
.au-perm-check span { display: flex; flex-direction: column; gap: 2px; }
.au-perm-check small { color: var(--au-muted); font-size: 10px; }
.au-perm-check.locked { opacity: .78; }
.au-savebar { position: sticky; bottom: 0; margin-top: 14px; padding: 12px; background: #fff; border: 1px solid var(--au-border); border-radius: 10px; display: flex; gap: 10px; justify-content: flex-end; }
.au-savebar .au-input { min-width: 300px; }
.risk { font-style: normal; font-size: 10px; color: var(--au-danger); margin-left: 6px; }
.au-mono { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; }
.au-reason { max-width: 260px; color: var(--au-muted); }
.au-health-head { display: flex; justify-content: space-between; align-items: center; background: #fff; border: 1px solid var(--au-border); border-radius: 10px; padding: 14px 16px; }
.au-health-head p { margin: 0; color: var(--au-muted); }
.au-alerts { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.au-alerts li { background: #fff; border: 1px solid var(--au-border); border-left: 4px solid var(--au-primary); border-radius: 8px; padding: 12px 14px; display: flex; justify-content: space-between; }
.au-alerts li.critical { border-left-color: var(--au-danger); }
.au-alerts li.warning { border-left-color: #d97706; }
.au-alerts li.ok { border-left-color: #177245; color: #177245; }
.au-modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, .5); display: grid; place-items: center; z-index: 2200; padding: 24px; }
.au-modal { width: min(560px, 96vw); max-height: 90vh; overflow: auto; background: #fff; border-radius: 12px; box-shadow: 0 24px 60px rgba(15, 23, 42, .28); }
.au-modal.wide { width: min(980px, 96vw); }
.au-modal header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--au-border); }
.au-modal header h2 { margin: 0; font-size: 17px; color: var(--au-primary); }
.au-close { border: 0; background: transparent; font-size: 22px; cursor: pointer; color: var(--au-muted); }
.au-modal footer { display: flex; justify-content: flex-end; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--au-border); position: sticky; bottom: 0; background: #fff; }
.au-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; padding: 18px 20px; }
.au-form-grid label, .au-modal > label { display: flex; flex-direction: column; gap: 6px; color: var(--au-muted); font-size: 12px; }
.au-form-grid .span-2 { grid-column: span 2; }
.au-modal-hint { padding: 0 20px; color: var(--au-muted); line-height: 1.7; }
.au-modal-hint.danger-hint { color: var(--au-danger); }
.au-impact {
  display: flex; flex-wrap: wrap; gap: 10px 18px; margin: 0 20px 12px;
  padding: 10px 12px; background: #fff7f6; border: 1px solid #f3d3cf; border-radius: 8px;
  color: var(--au-ink); font-size: 13px;
}
.au-impact strong { color: var(--au-primary); font-size: 15px; }
.au-impact-danger { color: var(--au-danger); font-weight: 600; }
.au-avatar-modal { width: min(620px, 96vw); }
.au-avatar-card { display: flex; gap: 20px; padding: 20px; align-items: flex-start; }
.au-avatar-xl { width: 88px; height: 88px; font-size: 30px; cursor: default; }
.au-avatar-meta { min-width: 0; flex: 1; }
.au-avatar-meta h3 { margin: 0 0 4px; font-size: 20px; color: var(--au-primary); }
.au-avatar-meta > p { margin: 0 0 10px; color: var(--au-muted); font-size: 12px; }
.au-avatar-tags { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.au-avatar-dl {
  display: grid; grid-template-columns: 76px 1fr; gap: 6px 12px;
  margin: 0; font-size: 13px;
}
.au-avatar-dl dt { color: var(--au-muted); }
.au-avatar-dl dd { margin: 0; color: var(--au-ink); word-break: break-all; }
.au-perm-summary { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 20px; background: #f8fafd; border-bottom: 1px solid var(--au-border); }
.au-perm-summary span { background: #fff; border: 1px solid var(--au-border); border-radius: 999px; padding: 3px 10px; font-size: 12px; }
.au-perm-body { padding: 14px 20px; max-height: 54vh; overflow: auto; }
.au-perm-group h3 { margin: 14px 0 6px; font-size: 13px; color: var(--au-primary); }
.au-perm-row { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-top: 1px dashed #edf1f7; align-items: center; }
.au-perm-name strong { font-weight: 500; }
.au-tristate { display: inline-flex; border: 1px solid var(--au-border); border-radius: 7px; overflow: hidden; flex: none; }
.au-tristate button { border: 0; background: #fff; padding: 5px 9px; cursor: pointer; font-size: 12px; color: var(--au-muted); }
.au-tristate button.on { background: var(--au-primary); color: #fff; }
.au-permission-modal footer .au-input { flex: 1; min-width: 160px; }
.au-toast { position: fixed; left: 50%; bottom: 36px; transform: translateX(-50%); background: #1f2937; color: #fff; padding: 10px 18px; border-radius: 8px; z-index: 2400; box-shadow: 0 8px 24px rgba(0,0,0,.2); }
@media (max-width: 1100px) {
  .au-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .au-template-grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .au-page * { transition: none !important; animation: none !important; }
}
</style>
