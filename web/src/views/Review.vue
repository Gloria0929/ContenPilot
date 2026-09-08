<template>
  <div class="review">
    <el-table :data="reviews" :row-key="(row: any) => row.id">
      <el-table-column prop="id" label="ID" min-width="60" />
      <el-table-column label="文章" min-width="260" show-overflow-tooltip>
        <template #default="scope"
          >#{{ scope.row.article_id }}
          {{ scope.row.article_title ?? "" }}</template
        >
      </el-table-column>
      <el-table-column label="平台" min-width="130">
        <template #default="scope">{{
          platformLabel(scope.row.platform)
        }}</template>
      </el-table-column>
      <el-table-column label="版本" min-width="80">
        <template #default="scope">
          <span class="ver">
            <span>v{{ scope.row.version ?? "?" }}</span>
            <el-tag
              v-if="scope.row.version_outdated"
              class="ver-tag"
              type="warning"
              >内容已更新</el-tag
            >
            <el-tag v-if="scope.row.stale" class="ver-tag" type="danger"
              >超期未审</el-tag
            >
          </span>
        </template>
      </el-table-column>
      <el-table-column label="审核" min-width="92">
        <template #default="scope">{{
          reviewLabel(scope.row.review_policy)
        }}</template>
      </el-table-column>
      <el-table-column label="发布" min-width="80">
        <template #default="scope">{{
          publishLabel(scope.row.publish_policy)
        }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="88">
        <template #default="scope">
          <el-tag :type="statusMap[scope.row.status]?.type ?? 'warning'">{{
            statusMap[scope.row.status]?.label ?? scope.row.status
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="180">
        <template #default="scope">{{
          fmtTime(scope.row.created_at)
        }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="280">
        <template #default="scope">
          <div class="row-actions">
            <template v-if="scope.row.status === 'pending'">
              <el-button
                v-if="scope.row.version_outdated"
                type="warning"
                plain
                @click="refreshVersion(scope.row)"
                >刷新版本</el-button
              >
              <el-button type="primary" @click="approve(scope.row)"
                >通过</el-button
              >
              <el-button type="danger" plain @click="reject(scope.row)"
                >拒绝</el-button
              >
            </template>
            <!-- §9.2：编辑新版本后重新送审（重绑版本并回到待审核） -->
            <el-button
              v-if="scope.row.status === 'rejected'"
              type="warning"
              plain
              @click="refreshVersion(scope.row)"
              >{{
                scope.row.version_outdated ? "刷新版本重新送审" : "重新送审"
              }}</el-button
            >
            <el-button text @click="openEdit(scope.row)">编辑</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑文章（§38 [编辑]） -->
    <el-dialog
      v-model="showEdit"
      :title="`编辑文章 · ${editTarget?.article_title ?? ''}`"
      min-width="640px"
    >
      <el-form label-position="top">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="editForm.content" type="textarea" :rows="10" />
        </el-form-item>
        <div class="form-actions">
          <el-button @click="showEdit = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveEdit"
            >保存修改</el-button
          >
        </div>
      </el-form>
      <p class="edit-note">
        保存后当前审核仍针对旧版本，请点击「刷新版本」重绑最新内容
      </p>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
} from "element-plus";
import api from "../api";
import { platformLabel } from "../platforms";

const reviews = ref<any[]>([]);

const statusMap: Record<
  string,
  { label: string; type: "warning" | "success" | "danger" }
> = {
  pending: { label: "待审核", type: "warning" },
  approved: { label: "已通过", type: "success" },
  rejected: { label: "已拒绝", type: "danger" },
};
const reviewLabel = (v: string) =>
  (({ always: "始终审核", optional: "可选审核", never: "无需审核" }) as any)[
    v
  ] ?? v;
const publishLabel = (v: string) =>
  (
    ({
      automatic: "自动",
      manual: "手动",
      scheduled: "定时",
      disabled: "禁止",
    }) as any
  )[v] ?? v;
const fmtTime = (t: string) => (t ? t.slice(0, 19).replace("T", " ") : "");

async function load() {
  const r = await api.get("/reviews");
  reviews.value = r.data;
}

async function approve(row: any) {
  if (row.version_outdated) {
    ElMessage.warning("内容已更新，请先「刷新版本」再审核");
    return;
  }
  try {
    await api.post(`/reviews/${row.id}/approve`);
    ElMessage.success(`审核 #${row.id} 已通过`);
    load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function reject(row: any) {
  try {
    await api.post(`/reviews/${row.id}/reject`);
    ElMessage.info("已拒绝。编辑文章后点击「重新送审」即可再次进入待审核");
    load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function refreshVersion(row: any) {
  try {
    const r = await api.post(`/reviews/${row.id}/refresh`);
    ElMessage.success(
      r.data.version ? `已刷新到最新版本（v${r.data.version}）` : "已刷新到最新版本",
    );
    load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "刷新失败");
  }
}

// ---- 编辑 ----
const showEdit = ref(false);
const saving = ref(false);
const editTarget = ref<any>(null);
const editForm = ref({ title: "", content: "" });

function openEdit(row: any) {
  editTarget.value = row;
  api.get(`/articles/${row.article_id}`).then((r) => {
    editForm.value = { title: r.data.title, content: r.data.content };
    showEdit.value = true;
  });
}

async function saveEdit() {
  saving.value = true;
  try {
    await api.patch(`/articles/${editTarget.value.article_id}`, editForm.value);
    ElMessage.success("文章已保存，审核列表将显示「内容已更新」");
    showEdit.value = false;
    load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

// ---- SSE 实时刷新（§42） ----
let es: EventSource | null = null;
onMounted(() => {
  load();
  es = new EventSource("/api/events");
  es.onmessage = () => load();
});
onUnmounted(() => es?.close());
</script>

<style scoped>
.ver {
  display: inline-flex;
  align-items: center;
}
.ver-tag {
  margin-left: 6px;
}
.row-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 8px 0;
}
.form-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.edit-note {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--el-color-warning);
}
</style>
