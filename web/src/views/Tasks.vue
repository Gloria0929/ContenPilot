<template>
  <div>
    <el-table :data="tasks" min-width="120">
      <el-table-column prop="id" label="ID" min-width="60" />
      <el-table-column label="文章" min-width="70">
        <template #default="scope">#{{ scope.row.article_id }}</template>
      </el-table-column>
      <el-table-column prop="platform" label="平台" min-width="100" />
      <el-table-column prop="review_policy" label="审核" min-width="92" />
      <el-table-column prop="publish_policy" label="发布" min-width="80" />
      <el-table-column label="下限锁定" min-width="90">
        <template #default="scope">
          <el-tag v-if="scope.row.policy_floor_locked" type="warning"
            >已锁定</el-tag
          >
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" min-width="100">
        <template #default="scope">
          <el-tag :type="statusType(scope.row.status)">{{
            statusLabel[scope.row.status] ?? scope.row.status
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="远程链接" min-width="110">
        <template #default="scope">
          <el-link
            v-if="scope.row.remote_url"
            :href="scope.row.remote_url"
            target="_blank"
            type="primary"
            >查看</el-link
          >
          <el-tooltip
            v-else-if="scope.row.error_message"
            :content="scope.row.error_message"
            placement="top"
          >
            <span class="err-tip">—</span>
          </el-tooltip>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="180">
        <template #default="scope">
          <div class="row-actions">
            <el-button
              v-if="scope.row.status === 'pending'"
              text
              type="primary"
              @click="act(scope.row.id, 'resume', '发布')"
              >发布</el-button
            >
            <el-button
              v-if="['failed', 'blocked', 'timeout'].includes(scope.row.status)"
              text
              @click="act(scope.row.id, 'retry', '重试')"
              >重试</el-button
            >
            <el-button
              v-if="['waiting_manual', 'timeout'].includes(scope.row.status)"
              text
              @click="act(scope.row.id, 'resume', '恢复')"
              >恢复</el-button
            >
            <el-button
              v-if="
                !['success', 'failed', 'cancelled'].includes(scope.row.status)
              "
              type="danger"
              plain
              text
              @click="act(scope.row.id, 'cancel', '取消')"
              >取消</el-button
            >
            <!-- 终态任务可删除（后端同样校验） -->
            <el-button
              v-if="
                ['success', 'failed', 'cancelled', 'timeout'].includes(
                  scope.row.status,
                )
              "
              text
              type="danger"
              @click="confirmRemoveTask(scope.row)"
              >删除</el-button
            >
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElLink,
  ElTooltip,
  ElMessageBox,
  ElMessage,
} from "element-plus";
import api from "../api";

const tasks = ref<any[]>([]);

const statusLabel: Record<string, string> = {
  pending: "待处理",
  queued: "排队中",
  processing: "发布中",
  waiting_review: "等待审核",
  waiting_auth: "等待授权",
  waiting_manual: "等待人工",
  blocked: "被拦截",
  success: "成功",
  failed: "失败",
  cancelled: "已取消",
  timeout: "超时",
};
const statusType = (s: string) => {
  const m: Record<
    string,
    "success" | "danger" | "warning" | "info" | undefined
  > = {
    success: "success",
    failed: "danger",
    blocked: "danger",
    timeout: "warning",
    waiting_review: "warning",
    waiting_auth: "warning",
    waiting_manual: "warning",
    processing: "info",
    queued: "info",
    pending: undefined,
    cancelled: undefined,
  };
  return m[s];
};

async function load() {
  const r = await api.get("/tasks");
  tasks.value = r.data;
}

async function act(id: number, action: string, label: string) {
  try {
    await api.post(`/tasks/${id}/${action}`);
    ElMessage.success(`任务 #${id} 已${label}`);
    load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || `${label}失败`);
  }
}

async function confirmRemoveTask(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除任务 #${row.id} 吗？关联的审核记录与日志将一并删除。`,
      "删除任务",
      {
        confirmButtonText: "确认删除",
        cancelButtonText: "取消",
        type: "warning",
        confirmButtonClass: "el-button--danger",
      },
    );
  } catch {
    return;
  }
  await removeTask(row.id);
}

async function removeTask(id: number) {
  try {
    await api.delete(`/tasks/${id}`);
    ElMessage.success(`任务 #${id} 已删除`);
    load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
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
.err-tip {
  cursor: help;
  color: var(--el-color-danger);
}
.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
