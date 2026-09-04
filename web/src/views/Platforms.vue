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
        <el-table-column prop="id" label="ID" min-width="56" />
        <el-table-column prop="name" label="平台" min-width="160" />
        <el-table-column label="发布方式">
          <template #default="scope">
            <el-tag :type="scope.row.mode === 'api' ? 'info' : undefined">
              {{ modeLabel[scope.row.mode] ?? scope.row.mode }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号数" min-width="90">
          <template #default="scope">
            {{
              accounts.filter((a) => a.platform === scope.row.name).length ||
              "-"
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
        <el-table-column prop="id" label="ID" min-width="56" />
        <el-table-column label="账号" min-width="180">
          <template #default="scope">{{ accountLabel(scope.row) }}</template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="120" />
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
          <span>可视化人工接管（noVNC）</span>
          <el-link :href="vncExternal" target="_blank" rel="noopener">
            新窗口打开
          </el-link>
        </div>
      </template>
      <p class="vnc-hint">
        任务进入「等待授权 /
        等待人工」时，在下方浏览器画面中完成扫码、验证码等操作，
        完成后回到任务列表点「恢复」。需要 Docker 以
        <code>HEADLESS=false</code> 部署；内嵌画面不可用时可点
        「新窗口打开」直连 noVNC（端口 6080）。
      </p>
      <div class="vnc-box">
        <iframe
          src="/vnc/vnc.html?autoconnect=1&resize=scale"
          title="noVNC"
          class="vnc-frame"
        ></iframe>
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
} from "element-plus";
import api from "../api";

const platforms = ref<any[]>([]);
const sessions = ref<any[]>([]);
const accounts = ref<any[]>([]);
const loading = ref(false);

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

// 直连 noVNC（Docker 部署下 /vnc 代理不可用时的兜底入口）
const vncExternal = computed(
  () =>
    `${window.location.protocol}//${window.location.hostname}:6080/vnc.html`,
);

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
onMounted(() => {
  load();
  es = new EventSource("/api/events");
  es.onmessage = () => load();
});
onUnmounted(() => es?.close());
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
.vnc-frame {
  width: 100%;
  height: 480px;
  border: 0;
  display: block;
}
</style>
