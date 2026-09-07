<template>
  <!-- 编辑/新建视图：整页切换，不用弹窗 -->
  <div v-if="showForm" class="article-edit">
    <div class="edit-header">
      <el-button text class="back-btn" @click="showForm = false">
        <el-icon><ArrowLeft /></el-icon>
        <span>返回列表</span>
      </el-button>
      <span class="edit-title">{{
        editingId ? `编辑文章 #${editingId}` : "新建文章"
      }}</span>
    </div>
    <el-form label-position="top" @submit.prevent="save">
      <el-form-item label="标题">
        <el-input v-model="form.title" placeholder="文章标题" />
      </el-form-item>
      <el-form-item label="内容">
        <MdEditor
          v-model="form.content"
          :toolbars="mdToolbars"
          :on-save="save"
          placeholder="支持 Markdown"
          class="editor"
        />
      </el-form-item>
      <el-form-item label="摘要">
        <el-input v-model="form.summary" placeholder="可选" />
      </el-form-item>
      <el-form-item v-if="editingId" label="状态">
        <el-radio-group v-model="form.status">
          <el-radio value="draft">草稿</el-radio>
          <el-radio value="ready">已完成</el-radio>
          <el-radio value="archived">已归档</el-radio>
        </el-radio-group>
      </el-form-item>
      <div class="form-actions">
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">
          {{ editingId ? "保存" : "创建" }}
        </el-button>
      </div>
    </el-form>
  </div>

  <!-- 列表视图 -->
  <div v-else class="articles">
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">新建文章</el-button>
    </div>
    <el-table :data="articles" row-key="id">
      <el-table-column prop="id" label="ID" min-width="56" />
      <el-table-column prop="title" label="标题" show-overflow-tooltip />
      <el-table-column label="状态" min-width="90">
        <template #default="scope">
          <el-tag :type="statusMap[scope.row.status]?.type">
            {{ statusMap[scope.row.status]?.label ?? scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="发布进度" min-width="100">
        <template #default="scope">
          <el-tag :type="aggMap[scope.row.aggregate_status]?.type">
            {{
              aggMap[scope.row.aggregate_status]?.label ??
              scope.row.aggregate_status
            }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="180">
        <template #default="scope">
          {{ fmtTime(scope.row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="200">
        <template #default="scope">
          <div class="row-actions">
            <el-button text @click="openEdit(scope.row)"> 编辑 </el-button>
            <el-button text @click="openPolicy(scope.row)"> 策略 </el-button>
            <el-button text type="danger" @click="confirmRemove(scope.row)">
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- 策略设置（§39） -->
    <el-dialog
      v-model="showPolicy"
      :title="`策略设置 · ${policyArticle?.title ?? ''}`"
      min-width="660px"
    >
      <h4 class="pol-sec">文章级覆盖</h4>
      <p class="pol-hint">
        「跟随上级」= 不配置该层，继承 平台 / 账号 / 全局
        设置；两个维度都跟随上级时保存将删除覆盖
      </p>
      <div class="pol-grid">
        <div class="pol-item">
          <div class="pol-label">
            审核策略
            <el-tag v-if="hasOverride">已覆盖</el-tag>
          </div>
          <el-radio-group v-model="polReview">
            <el-radio value="">跟随上级</el-radio>
            <el-radio value="always">始终审核</el-radio>
            <el-radio value="optional">可选审核</el-radio>
            <el-radio value="never">无需审核</el-radio>
          </el-radio-group>
        </div>
        <div class="pol-item">
          <div class="pol-label">发布策略</div>
          <el-radio-group v-model="polPublish">
            <el-radio value="">跟随上级</el-radio>
            <el-radio value="automatic">自动发布</el-radio>
            <el-radio value="manual">手动发布</el-radio>
            <el-radio value="disabled">禁止发布</el-radio>
          </el-radio-group>
        </div>
      </div>
      <div class="pol-actions">
        <el-button
          type="primary"
          :loading="savingPolicy"
          :disabled="polReview === '' && polPublish === '' && !hasOverride"
          @click="savePolicy"
        >
          {{
            polReview === "" && polPublish === ""
              ? "删除覆盖（跟随上级）"
              : "保存覆盖"
          }}
        </el-button>
      </div>

      <h4 class="pol-sec">各平台最终解析结果</h4>
      <p class="pol-hint">
        只读，由 PolicyResolver 实时计算（含平台 / 账号 / 本文章覆盖）
      </p>
      <div v-loading="resolving" class="pol-list">
        <div v-for="r in resolvedRows" :key="r.platform" class="pol-row">
          <span class="pol-platform">{{ r.platform }}</span>
          <span class="pol-cell">
            审核：<b
              :class="
                r.resolved.review_policy === 'always' ? 'rv-always' : 'rv-ok'
              "
            >
              {{ reviewLabel(r.resolved.review_policy) }}
            </b>
          </span>
          <span class="pol-cell"
            >发布：<b>{{ publishLabel(r.resolved.publish_policy) }}</b></span
          >
          <span v-if="r.resolved.is_floor_locked" class="pol-floor"
            >强制审核，不可调低</span
          >
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElRadioGroup,
  ElRadio,
  ElTag,
  ElMessageBox,
  ElMessage,
} from "element-plus";
import { MdEditor } from "md-editor-v3";
import type { ToolbarNames } from "md-editor-v3";
import { ArrowLeft } from "@element-plus/icons-vue";
// 与主题一致的经典配色（编辑器自带暗色切换不需要）
import "md-editor-v3/lib/style.css";
import api from "../api";

const articles = ref<any[]>([]);
const showForm = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const form = ref({ title: "", content: "", summary: "", status: "draft" });

// 常用工具栏（全量见 md-editor-v3 文档，去掉 html 预览/导出等发布无关项）
const mdToolbars: ToolbarNames[] = [
  "bold",
  "underline",
  "italic",
  "-",
  "title",
  "strikeThrough",
  "sub",
  "sup",
  "quote",
  "unorderedList",
  "orderedList",
  "task",
  "-",
  "codeRow",
  "code",
  "link",
  "image",
  "table",
  "-",
  "revoke",
  "next",
  "save",
  "=",
  "pageFullscreen",
  "preview",
];

const statusMap: Record<string, { label: string; type?: "success" | "info" }> =
  {
    draft: { label: "草稿" },
    ready: { label: "已完成", type: "success" },
    archived: { label: "已归档", type: "info" },
  };

// §27 只读聚合状态（由该文章全部发布任务实时计算）
const aggMap: Record<
  string,
  { label: string; type?: "success" | "warning" | "danger" }
> = {
  none: { label: "未发布" },
  processing: { label: "处理中", type: "warning" },
  partial_success: { label: "部分成功", type: "warning" },
  failed: { label: "发布失败", type: "danger" },
  published: { label: "已发布", type: "success" },
};

function fmtTime(t: string) {
  return t ? t.slice(0, 19).replace("T", " ") : "";
}

async function load() {
  const r = await api.get("/articles");
  articles.value = r.data;
}

function openCreate() {
  editingId.value = null;
  form.value = { title: "", content: "", summary: "", status: "draft" };
  showForm.value = true;
}

function openEdit(row: any) {
  editingId.value = row.id;
  form.value = {
    title: row.title,
    content: row.content,
    summary: row.summary,
    status: row.status,
  };
  showForm.value = true;
}

async function save() {
  if (!form.value.title.trim()) {
    ElMessage.warning("标题不能为空");
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await api.patch(`/articles/${editingId.value}`, form.value);
      ElMessage.success("文章已更新");
    } else {
      await api.post("/articles", form.value);
      ElMessage.success("文章已创建（草稿），完成后请在编辑中改为「已完成」");
    }
    showForm.value = false;
    await load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function confirmRemove(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除文章「${row.title}」吗？已关联发布任务的文章无法删除。`,
      "删除文章",
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
  await remove(row);
}

async function remove(row: any) {
  try {
    await api.delete(`/articles/${row.id}`);
    ElMessage.success("文章已删除");
    await load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  }
}

// ---- 策略覆盖（§39） ----
const showPolicy = ref(false);
const policyArticle = ref<any>(null);
const polReview = ref("");
const polPublish = ref("");
const hasOverride = ref(false);
const savingPolicy = ref(false);
const resolving = ref(false);
const resolvedRows = ref<any[]>([]);

async function openPolicy(row: any) {
  policyArticle.value = row;
  showPolicy.value = true;
  await Promise.all([loadOverride(), refreshResolved()]);
}

async function loadOverride() {
  polReview.value = "";
  polPublish.value = "";
  hasOverride.value = false;
  try {
    const r = await api.get("/policies", {
      params: { scope_type: "article", scope_id: policyArticle.value.id },
    });
    if (r.data) {
      hasOverride.value = true;
      polReview.value = r.data.review_mode;
      polPublish.value = r.data.publish_mode;
    }
  } catch {
    /* 读取失败按未配置处理 */
  }
}

async function refreshResolved() {
  resolving.value = true;
  try {
    const ps = await api.get("/platforms");
    const rows = await Promise.all(
      ps.data.map(async (p: any) => {
        const r = await api.get("/policies/resolve", {
          params: { article_id: policyArticle.value.id, platform_id: p.id },
        });
        return { platform: p.name, resolved: r.data };
      }),
    );
    resolvedRows.value = rows;
  } finally {
    resolving.value = false;
  }
}

async function savePolicy() {
  savingPolicy.value = true;
  try {
    await api.post("/policies", {
      scope_type: "article",
      scope_id: policyArticle.value.id,
      review_mode: polReview.value || null,
      publish_mode: polPublish.value || null,
    });
    ElMessage.success(
      polReview.value || polPublish.value
        ? "文章级覆盖已保存"
        : "已恢复跟随上级",
    );
    await Promise.all([loadOverride(), refreshResolved()]);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    savingPolicy.value = false;
  }
}

function reviewLabel(v: string) {
  const m: Record<string, string> = {
    always: "始终审核",
    optional: "可选审核",
    never: "无需审核",
  };
  return m[v] ?? v;
}
function publishLabel(v: string) {
  const m: Record<string, string> = {
    automatic: "自动发布",
    manual: "手动发布",
    scheduled: "定时发布",
    disabled: "禁止发布",
  };
  return m[v] ?? v;
}

onMounted(load);
</script>

<style scoped>
/* 编辑/新建视图：占满内容区高度，编辑器自适应剩余空间 */
.article-edit {
  max-width: 1100px;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.edit-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}
.back-btn {
  padding: 6px 10px 6px 6px;
  margin-left: -6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.back-btn :deep(.el-icon) {
  margin-right: 2px;
  font-size: 14px;
}
.edit-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.article-edit :deep(.el-form) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.editor {
  /* 视口高 - 顶栏56 - 内边距48 - 标题/摘要/按钮区约 260 */
  height: calc(100dvh - 370px);
  min-height: 360px;
}
.editor :deep(.md-editor-footer) {
  height: auto;
}
.articles {
  width: 100%;
}
.toolbar {
  margin: 16px 0;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  /* 钉在表单底部 + 固定底部间距，避免按钮贴底无留白 */
  padding: 24px;
}
/* 按钮行上方那个表单项自带 18px 底部外边距，会把 .form-actions 的
   margin-top 叠加掩盖；这里清零，让间距完全由 .form-actions 控制 */
.article-edit :deep(.el-form-item:has(+ .form-actions)) {
  margin-bottom: 0;
}
/* EP 相邻按钮自带 margin，会与 flex gap 叠加成双倍间距，统一交给 gap */
.article-edit :deep(.el-button + .el-button),
.articles :deep(.el-button + .el-button) {
  margin-left: 0;
}
.row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.pol-sec {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 4px 0 8px;
}
.pol-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin: 0 0 14px;
}
.pol-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 14px;
}
.pol-item {
  padding: 12px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}
.pol-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.pol-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 22px;
}
.pol-list {
  display: grid;
  gap: 10px;
}
.pol-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  padding: 9px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.pol-platform {
  flex: 0 0 110px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.pol-cell b {
  font-weight: 600;
}
.rv-always {
  color: var(--el-color-danger);
}
.rv-ok {
  color: var(--el-color-success);
}
.pol-floor {
  font-size: 12px;
  color: var(--el-color-warning);
}
</style>
