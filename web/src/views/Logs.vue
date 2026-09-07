<template>
  <div class="logs">
    <div class="toolbar">
      <el-input-number
        v-model="filterTaskId"
        placeholder="任务 ID"
        :style="{ width: '140px' }"
        @change="load"
      />
      <el-select
        v-model="filterLevel"
        placeholder="级别"
        clearable
        :style="{ width: '130px' }"
        @change="load"
      >
        <el-option
          v-for="opt in levelOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-button @click="load">刷新</el-button>
    </div>
    <el-table v-loading="loading" :data="logs">
      <el-table-column label="时间" min-width="100">
        <template #default="scope">{{
          fmtTime(scope.row.created_at)
        }}</template>
      </el-table-column>
      <el-table-column label="任务" min-width="50">
        <template #default="scope">
          {{ scope.row.task_id ? `#${scope.row.task_id}` : "-" }}
        </template>
      </el-table-column>
      <el-table-column label="级别" min-width="100">
        <template #default="scope">
          <el-tag :type="levelType[scope.row.level]">
            {{ levelLabel[scope.row.level] ?? scope.row.level }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="事件" min-width="120">
        <template #default="scope">
          {{ eventLabel[scope.row.event] ?? scope.row.event }}
        </template>
      </el-table-column>
      <el-table-column label="消息" min-width="200" show-overflow-tooltip>
        <template #default="scope">{{ fmtMessage(scope.row) }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import {
  ElInputNumber,
  ElSelect,
  ElOption,
  ElButton,
  ElTable,
  ElTableColumn,
  ElTag,
} from "element-plus";
import api from "../api";

const logs = ref<any[]>([]);
const loading = ref(false);
const filterTaskId = ref<number | null>(null);
const filterLevel = ref<string | null>(null);

const levelOptions = [
  { label: "信息", value: "info" },
  { label: "警告", value: "warning" },
  { label: "错误", value: "error" },
];

const levelType: Record<string, "warning" | "danger" | undefined> = {
  info: undefined,
  warning: "warning",
  error: "danger",
};

const levelLabel: Record<string, string> = {
  info: "信息",
  warning: "警告",
  error: "错误",
};

// 事件名 → 中文（与后端 LogService / Worker / Browser 层事件一一对应）
const eventLabel: Record<string, string> = {
  task_created: "任务已创建",
  task_retry: "任务重试",
  waiting_review: "等待审核",
  waiting_auth: "等待授权",
  waiting_manual: "等待人工",
  publish_success: "发布成功",
  publish_failed: "发布失败",
  publish_unconfirmed: "发布结果未确认",
  "task.timeout": "任务超时",
  browser_started: "浏览器任务启动",
  login_checked: "登录状态检查",
  page_opened: "打开发布页面",
  content_filled: "内容填写提交",
  submit_clicked: "发布按钮已点击",
  review_refreshed: "审核版本已刷新",
  policy_override: "策略覆盖（审计）",
};

// message 美化：原样多为 "platform=xxx" / 文章链接
function fmtMessage(row: any): string {
  const m = row.message || "";
  const pm = m.match(/^platform=([\w-]+)$/);
  if (pm) return `平台：${pm[1]}`;
  if (/^https?:\/\//.test(m)) return `发布链接：${m}`;
  return m || "-";
}

const fmtTime = (t: string) => (t ? t.slice(0, 19).replace("T", " ") : "");

async function load() {
  loading.value = true;
  try {
    const params: any = { limit: 200 };
    if (filterTaskId.value != null) params.task_id = filterTaskId.value;
    if (filterLevel.value) params.level = filterLevel.value;
    const r = await api.get("/logs", { params });
    logs.value = r.data;
  } finally {
    loading.value = false;
  }
}

let es: EventSource | null = null;
onMounted(() => {
  load();
  es = new EventSource("/api/events");
  es.onmessage = () => load();
});
onUnmounted(() => es?.close());
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
