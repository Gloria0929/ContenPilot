<template>
  <div class="publish">
    <el-card class="picker-card" shadow="never">
      <h3 class="sec-title">创建发布任务</h3>
      <el-form label-position="top">
        <el-form-item label="文章">
          <el-select
            v-model="articleId"
            placeholder="选择要发布的文章"
            filterable
          >
            <el-option
              v-for="o in articleOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
              :disabled="o.disabled"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="平台">
          <el-select
            v-model="platforms"
            placeholder="选择发布平台（可多选）"
            multiple
          >
            <el-option
              v-for="o in platformOptions"
              :key="o.value"
              :label="o.label"
              :value="o.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="articleId && platforms.length" label="账号">
          <div class="account-grid">
            <div v-for="p in platforms" :key="p" class="account-row">
              <span class="account-platform">{{ p }}</span>
              <el-select
                class="account-select"
                :model-value="accountIds[p] ?? null"
                placeholder="选择账号"
                :disabled="accountOptionsFor(p).length === 0"
                @change="(v: any) => setAccount(p, v)"
              >
                <el-option
                  v-for="o in accountOptionsFor(p)"
                  :key="o.value"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="本次审核策略">
          <el-radio-group v-model="reviewOverride">
            <el-radio value="">跟随策略</el-radio>
            <el-radio value="always">强制审核</el-radio>
            <el-radio value="never">跳过审核</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card
      v-if="articleId && platforms.length"
      class="preview-card"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <span>最终策略预览</span>
          <span class="preview-hint">PolicyResolver 实时解析，非猜测</span>
        </div>
      </template>
      <div v-loading="resolving" class="policy-list">
        <div v-for="row in policyRows" :key="row.platform" class="policy-row">
          <div class="policy-platform">
            {{ row.platform }}
            <el-tag v-if="row.mode === 'api'" type="info"> API </el-tag>
            <el-tag v-else>浏览器</el-tag>
          </div>
          <template v-if="row.resolved">
            <div class="policy-cells">
              <span class="policy-cell">
                审核：<b :class="reviewClass(row)">{{ reviewLabel(row) }}</b>
              </span>
              <span class="policy-cell"
                >发布：<b>{{ publishLabel(row) }}</b></span
              >
            </div>
            <div v-if="row.resolved.is_floor_locked" class="floor-note">
              已被账号/平台层强制审核，不可调低
            </div>
          </template>
          <div v-else class="policy-cells">
            <span class="policy-pending">—</span>
          </div>
        </div>
      </div>
      <div class="actions">
        <el-button
          type="primary"
          size="large"
          :loading="publishing"
          :disabled="!canPublish"
          @click="doPublish"
        >
          创建发布任务
        </el-button>
        <span v-if="!canPublish && articleId && platforms.length" class="hint">
          请为每个平台选择账号
        </span>
      </div>
    </el-card>

    <el-dialog v-model="showResult" title="任务已创建" min-width="480px">
      <el-table :data="resultTasks">
        <el-table-column label="任务" min-width="60">
          <template #default="scope">#{{ scope.row.id }}</template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" min-width="110" />
        <el-table-column label="状态">
          <template #default="scope">
            <el-tag
              :type="
                scope.row.status === 'success'
                  ? 'success'
                  : scope.row.status === 'failed'
                    ? 'danger'
                    : 'warning'
              "
            >
              {{ statusLabel[scope.row.status] ?? scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <div class="result-footer">
          <el-button @click="showResult = false">留在本页</el-button>
          <el-button type="primary" @click="goTasks">查看任务列表</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
  ElButton,
  ElCard,
  ElForm,
  ElFormItem,
  ElSelect,
  ElOption,
  ElRadioGroup,
  ElRadio,
  ElTag,
  ElDialog,
  ElTable,
  ElTableColumn,
  ElMessage,
} from "element-plus";
import api from "../api";

const router = useRouter();

// ---- 数据源 ----
const articles = ref<any[]>([]);
const platformsList = ref<any[]>([]);
const accounts = ref<any[]>([]);

const articleId = ref<number | null>(null);
const platforms = ref<string[]>([]);
const accountIds = ref<Record<string, number>>({});
const reviewOverride = ref("");

const resolving = ref(false);
const policyRows = ref<any[]>([]);
const publishing = ref(false);
const showResult = ref(false);
const resultTasks = ref<any[]>([]);

const articleOptions = computed(() =>
  articles.value.map((a) => ({
    label: `#${a.id} ${a.title}${a.status !== "ready" ? `（${a.status}）` : ""}`,
    value: a.id,
    disabled: a.status !== "ready",
  })),
);
const platformOptions = computed(() =>
  platformsList.value.map((p) => ({
    label: `${p.name}（${p.mode === "api" ? "官方 API" : "浏览器自动化"}）`,
    value: p.name,
  })),
);

function accountOptionsFor(platform: string) {
  return accounts.value
    .filter((a) => a.platform === platform && a.status !== "disabled")
    .map((a) => ({ label: a.name || a.key, value: a.id }));
}

function setAccount(platform: string, v: number | null) {
  if (v == null) delete accountIds.value[platform];
  else accountIds.value[platform] = v;
}

const canPublish = computed(
  () =>
    Boolean(articleId.value && platforms.value.length) &&
    platforms.value.every((p) => accountIds.value[p] != null),
);

// ---- 策略预览（§40：展示 resolve 后的最终策略 + 是否被下限锁定）----
async function refreshPreview() {
  if (!articleId.value || !platforms.value.length) {
    policyRows.value = [];
    return;
  }
  resolving.value = true;
  try {
    const rows = await Promise.all(
      platforms.value.map(async (p) => {
        const meta = platformsList.value.find((x) => x.name === p);
        let resolved = null;
        try {
          const qs = new URLSearchParams({
            article_id: String(articleId.value),
            platform_id: String(meta?.id ?? ""),
          });
          if (accountIds.value[p])
            qs.set("account_id", String(accountIds.value[p]));
          const r = await api.get("/policies/resolve", { params: qs });
          resolved = r.data;
        } catch {
          resolved = null;
        }
        return { platform: p, mode: meta?.mode ?? "browser", resolved };
      }),
    );
    policyRows.value = rows;
  } finally {
    resolving.value = false;
  }
}

watch([articleId, platforms, accountIds], refreshPreview, { deep: true });

function reviewLabel(row: any) {
  const m: Record<string, string> = {
    always: "始终审核",
    optional: "可选审核",
    never: "无需审核",
  };
  return m[row.resolved.review_policy] ?? row.resolved.review_policy;
}
function reviewClass(row: any) {
  return row.resolved.review_policy === "always" ? "rv-always" : "rv-other";
}
function publishLabel(row: any) {
  const m: Record<string, string> = {
    automatic: "自动发布",
    manual: "手动发布",
    scheduled: "定时发布",
    disabled: "禁止发布",
  };
  return m[row.resolved.publish_policy] ?? row.resolved.publish_policy;
}

// ---- 发布 ----
async function doPublish() {
  publishing.value = true;
  try {
    const payload: any = {
      article_id: articleId.value,
      platforms: platforms.value,
      account_ids: { ...accountIds.value },
    };
    if (reviewOverride.value) payload.review_override = reviewOverride.value;
    const r = await api.post("/publish", payload);
    resultTasks.value = r.data;
    showResult.value = true;
    ElMessage.success(`已创建 ${r.data.length} 个发布任务`);
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "创建任务失败");
  } finally {
    publishing.value = false;
  }
}

function goTasks() {
  showResult.value = false;
  router.push("/tasks");
}

const statusLabel: Record<string, string> = {
  pending: "待处理",
  queued: "排队中",
  waiting_review: "等待审核",
  processing: "发布中",
  success: "成功",
  failed: "失败",
};

onMounted(async () => {
  const [a, p, acc] = await Promise.all([
    api.get("/articles"),
    api.get("/platforms"),
    api.get("/accounts"),
  ]);
  articles.value = a.data;
  platformsList.value = p.data;
  accounts.value = acc.data;
});
</script>

<style scoped>
.publish {
  display: grid;
  gap: 20px;
}
.sec-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin: 0 0 16px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.account-grid {
  display: grid;
  gap: 10px;
  min-width: 100%;
}
.account-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.account-platform {
  flex: 0 0 96px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.account-select {
  flex: 1;
}
/* select 撑满表单行（沿用迁移前行为） */
.publish :deep(.el-select) {
  min-width: 100%;
}
/* EP 相邻按钮自带 margin，会与 flex gap 叠加成双倍间距，统一交给 gap */
.publish :deep(.el-button + .el-button) {
  margin-left: 0;
}
.preview-hint {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.policy-list {
  display: grid;
  gap: 12px;
}
.policy-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  padding: 10px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}
.policy-platform {
  flex: 0 0 150px;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.policy-cells {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.rv-always {
  color: var(--el-color-danger);
}
.rv-other {
  color: var(--el-color-success);
}
.floor-note {
  font-size: 12px;
  color: var(--el-color-warning);
}
.policy-pending {
  color: var(--el-text-color-disabled);
}
.actions {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.hint {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}
.result-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
