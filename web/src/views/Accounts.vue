<template>
  <div class="accounts">
    <div class="toolbar">
      <el-button type="primary" @click="openAdd">添加账号</el-button>
    </div>
    <el-table :data="accounts" row-key="id">
      <el-table-column prop="id" label="ID" min-width="60" />
      <el-table-column prop="key" label="标识" show-overflow-tooltip />
      <el-table-column label="平台" min-width="140">
        <template #default="scope">
          <el-tag size="small">{{ scope.row.platform }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" show-overflow-tooltip />
      <el-table-column label="状态" min-width="100">
        <template #default="scope">
          <el-tag :type="statusInfo(scope.row.status).type">
            {{ statusInfo(scope.row.status).label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="180">
        <template #default="scope">
          <div class="row-actions">
            <el-button text @click="openEdit(scope.row)"> 编辑 </el-button>
            <el-button
              v-if="scope.row.status !== 'disabled'"
              text
              type="warning"
              @click="confirmDisable(scope.row)"
            >
              停用
            </el-button>
            <el-button
              v-else
              text
              type="success"
              @click="toggleEnabled(scope.row, true)"
            >
              启用
            </el-button>
            <el-button text type="danger" @click="confirmRemove(scope.row)">
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="showForm"
      :title="editingId ? '编辑账号' : '添加账号'"
      width="460px"
    >
      <el-form label-position="top" @submit.prevent="save">
        <el-form-item label="平台">
          <el-select
            v-model="form.platform"
            placeholder="选择平台"
            filterable
            allow-create
          >
            <el-option
              v-for="opt in platformOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editingId" label="标识">
          <el-input
            v-model="form.key"
            placeholder="唯一业务标识，如 juejin_主号；留空自动生成"
          />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="账号显示名称" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="发布方式">
          <el-radio-group v-model="authMode">
            <el-radio value="browser">浏览器登录</el-radio>
            <el-radio value="api">官方 API</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="!editingId && authMode === 'api'">
          <el-form-item label="API 用户名">
            <el-input
              v-model="form.username"
              placeholder="平台登录用户名（如博客园）"
            />
          </el-form-item>
          <el-form-item label="API 令牌">
            <el-input
              v-model="form.token"
              type="password"
              show-password
              placeholder="访问令牌（如博客园 MetaWeblog 令牌）"
            />
          </el-form-item>
          <el-form-item v-if="form.platform === 'cnblogs'" label="博客名">
            <el-input
              v-model="form.blog_name"
              placeholder="博客地址中 /<博客名>/ 部分；留空取用户名"
            />
          </el-form-item>
          <p class="cred-hint">凭据将加密存储，保存后不再可见</p>
        </template>
        <div class="form-actions">
          <el-button @click="showForm = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="save">
            {{ editingId ? "保存" : "添加" }}
          </el-button>
        </div>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import {
  ElButton,
  ElTable,
  ElTableColumn,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElRadioGroup,
  ElRadio,
  ElTag,
  ElMessageBox,
  ElMessage,
} from "element-plus";
import api from "../api";

const accounts = ref<any[]>([]);
const platformsList = ref<any[]>([]);
const showForm = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
// 浏览器登录（默认）/ 官方 API：对齐 CLI `publisher account add --username --token`
const authMode = ref<"browser" | "api">("browser");
const form = ref({
  platform: null as string | null,
  key: "",
  name: "",
  username: "",
  token: "",
  blog_name: "",
});

const platformOptions = computed(() =>
  platformsList.value.map((p) => ({
    label: `${p.name}（${p.mode === "api" ? "官方 API" : "浏览器自动化"}）`,
    value: p.name,
  })),
);

const statusMap: Record<
  string,
  { label: string; type: "success" | "warning" | "danger" }
> = {
  active: { label: "正常", type: "success" },
  auth_expired: { label: "登录失效", type: "warning" },
  cooling: { label: "冷却中", type: "warning" },
  disabled: { label: "已禁用", type: "danger" },
};

function statusInfo(status: string) {
  return statusMap[status] || { label: status, type: undefined };
}

async function load() {
  const [a, p] = await Promise.all([
    api.get("/accounts"),
    api.get("/platforms"),
  ]);
  accounts.value = a.data;
  platformsList.value = p.data;
}

function openAdd() {
  editingId.value = null;
  authMode.value = "browser";
  form.value = {
    platform: null,
    key: "",
    name: "",
    username: "",
    token: "",
    blog_name: "",
  };
  showForm.value = true;
}

function openEdit(row: any) {
  editingId.value = row.id;
  form.value = {
    platform: row.platform,
    key: row.key,
    name: row.name,
    username: "",
    token: "",
    blog_name: "",
  };
  showForm.value = true;
}

async function save() {
  if (!form.value.platform) {
    ElMessage.warning("请选择平台");
    return;
  }
  const f = form.value;
  let payload: any;
  if (editingId.value) {
    payload = { platform: f.platform, name: f.name };
  } else {
    if (authMode.value === "api" && (!f.username.trim() || !f.token.trim())) {
      ElMessage.warning("官方 API 方式需要填写用户名和令牌");
      return;
    }
    // 标识留空自动生成（与 CLI 相同规则）
    const key =
      f.key.trim() ||
      `${f.platform}_${f.name.trim() || f.username.trim() || "default"}`;
    payload = { key, platform: f.platform, name: f.name };
    if (authMode.value === "api") {
      payload.credentials = {
        username: f.username.trim(),
        token: f.token.trim(),
        ...(f.platform === "cnblogs"
          ? { blog_name: f.blog_name.trim() || f.username.trim() }
          : {}),
      };
    }
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await api.patch(`/accounts/${editingId.value}`, payload);
      ElMessage.success("账号已更新");
    } else {
      await api.post("/accounts", payload);
      ElMessage.success(
        authMode.value === "api" && !editingId.value
          ? "账号已添加，凭据已加密保存"
          : "账号已添加",
      );
    }
    showForm.value = false;
    await load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败");
  } finally {
    saving.value = false;
  }
}

async function confirmDisable(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定停用账号「${row.name || row.key}」吗？停用后新发布任务将被拦截，历史任务保留，可随时重新启用。`,
      "停用账号",
      {
        confirmButtonText: "停用",
        cancelButtonText: "取消",
        type: "warning",
      },
    );
  } catch {
    return;
  }
  await toggleEnabled(row, false);
}

async function toggleEnabled(row: any, enabled: boolean) {
  try {
    await api.patch(`/accounts/${row.id}`, {
      status: enabled ? "active" : "disabled",
    });
    ElMessage.success(enabled ? "账号已启用" : "账号已停用");
    await load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "操作失败");
  }
}

async function confirmRemove(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${row.name || row.key}」吗？`,
      "删除账号",
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
    await api.delete(`/accounts/${row.id}`);
    ElMessage.success("账号已删除");
    await load();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "删除失败");
  }
}

onMounted(load);
</script>

<style scoped>
.toolbar {
  margin: 16px 0;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 8px 0;
}
.cred-hint {
  margin: -4px 0 8px;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
</style>
