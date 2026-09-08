<template>
  <div class="admin-help">
    <el-card class="help-header">
      <h1>系统使用帮助</h1>
      <p>欢迎使用公安联考智能题库系统，以下是常见问题解答和操作指南</p>
    </el-card>

    <el-collapse v-model="activeNames">
      <el-collapse-item title="一、系统登录" name="1">
        <div class="help-content">
          <h4>1.1 如何登录系统？</h4>
          <ol>
            <li>打开浏览器，访问系统地址</li>
            <li>在登录页面输入您的用户名和密码</li>
            <li>点击"登录"按钮</li>
            <li>系统会根据您的角色自动跳转到对应的工作台</li>
          </ol>

          <h4>1.2 忘记密码怎么办？</h4>
          <p>请联系系统管理员重置密码。管理员可以在"用户管理"中选择您的账号，点击"重置密码"按钮。</p>

          <h4>1.3 账号被禁用怎么办？</h4>
          <p>如果您的账号被禁用，请联系管理员说明情况，管理员可以在"用户管理"中启用您的账号。</p>
        </div>
      </el-collapse-item>

      <el-collapse-item title="二、用户管理（管理员）" name="2">
        <div class="help-content">
          <h4>2.1 如何创建新用户？</h4>
          <ol>
            <li>进入"用户管理"页面</li>
            <li>点击"新增用户"按钮</li>
            <li>填写用户信息（用户编号、用户名、密码、手机号、用户类型等）</li>
            <li>点击"确认创建"保存</li>
          </ol>

          <h4>2.2 如何编辑用户信息？</h4>
          <ol>
            <li>在用户列表中找到目标用户</li>
            <li>点击操作列的"编辑"按钮</li>
            <li>在弹窗中修改用户信息（包括头像、手机号、邮箱等）</li>
            <li>点击"保存修改"提交</li>
          </ol>

          <h4>2.3 如何修改用户头像？</h4>
          <ol>
            <li>点击用户列表中的"编辑"按钮</li>
            <li>在编辑弹窗中找到"用户头像"区域</li>
            <li>可以选择"上传头像"（支持JPG/PNG格式，不超过2MB）</li>
            <li>或点击"从图库选择"使用预设头像</li>
            <li>也可以点击"重置默认"恢复默认头像</li>
          </ol>

          <h4>2.4 如何禁用/启用用户？</h4>
          <ol>
            <li>在用户列表中找到目标用户</li>
            <li>点击"禁用"按钮（正常状态用户）或"启用"按钮（禁用状态用户）</li>
            <li>确认操作后，用户状态会立即更新</li>
          </ol>

          <h4>2.5 如何重置用户密码？</h4>
          <ol>
            <li>在用户列表中找到目标用户</li>
            <li>点击操作列的"重置密码"按钮</li>
            <li>确认后系统会生成新密码并显示，请将新密码告知用户</li>
          </ol>
        </div>
      </el-collapse-item>

      <el-collapse-item title="三、题库管理（管理员）" name="3">
        <div class="help-content">
          <h4>3.1 如何查看题目？</h4>
          <ol>
            <li>进入"题库管理"页面</li>
            <li>可以使用筛选条件（科目、题型、难度、审核状态等）快速定位</li>
            <li>点击题目内容或"预览"按钮查看完整题目信息</li>
          </ol>

          <h4>3.2 如何编辑题目？</h4>
          <ol>
            <li>在题目列表中找到目标题目</li>
            <li>点击操作列的"编辑"按钮</li>
            <li>在弹窗中修改题目内容、选项、答案、解析等</li>
            <li>点击"保存修改"提交</li>
          </ol>

          <h4>3.3 如何审核题目？</h4>
          <ol>
            <li>在题目列表中筛选"待审核"状态的题目</li>
            <li>查看题目内容后，点击"通过"或"驳回"按钮</li>
            <li>如果驳回，需要选择驳回原因并可填写详细说明</li>
            <li>审核结果会立即生效</li>
          </ol>

          <h4>3.4 题目ID如何排序？</h4>
          <p>点击表格列头的"ID"列，可以按题目ID升序或降序排列。</p>
        </div>
      </el-collapse-item>

      <el-collapse-item title="四、数据备份" name="4">
        <div class="help-content">
          <h4>4.1 如何备份数据？</h4>
          <ol>
            <li>进入"数据备份"页面</li>
            <li>点击"立即备份"按钮</li>
            <li>系统会自动生成中文备份名称（如"系统全量备份_2026年09月08日_15点30分"）</li>
            <li>也可以手动输入备份名称</li>
            <li>等待备份完成，状态显示"已完成"即可</li>
          </ol>

          <h4>4.2 如何恢复数据？</h4>
          <ol>
            <li>在备份列表中找到目标备份</li>
            <li>点击"恢复"按钮</li>
            <li>系统会要求输入管理员密码进行二次确认</li>
            <li>确认后执行恢复操作</li>
          </ol>

          <h4>4.3 如何下载备份文件？</h4>
          <p>在备份列表中，状态为"已完成"的备份可以点击"下载"按钮下载备份文件。</p>
        </div>
      </el-collapse-item>

      <el-collapse-item title="五、日志审计" name="5">
        <div class="help-content">
          <h4>5.1 如何查看操作日志？</h4>
          <ol>
            <li>进入"日志审计"页面</li>
            <li>可以使用筛选条件（时间范围、用户、操作类型、模块等）筛选日志</li>
            <li>日志按时间倒序排列，最新的操作在最前面</li>
          </ol>

          <h4>5.2 日志包含哪些信息？</h4>
          <p>每条日志记录包含：操作时间、操作用户、用户角色、操作类型、操作模块、操作描述、IP地址、操作状态、耗时等信息。</p>

          <h4>5.3 如何导出日志？</h4>
          <p>点击页面右上角的"导出"按钮，可以将当前筛选结果导出为Excel文件。</p>
        </div>
      </el-collapse-item>

      <el-collapse-item title="六、系统设置" name="6">
        <div class="help-content">
          <h4>6.1 如何修改系统名称？</h4>
          <ol>
            <li>进入"系统设置"页面</li>
            <li>在"基本设置"选项卡中修改系统名称</li>
            <li>点击"保存设置"提交</li>
          </ol>

          <h4>6.2 如何更换系统Logo？</h4>
          <ol>
            <li>进入"系统设置"页面</li>
            <li>在"基本设置"选项卡中点击"更换Logo"</li>
            <li>上传新的Logo图片</li>
            <li>点击"保存设置"提交</li>
          </ol>
        </div>
      </el-collapse-item>

      <el-collapse-item title="七、常见问题" name="7">
        <div class="help-content">
          <h4>7.1 页面加载缓慢怎么办？</h4>
          <ol>
            <li>检查网络连接是否正常</li>
            <li>清除浏览器缓存（Ctrl+Shift+Delete）</li>
            <li>尝试刷新页面（F5）</li>
            <li>如果问题持续，请联系系统管理员检查服务器状态</li>
          </ol>

          <h4>7.2 操作报错怎么办？</h4>
          <ol>
            <li>记录错误信息（错误代码、错误描述）</li>
            <li>尝试刷新页面后重试</li>
            <li>如果问题持续，请将错误信息发送给系统管理员</li>
          </ol>

          <h4>7.3 常见错误代码说明</h4>
          <ul>
            <li><strong>401</strong>：未登录或登录已过期，请重新登录</li>
            <li><strong>403</strong>：权限不足，请联系管理员</li>
            <li><strong>404</strong>：页面不存在，请检查访问地址</li>
            <li><strong>500</strong>：服务器错误，请稍后重试或联系管理员</li>
          </ul>
        </div>
      </el-collapse-item>
    </el-collapse>

    <el-card class="help-footer">
      <p>如有其他问题，请联系系统管理员或技术支持</p>
      <p>技术支持邮箱：support@example.com</p>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeNames = ref(['1'])
</script>

<style scoped>
.admin-help {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.help-header {
  margin-bottom: 20px;
  text-align: center;
}

.help-header h1 {
  margin: 0 0 10px 0;
  color: #303133;
}

.help-header p {
  margin: 0;
  color: #606266;
}

.help-content {
  padding: 10px 20px;
  line-height: 1.8;
}

.help-content h4 {
  margin-top: 20px;
  margin-bottom: 10px;
  color: #409eff;
  font-size: 15px;
}

.help-content ol,
.help-content ul {
  padding-left: 20px;
  margin-bottom: 15px;
}

.help-content li {
  margin-bottom: 8px;
}

.help-content p {
  margin-bottom: 10px;
  color: #606266;
}

.help-content strong {
  color: #303133;
}

.help-footer {
  margin-top: 30px;
  text-align: center;
  color: #909399;
}

.help-footer p {
  margin: 5px 0;
}
</style>