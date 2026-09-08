<template>
  <div class="settings">
    <el-card shadow="never">
      <template #header>运行时设置</template>
      <div v-loading="loading" class="setting-list">
        <div v-for="s in items" :key="s.key" class="setting-item">
          <div class="setting-info">
            <div class="setting-label">{{ s.label }}</div>
            <div class="setting-desc">{{ s.description }}</div>
          </div>
          <el-switch
            v-if="s.type === 'bool'"
            :model-value="s.value"
            :loading="saving === s.key"
            @change="(v) => save(s.key, v as boolean)"
          />
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="apikey-card">
      <template #header>
        <div class="apikey-header">
          <span>API 密钥</span>
          <el-button type="primary" @click="showCreate = true"
            >生成密钥</el-button
          >
        </div>
      </template>
      <div class="setting-desc apikey-tip">
        生成的 Access Key / Secret Key 用于调用服务器 REST API（AI Skill
        通过配置文件读取密钥调用）。Secret Key 仅在生成时显示一次，请妥善保存。
      </div>
      <el-table :data="apiKeys" row-key="id">
        <el-table-column type="index" label="ID" min-width="60" />
        <el-table-column prop="name" label="名称" show-overflow-tooltip />
        <el-table-column label="Access Key" min-width="160">
          <template #default="scope">
            <span v-if="scope.row.access_key" class="ak-text">{{
              scope.row.access_key
            }}</span>
            <span v-else class="ak-legacy">旧格式密钥</span>
          </template>
        </el-table-column>
        <el-table-column label="跳过审核权限" min-width="110">
          <template #default="scope">
            <el-tag
              size="small"
              :type="scope.row.allow_override_review ? 'warning' : 'info'"
            >
              {{ scope.row.allow_override_review ? "允许" : "不允许" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近使用" min-width="150">
          <template #default="scope">{{
            fmtTime(scope.row.last_used_at)
          }}</template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="scope">{{
            fmtTime(scope.row.created_at)
          }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="90">
          <template #default="scope">
            <el-button text type="danger" @click="remove(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreate" title="生成 API 密钥" width="460px">
      <el-form label-position="top" @submit.prevent="createKey">
        <el-form-item label="名称">
          <el-input
            v-model="createForm.name"
            placeholder="用途标识，如 ai-skill"
          />
        </el-form-item>
        <el-form-item label="允许跳过审核（--no-review）">
          <el-switch v-model="createForm.allow_override_review" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createKey"
          >生成</el-button
        >
      </template>
    </el-dialog>

    <el-dialog
      v-model="showResult"
      title="密钥已生成"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="Secret Key 仅显示这一次，关闭后无法再次查看"
        class="result-alert"
      />
      <el-form label-position="top">
        <el-form-item label="Access Key">
          <div class="key-row">
            <el-input :model-value="created.access_key" readonly />
            <el-button @click="copy(created.access_key)">复制</el-button>
          </div>
        </el-form-item>
        <el-form-item label="Secret Key">
          <div class="key-row">
            <el-input :model-value="created.secret_key" readonly />
            <el-button @click="copy(created.secret_key)">复制</el-button>
          </div>
        </el-form-item>
        <el-form-item
          label="配置文件（保存到 ~/.contentpilot/api_client.json，供 AI Skill 调用 API）"
        >
          <div class="key-row">
            <el-input
              :model-value="configSnippet"
              type="textarea"
              :rows="5"
              readonly
            />
            <div class="key-actions">
              <el-button @click="copy(configSnippet)">复制</el-button>
              <el-button type="primary" plain @click="downloadConfig"
                >下载</el-button
              >
            </div>
          </div>
          <div class="key-tip">
            下载后执行：<code
              >mkdir -p ~/.contentpilot &amp;&amp; mv
              ~/Downloads/api_client.json ~/.contentpilot/ &amp;&amp; chmod 600
              ~/.contentpilot/api_client.json</code
            >
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" @click="showResult = false"
          >我已保存</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import {
  ElAlert,
  ElButton,
  ElCard,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessageBox,
  ElMessage,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
} from "element-plus";
import api from "../api";

const items = ref<any[]>([]);
const loading = ref(false);
const saving = ref("");

const apiKeys = ref<any[]>([]);
const showCreate = ref(false);
const creating = ref(false);
const createForm = ref({ name: "", allow_override_review: false });
const showResult = ref(false);
const created = ref({ access_key: "", secret_key: "" });

const configSnippet = computed(() => {
  const base = window.location.origin;
  return JSON.stringify(
    {
      base_url: base,
      access_key: created.value.access_key,
      secret_key: created.value.secret_key,
    },
    null,
    2,
  );
});

const fmtTime = (t: string | null) =>
  t ? t.slice(0, 19).replace("T", " ") : "—";

async function load() {
  loading.value = true;
  try {
    const r = await api.get("/settings");
    items.value = r.data;
  } finally {
    loading.value = false;
  }
}

async function loadKeys() {
  const r = await api.get("/auth/api_keys");
  apiKeys.value = r.data;
}

async function save(key: string, value: boolean) {
  saving.value = key;
  try {
    await api.post("/settings", { key, value });
    ElMessage.success("设置已保存");
    await load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = "";
  }
}

async function createKey() {
  creating.value = true;
  try {
    const r = await api.post("/auth/api_keys", {
      name: createForm.value.name.trim() || "default",
      allow_override_review: createForm.value.allow_override_review,
    });
    created.value = {
      access_key: r.data.access_key,
      secret_key: r.data.secret_key,
    };
    showCreate.value = false;
    showResult.value = true;
    createForm.value = { name: "", allow_override_review: false };
    await loadKeys();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "生成失败");
  } finally {
    creating.value = false;
  }
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除密钥「${row.name || row.access_key || row.id}」吗？删除后使用该密钥的调用将立即失效，且不可恢复。`,
      "删除确认",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  try {
    await api.delete(`/auth/api_keys/${row.id}`);
    ElMessage.success("已删除");
    await loadKeys();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  }
}

async function copy(text: string) {
  try {
    // clipboard API 仅在 HTTPS / localhost 可用，HTTP 访问服务器时降级 execCommand
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    ElMessage.success("已复制");
  } catch {
    ElMessage.error("复制失败，请手动选择复制");
  }
}

function downloadConfig() {
  const blob = new Blob([configSnippet.value], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "api_client.json";
  a.click();
  URL.revokeObjectURL(url);
  ElMessage.success(
    "已下载 api_client.json，请移动到 ~/.contentpilot/ 并设置权限 600",
  );
}

onMounted(() => {
  load();
  loadKeys();
});
</script>

<style scoped>
.settings {
  display: grid;
  gap: 16px;
}
.apikey-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.apikey-tip {
  margin-bottom: 12px;
}
.ak-text {
  font-family: monospace;
  font-size: 12px;
}
.ak-legacy {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.result-alert {
  margin-bottom: 16px;
}
.key-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.key-row .el-button {
  flex-shrink: 0;
}
/* 去除 Element Plus 相邻按钮默认 margin-left:12px，改为按钮内边距 */
.key-actions :deep(.el-button + .el-button) {
  margin-left: 0;
  padding-left: 27px; /* 默认 15px + 12px 转为内边距 */
}
.setting-list {
  display: grid;
  gap: 14px;
}
.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 16px 18px;
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
}
.setting-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.setting-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
  line-height: 1.6;
}
</style>
