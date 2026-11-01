<template>
  <div class="mc-page">
    <header class="mc-head">
      <h1>创建卡片</h1>
      <p class="mc-sub">
        学生端不再通过 Excel 批量上传：一人一卡手动填写，<b>保存即公开展示（免审批）</b>。
        字段与后台「智能导入」的表格模板一一对应：正面 / 背面 / 分类 / 考点 + 1~2 张配图。
      </p>
    </header>

    <CardCreateForm inline :open="true" :subject="subject" @saved="onSaved" />

    <p class="mc-foot">
      需要的字段说明：正面 ≤120 字；背面 ≤600 字（背面为空时必须配图）；
      分类留空由系统按文本自动判定；配图支持 png / jpg / webp，单张 ≤5MB。
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import CardCreateForm from '@/components/materials/CardCreateForm.vue';

const subject = ref('xingce');

const onSaved = (payload: Record<string, any>) => {
  if (payload?.subject) subject.value = String(payload.subject);
  ElMessage.success('卡片已创建并公开展示');
};
</script>

<style scoped>
.mc-page {
  max-width: 780px;
  margin: 0 auto;
  padding: 24px 18px 56px;
}
.mc-head h1 {
  margin: 0 0 6px;
  font-size: 21px;
  color: #111827;
}
.mc-sub {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.7;
  color: #6b7280;
}
.mc-sub b {
  color: #b45309;
}
.mc-foot {
  margin: 14px 0 0;
  font-size: 12px;
  line-height: 1.8;
  color: #9ca3af;
}
@media (max-width: 600px) {
  .mc-page {
    padding: 16px 12px 40px;
  }
}
</style>
