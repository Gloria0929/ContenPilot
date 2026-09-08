<template>
  <div class="platforms">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>平台</span>
          <el-button text :loading="loading" @click="load"> 刷新 </el-button>
        </div>
      </template>
      <el-table :data="platforms">
        <el-table-column type="index" label="ID" min-width="56" />
        <el-table-column label="平台" min-width="160">
          <template #default="scope">{{
            platformLabel(scope.row.name)
          }}</template>
        </el-table-column>
        <el-table-column label="发布方式">
          <template #default="scope">
            <el-tag>
              {{ modeLabel[scope.row.mode] ?? scope.row.mode }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号数" min-width="90">
          <template #default="scope">
            {{
              accounts.filter((a) => a.platform === scope.row.name).length || 0
            }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>浏览器会话（账号锁状态）</span>
          <span class="card-extra">
            <el-tag :type="busyCount ? 'warning' : 'success'">
              {{ busyCount ? `${busyCount} 个占用中` : "全部空闲" }}
            </el-tag>
            <el-button text :loading="loading" @click="load"> 刷新 </el-button>
          </span>
        </div>
      </template>
      <el-table :data="sessions">
        <el-table-column type="index" label="ID" min-width="56" />
        <el-table-column label="账号" min-width="180">
          <template #default="scope">{{ accountLabel(scope.row) }}</template>
        </el-table-column>
        <el-table-column label="平台" min-width="130">
          <template #default="scope">{{
            platformLabel(scope.row.platform)
          }}</template>
        </el-table-column>
        <el-table-column label="状态" min-width="100">
          <template #default="scope">
            <el-tag :type="scope.row.status === 'busy' ? 'warning' : 'success'">
              {{ lockLabel[scope.row.status] ?? scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="持有任务" min-width="100">
          <template #default="scope">
            {{
              scope.row.current_task_id ? `#${scope.row.current_task_id}` : "-"
            }}
          </template>
        </el-table-column>
        <el-table-column label="登录态" min-width="90">
          <template #default="scope">
            <el-tag :type="scope.row.session_path ? 'success' : undefined">
              {{ scope.row.session_path ? "已保存" : "未登录" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="锁定时间" min-width="170">
          <template #default="scope">{{
            fmtTime(scope.row.locked_at)
          }}</template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!sessions.length"
        description="暂无浏览器会话记录"
        :image-size="60"
        style="padding: 24px 0"
      />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>账号登录</span>
          <span class="card-extra">
            <el-tag v-if="loginRunningCount" type="warning">
              {{ loginRunningCount }} 个登录中
            </el-tag>
            <el-button text :loading="loading" @click="load"> 刷新 </el-button>
          </span>
        </div>
      </template>
      <p class="vnc-hint">
        点击「打开登录」会在服务器打开该平台的浏览器登录页（显示在下方 noVNC
        画面中），完成登录后自动保存登录态；若有等待授权的任务也会自动恢复。
      </p>
      <el-table :data="browserAccounts">
        <el-table-column type="index" label="ID" min-width="56" />
        <el-table-column label="账号" min-width="180" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.name || scope.row.key }}
          </template>
        </el-table-column>
        <el-table-column label="平台" min-width="150">
          <template #default="scope">{{
            platformLabel(scope.row.platform)
          }}</template>
        </el-table-column>
        <el-table-column label="登录态" min-width="90">
          <template #default="scope">
            <el-tag :type="hasSession(scope.row) ? 'success' : undefined">
              {{ hasSession(scope.row) ? "已保存" : "未登录" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="登录状态" min-width="160">
          <template #default="scope">
            <el-tag
              v-if="loginState(scope.row)"
              :type="loginState(scope.row).tag"
            >
              {{ loginState(scope.row).label }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="110">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              :loading="startingKey === scope.row.key"
              @click="startLogin(scope.row)"
            >
              打开登录
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!browserAccounts.length"
        description="暂无浏览器平台的账号，请先在账号管理中添加"
        :image-size="60"
        style="padding: 24px 0"
      />
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>可视化人工接管（noVNC）</span>
          <el-link :href="vncExternal" target="_blank" rel="noopener">
            新窗口打开
          </el-link>
        </div>
      </template>
      <p class="vnc-hint">
        在「账号登录」点「打开登录」或在任务等待授权 / 人工时，
        在下方浏览器画面中完成登录、扫码、验证码等操作，
        登录完成后等待授权的任务会自动恢复。需要 Docker 以
        <code>HEADLESS=false</code> 部署；内嵌画面不可用时可点
        「新窗口打开」直连 noVNC（端口 6080）。
      </p>
      <div ref="vncBoxRef" class="vnc-box">
        <!-- 懒加载：滚动到可视区域才挂载 iframe。noVNC 加载后会 focus
             画布，若首屏就挂载会把页面自动拽到底部 -->
        <iframe
          v-if="vncVisible"
          :src="vncFrame"
          title="noVNC"
          class="vnc-frame"
          allow="fullscreen"
        ></iframe>
        <div v-else class="vnc-placeholder">滚动到此处时加载 noVNC 画面</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import {
  ElCard,
  ElButton,
  ElTag,
  ElTable,
  ElTableColumn,
  ElEmpty,
  ElLink,
  ElMessage,
} from "element-plus";
import api from "../api";
import { platformLabel } from "../platforms";

const platforms = ref<any[]>([]);
const sessions = ref<any[]>([]);
const accounts = ref<any[]>([]);
const loading = ref(false);
// 后台登录状态：key = "platform:account_key" → {status, error}
const loginStates = ref<Record<string, any>>({});
const startingKey = ref<string | null>(null);
let loginTimer: ReturnType<typeof setInterval> | null = null;

const modeLabel: Record<string, string> = {
  api: "官方 API",
  browser: "浏览器自动化",
  manual: "手动",
};

const lockLabel: Record<string, string> = {
  idle: "空闲",
  busy: "占用中",
};

function accountLabel(row: any): string {
  if (!row.account_id) return "-";
  const a = accounts.value.find((x) => x.id === row.account_id);
  return a ? `${a.name || a.key}（#${a.id}）` : `#${row.account_id}`;
}

function fmtTime(t: string | null): string {
  return t ? t.slice(0, 19).replace("T", " ") : "-";
}

const busyCount = computed(
  () => sessions.value.filter((s) => s.status === "busy").length,
);

// 直连 noVNC（跨端口 iframe 展示与操作均正常，websockify 直连 :6080）
const vncExternal = computed(
  () =>
    `${window.location.protocol}//${window.location.hostname}:6080/vnc.html`,
);
const vncFrame = computed(
  () =>
    `${window.location.protocol}//${window.location.hostname}:6080/vnc.html?autoconnect=1&resize=scale`,
);

// 浏览器平台的账号（登录入口只对 browser 模式有意义）
const browserAccounts = computed(() =>
  accounts.value.filter((a) =>
    platforms.value.some((p) => p.name === a.platform && p.mode === "browser"),
  ),
);

const loginRunningCount = computed(
  () =>
    Object.values(loginStates.value).filter((s: any) => s?.status === "running")
      .length,
);

function hasSession(row: any): boolean {
  return sessions.value.some((s) => s.account_id === row.id && s.session_path);
}

function loginState(row: any): { label: string; tag: any } | null {
  const st = loginStates.value[`${row.platform}:${row.key}`];
  if (!st) return null;
  if (st.status === "running")
    return { label: "登录中，请在 noVNC 完成", tag: "warning" };
  if (st.status === "success") return { label: "登录成功", tag: "success" };
  return { label: `登录失败：${st.error || "未知原因"}`, tag: "danger" };
}

async function startLogin(row: any) {
  startingKey.value = row.key;
  try {
    const r = await api.post("/browser/login", {
      platform: row.platform,
      account_id: row.id,
    });
    loginStates.value[`${row.platform}:${row.key}`] = {
      status: r.data.status,
    };
    ElMessage.success("已打开浏览器登录窗口，请在下方 noVNC 画面完成登录");
    startPolling();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "启动登录失败");
  } finally {
    startingKey.value = null;
  }
}

// 轮询进行中的登录状态，全部结束后停止
function startPolling() {
  if (loginTimer) return;
  loginTimer = setInterval(async () => {
    const keys = Object.entries(loginStates.value).filter(
      ([, s]) => (s as any)?.status === "running",
    );
    if (!keys.length) {
      stopPolling();
      return;
    }
    for (const [k] of keys) {
      const [platform, key] = k.split(":");
      try {
        const r = await api.get("/browser/login/status", {
          params: { platform, account_key: key },
        });
        if (r.data && r.data.status !== "running") {
          loginStates.value[k] = r.data;
          if (r.data.status === "success") {
            ElMessage.success(`${platform} 登录完成`);
            await load();
          }
        }
      } catch {
        // 单次查询失败忽略，下轮重试
      }
    }
  }, 2000);
}

function stopPolling() {
  if (loginTimer) {
    clearInterval(loginTimer);
    loginTimer = null;
  }
}

async function load() {
  loading.value = true;
  try {
    const [p, s, a] = await Promise.all([
      api.get("/platforms"),
      api.get("/browser/sessions"),
      api.get("/accounts"),
    ]);
    platforms.value = p.data;
    sessions.value = s.data;
    accounts.value = a.data;
  } finally {
    loading.value = false;
  }
}

let es: EventSource | null = null;
// noVNC iframe 懒加载：进入可视区域才挂载（加载时 focus 会把页面拽到底部）
const vncBoxRef = ref<HTMLElement | null>(null);
const vncVisible = ref(false);
let vncObserver: IntersectionObserver | null = null;

onMounted(() => {
  load();
  es = new EventSource("/api/events");
  es.onmessage = () => load();
  if (vncBoxRef.value && "IntersectionObserver" in window) {
    vncObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          vncVisible.value = true;
          vncObserver?.disconnect();
          vncObserver = null;
        }
      },
      { rootMargin: "200px" },
    );
    vncObserver.observe(vncBoxRef.value);
  } else {
    vncVisible.value = true; // 环境不支持时直接挂载
  }
});
onUnmounted(() => {
  es?.close();
  stopPolling();
  vncObserver?.disconnect();
  vncObserver = null;
});
</script>

<style scoped>
.platforms {
  display: grid;
  gap: 20px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-extra {
  display: flex;
  align-items: center;
  gap: 10px;
}
.vnc-hint {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 0 0 14px;
  line-height: 1.7;
}
.vnc-hint code {
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}
.vnc-box {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: #000;
}
/* Xvfb 屏幕为 1280×800（8:5），iframe 按该比例撑满宽度，
   noVNC resize=scale 会随容器等比放大远程画面；过高时限制视口高度 */
.vnc-frame {
  width: 100%;
  aspect-ratio: 8 / 5;
  max-height: 80vh;
  border: 0;
  display: block;
}
.vnc-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  aspect-ratio: 8 / 5;
  max-height: 80vh;
  color: rgba(148, 163, 184, 0.8);
  font-size: 13px;
}
</style>
