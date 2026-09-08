<template>
  <div class="dash">
    <!-- 欢迎横幅：问候 + 概要 + 发布成功率环形图 -->
    <section class="hero">
      <div class="hero-main">
        <div class="hero-hi">{{ greeting }}，欢迎回来</div>
        <div class="hero-date">{{ todayText }}</div>
        <div class="hero-desc">
          共 <b>{{ articles.length }}</b> 篇文章 ·
          <b>{{ tasks.length }}</b> 个发布任务 ·
          <b>{{ accountCount }}</b> 个平台账号
        </div>
        <div class="hero-actions">
          <router-link to="/articles" custom v-slot="{ navigate }">
            <el-button @click="navigate">管理文章</el-button>
          </router-link>
          <router-link to="/publish" custom v-slot="{ navigate }">
            <el-button type="primary" @click="navigate">新建发布</el-button>
          </router-link>
          <router-link to="/tasks" custom v-slot="{ navigate }">
            <el-button @click="navigate">查看任务</el-button>
          </router-link>
        </div>
      </div>
      <div class="hero-ring">
        <svg viewBox="0 0 120 120" class="ring" aria-hidden="true">
          <circle class="ring-track" cx="60" cy="60" r="52" />
          <circle
            class="ring-value"
            cx="60"
            cy="60"
            r="52"
            :stroke-dasharray="ringDash"
          />
        </svg>
        <div class="ring-text">
          <div class="ring-num">{{ successRate === null ? "—" : successRate + "%" }}</div>
          <div class="ring-label">发布成功率</div>
        </div>
      </div>
    </section>

    <!-- 核心指标：图标 + 数值 + 说明 -->
    <section class="kpi-grid">
      <el-card v-for="k in kpis" :key="k.label" class="kpi" shadow="hover">
        <div class="kpi-icon" :class="k.tone">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path :d="k.icon" />
          </svg>
        </div>
        <div class="kpi-body">
          <div class="kpi-value">{{ k.count }}</div>
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-sub">{{ k.sub }}</div>
        </div>
      </el-card>
    </section>

    <div class="grid-2">
      <div class="col-left">
        <!-- 任务状态分布：堆叠比例条 + 图例 -->
        <el-card class="panel" shadow="hover">
          <template #header>
            <span class="panel-title">任务状态分布</span>
            <span class="panel-sub">共 {{ tasks.length }} 个发布任务</span>
          </template>
          <div class="stack-bar" v-if="tasks.length">
            <div
              v-for="seg in statusSegments"
              :key="seg.label"
              class="stack-seg"
              :class="seg.tone"
              :style="{ flex: seg.count }"
              :title="`${seg.label} ${seg.count}`"
            ></div>
          </div>
          <el-empty v-else description="暂无发布任务" :image-size="64" />
          <div class="legend" v-if="tasks.length">
            <div
              v-for="seg in statusSegments"
              :key="seg.label"
              class="legend-item"
            >
              <span class="dot" :class="seg.tone"></span>
              <span class="legend-label">{{ seg.label }}</span>
              <span class="legend-count">{{ seg.count }}</span>
            </div>
          </div>
        </el-card>

        <!-- 文章发布进度：每状态一行比例条 -->
        <el-card class="panel" shadow="hover">
          <template #header>
            <span class="panel-title">文章发布进度</span>
            <span class="panel-sub">共 {{ articles.length }} 篇文章</span>
          </template>
          <div class="agg-row" v-for="a in aggregates" :key="a.label">
            <div class="agg-head">
              <span class="agg-label">
                <span class="dot" :class="a.tone"></span>{{ a.label }}
              </span>
              <span class="agg-num">{{ a.count }} 篇</span>
            </div>
            <div class="agg-track">
              <div
                class="agg-fill"
                :class="a.tone"
                :style="{ width: aggPercent(a.count) + '%' }"
              ></div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 最近任务 -->
      <el-card class="panel" shadow="hover">
        <template #header>
          <span class="panel-title">最近任务</span>
          <router-link to="/tasks" class="panel-link">全部任务</router-link>
        </template>
        <div v-if="recentTasks.length" class="task-list">
          <router-link
            v-for="t in recentTasks"
            :key="t.id"
            to="/tasks"
            class="task-item"
          >
            <span class="task-platform">{{ t.platform }}</span>
            <span class="task-title">{{ t.title || `文章 #${t.article_id}` }}</span>
            <span class="task-time">{{ relTime(t.created_at) }}</span>
            <span
              class="task-status"
              :class="statusTone(t.status)"
              >{{ statusLabel[t.status] ?? t.status }}</span
            >
          </router-link>
        </div>
        <el-empty v-else description="暂无发布任务" :image-size="64" />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { ElCard, ElButton, ElEmpty } from "element-plus";
import api from "../api";

type Stat = { label: string; count: number; tone?: string };

const tasks = ref<any[]>([]);
const articles = ref<any[]>([]);
const accountCount = ref(0);

const statusLabel: Record<string, string> = {
  pending: "待发布",
  queued: "排队中",
  processing: "发布中",
  success: "发布成功",
  failed: "发布失败",
  cancelled: "已取消",
  timeout: "超时",
  waiting_review: "待审核",
  waiting_auth: "等待授权",
  waiting_manual: "等待人工",
  blocked: "已阻塞",
};

const by = (s: string) => tasks.value.filter((x) => x.status === s).length;

// 发布成功率：仅统计终态任务（成功/失败/超时）
const successRate = computed(() => {
  const done = by("success") + by("failed") + by("timeout");
  if (!done) return null;
  return Math.round((by("success") / done) * 100);
});

const ringDash = computed(() => {
  const r = 52;
  const c = 2 * Math.PI * r;
  const p = successRate.value ?? 0;
  return `${(c * p) / 100} ${c}`;
});

const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 6) return "夜深了";
  if (h < 12) return "早上好";
  if (h < 14) return "中午好";
  if (h < 18) return "下午好";
  return "晚上好";
});

const todayText = new Date().toLocaleDateString("zh-CN", {
  year: "numeric",
  month: "long",
  day: "numeric",
  weekday: "long",
});

const kpis = computed(() => [
  {
    label: "文章总数",
    count: articles.value.length,
    sub: `已发布 ${byAgg("published")} 篇`,
    tone: "primary",
    icon: "M5 3h11l3 3v15H5zM8 12h8M8 16h5M8 8h5",
  },
  {
    label: "进行中",
    count: by("processing") + by("queued"),
    sub: `待发布 ${by("pending") + by("queued")} 个`,
    tone: "wait",
    icon: "M12 3a9 9 0 1 0 9 9M12 7v5l4 2",
  },
  {
    label: "待处理",
    count: by("waiting_review") + by("waiting_auth") + by("waiting_manual"),
    sub: "审核 / 授权 / 人工",
    tone: "wait",
    icon: "M12 8v4l3 2M4 5h16v14H4z",
  },
  {
    label: "失败与超时",
    count: by("failed") + by("timeout"),
    sub: `成功 ${by("success")} 个`,
    tone: "bad",
    icon: "M12 3l9 16H3zM12 9v5M12 17.5v.5",
  },
]);

// 任务状态分布（只展示有数据的状态，按固定顺序）
const statusOrder: Array<[string, string]> = [
  ["success", "ok"],
  ["processing", "primary"],
  ["queued", "wait"],
  ["pending", "wait"],
  ["waiting_review", "wait"],
  ["waiting_auth", "wait"],
  ["waiting_manual", "wait"],
  ["failed", "bad"],
  ["timeout", "bad"],
  ["cancelled", "neutral"],
  ["blocked", "bad"],
];

const statusSegments = computed(() =>
  statusOrder
    .filter(([s]) => by(s) > 0)
    .map(([s, tone]) => ({
      label: statusLabel[s] ?? s,
      count: by(s),
      tone,
    }))
);

const byAgg = (s: string) =>
  articles.value.filter((x) => (x.aggregate_status ?? "none") === s).length;

const aggregates = computed<Stat[]>(() => [
  { label: "已发布", count: byAgg("published"), tone: "ok" },
  { label: "部分成功", count: byAgg("partial_success"), tone: "wait" },
  { label: "处理中", count: byAgg("processing"), tone: "wait" },
  { label: "发布失败", count: byAgg("failed"), tone: "bad" },
  { label: "未发布", count: byAgg("none"), tone: "neutral" },
]);

const aggPercent = (n: number) =>
  articles.value.length ? (n / articles.value.length) * 100 : 0;

// 最近任务：按创建时间倒序取前 8 条，关联文章标题
const recentTasks = computed(() => {
  const titleOf = new Map(articles.value.map((a: any) => [a.id, a.title]));
  return [...tasks.value]
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    .slice(0, 8)
    .map((t) => ({
      ...t,
      title: titleOf.get(t.article_id) || "",
    }));
});

function statusTone(s: string) {
  if (s === "success") return "ok";
  if (["failed", "timeout", "blocked"].includes(s)) return "bad";
  if (["waiting_review", "waiting_auth", "waiting_manual"].includes(s))
    return "wait";
  if (["processing", "queued"].includes(s)) return "primary";
  return "neutral";
}

function relTime(iso: string) {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "刚刚";
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d} 天前`;
  return new Date(iso).toLocaleDateString("zh-CN");
}

async function load() {
  const [arts, tks, accs] = await Promise.all([
    api.get("/articles"),
    api.get("/tasks"),
    api.get("/accounts").catch(() => ({ data: [] })),
  ]);
  articles.value = arts.data;
  tasks.value = tks.data;
  accountCount.value = accs.data.length ?? 0;
}

let timer: any;
let es: EventSource | null = null;
onMounted(() => {
  load();
  es = new EventSource("/api/events");
  es.onmessage = () => load();
  timer = setInterval(load, 5000);
});
onUnmounted(() => {
  clearInterval(timer);
  es?.close();
});
</script>

<style scoped>
.dash {
  display: grid;
  gap: 22px;
}

/* ===================== 欢迎横幅 ===================== */
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 30px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background:
    radial-gradient(420px 200px at 92% -40%, rgba(47, 169, 140, 0.1), transparent),
    linear-gradient(135deg, #f2faf8 0%, #ffffff 58%);
  box-shadow: var(--el-box-shadow-lighter);
}

.hero-hi {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--el-text-color-primary);
}

.hero-date {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.hero-desc {
  margin-top: 12px;
  font-size: 13.5px;
  color: var(--el-text-color-regular);
}
.hero-desc b {
  color: var(--el-color-primary-dark-2);
  font-variant-numeric: tabular-nums;
}

.hero-actions {
  margin-top: 18px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* 成功率环形图 */
.hero-ring {
  position: relative;
  flex-shrink: 0;
  width: 128px;
  height: 128px;
}
.ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.ring-track,
.ring-value {
  fill: none;
  stroke-width: 10;
}
.ring-track {
  stroke: var(--el-color-primary-light-8);
}
.ring-value {
  stroke: var(--el-color-primary);
  stroke-linecap: round;
  transition: stroke-dasharray 0.5s ease;
}
.ring-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.ring-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-color-primary-dark-2);
  font-variant-numeric: tabular-nums;
}
.ring-label {
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

/* ===================== 核心指标卡 ===================== */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(215px, 1fr));
  gap: 14px;
}

.kpi :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 18px 20px;
}

.kpi-icon {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.kpi-icon svg {
  width: 22px;
  height: 22px;
}
.kpi-icon.primary {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary-dark-2);
}
.kpi-icon.ok {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.kpi-icon.bad {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}
.kpi-icon.wait {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
}

.kpi-value {
  font-size: 25px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.kpi-label {
  margin-top: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-regular);
}

.kpi-sub {
  margin-top: 2px;
  font-size: 11.5px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}

/* ===================== 双列区 ===================== */
.grid-2 {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: 14px;
  align-items: stretch;
}
.col-left {
  display: grid;
  gap: 14px;
  grid-template-rows: auto 1fr;
}

/* 最近任务卡片：撑满列高，列表填充剩余空间 */
.grid-2 > .panel {
  display: flex;
  flex-direction: column;
}
.grid-2 > .panel :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.task-list {
  flex: 1;
  display: grid;
  gap: 4px;
  grid-auto-rows: minmax(40px, auto);
  align-content: start;
}

.panel :deep(.el-card__header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
}
.panel-sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.panel-link {
  font-size: 12.5px;
  color: var(--el-color-primary-dark-2);
  text-decoration: none;
}
.panel-link:hover {
  text-decoration: underline;
}

/* ---- 堆叠比例条 ---- */
.stack-bar {
  display: flex;
  height: 14px;
  border-radius: 7px;
  overflow: hidden;
  gap: 2px;
}
.stack-seg {
  min-width: 4px;
  transition: flex 0.4s ease;
}
.stack-seg.ok { background: var(--el-color-success); }
.stack-seg.bad { background: var(--el-color-danger); }
.stack-seg.wait { background: var(--el-color-warning); }
.stack-seg.primary { background: var(--el-color-primary); }
.stack-seg.neutral { background: var(--el-color-info-light-5); }

.legend {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
  gap: 10px 8px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: var(--el-text-color-regular);
}
.legend-count {
  margin-left: auto;
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.dot.ok { background: var(--el-color-success); }
.dot.bad { background: var(--el-color-danger); }
.dot.wait { background: var(--el-color-warning); }
.dot.primary { background: var(--el-color-primary); }
.dot.neutral { background: var(--el-color-info-light-5); }

/* ---- 文章发布进度 ---- */
.agg-row + .agg-row {
  margin-top: 14px;
}
.agg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.agg-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.agg-num {
  font-size: 12.5px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
.agg-track {
  height: 8px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  overflow: hidden;
}
.agg-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}
.agg-fill.ok { background: var(--el-color-success); }
.agg-fill.bad { background: var(--el-color-danger); }
.agg-fill.wait { background: var(--el-color-warning); }
.agg-fill.neutral { background: var(--el-color-info-light-5); }

/* ---- 最近任务 ---- */
.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 8px;
  text-decoration: none;
  color: inherit;
  transition: background-color 0.15s ease;
}
.task-item:hover {
  background: var(--el-color-primary-light-9);
}
.task-platform {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-color-primary-dark-2);
  background: var(--el-color-primary-light-9);
  padding: 2px 8px;
  border-radius: 6px;
}
.task-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.task-time {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.task-status {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 6px;
}
.task-status.ok {
  color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}
.task-status.bad {
  color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}
.task-status.wait {
  color: var(--el-color-warning);
  background: var(--el-color-warning-light-9);
}
.task-status.primary {
  color: var(--el-color-primary-dark-2);
  background: var(--el-color-primary-light-9);
}
.task-status.neutral {
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-light);
}

/* ===================== 响应式 ===================== */
@media (max-width: 900px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
  .hero {
    flex-direction: column;
    text-align: center;
  }
  .hero-actions {
    justify-content: center;
  }
}
</style>
