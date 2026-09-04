<template>
  <div class="dash">
    <section class="stat-group">
      <h3 class="group-title">内容概览</h3>
      <div class="card-row">
        <el-card
          v-for="s in overview"
          :key="s.label"
          class="stat-card"
          shadow="hover"
        >
          <span
            class="accent"
            :class="s.tone ?? 'neutral'"
            aria-hidden="true"
          ></span>
          <div class="stat-body">
            <div class="stat-value">{{ s.count }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </el-card>
      </div>
    </section>

    <section class="stat-group">
      <h3 class="group-title">发布状态（任务级）</h3>
      <div class="card-row">
        <el-card
          v-for="s in statuses"
          :key="s.label"
          class="stat-card"
          :class="s.tone"
          shadow="hover"
        >
          <span
            class="accent"
            :class="s.tone ?? 'neutral'"
            aria-hidden="true"
          ></span>
          <div class="stat-body">
            <div class="stat-value">{{ s.count }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </el-card>
      </div>
    </section>

    <section class="stat-group">
      <h3 class="group-title">文章发布进度（聚合）</h3>
      <div class="card-row">
        <el-card
          v-for="s in aggregates"
          :key="s.label"
          class="stat-card"
          :class="s.tone"
          shadow="hover"
        >
          <span
            class="accent"
            :class="s.tone ?? 'neutral'"
            aria-hidden="true"
          ></span>
          <div class="stat-body">
            <div class="stat-value">{{ s.count }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </el-card>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { ElCard } from "element-plus";
import api from "../api";

type Stat = { label: string; count: number; tone?: string };

const stats = ref<Stat[]>([]);
const aggStats = ref<Stat[]>([]);

const overview = computed(() => stats.value.filter((s) => !s.tone));
const statuses = computed(() => stats.value.filter((s) => s.tone));
// 文章级只读聚合状态（§27：由该文章全部发布任务实时计算）
const aggregates = computed(() => aggStats.value);

async function load() {
  const [articles, tasks] = await Promise.all([
    api.get("/articles"),
    api.get("/tasks"),
  ]);
  const t = tasks.data;
  const by = (s: string) => t.filter((x: any) => x.status === s).length;
  stats.value = [
    { label: "文章总数", count: articles.data.length },
    { label: "待审核", count: by("waiting_review") },
    { label: "待发布", count: by("pending") + by("queued") },
    { label: "发布中", count: by("processing") },
    { label: "发布成功", count: by("success"), tone: "ok" },
    { label: "发布失败", count: by("failed"), tone: "bad" },
    { label: "等待授权", count: by("waiting_auth"), tone: "wait" },
    { label: "等待人工", count: by("waiting_manual"), tone: "wait" },
    { label: "超时", count: by("timeout"), tone: "bad" },
  ];
  const list = articles.data;
  const byAgg = (s: string) =>
    list.filter((x: any) => (x.aggregate_status ?? "none") === s).length;
  aggStats.value = [
    { label: "未发布", count: byAgg("none") },
    { label: "处理中", count: byAgg("processing"), tone: "wait" },
    { label: "部分成功", count: byAgg("partial_success"), tone: "wait" },
    { label: "发布失败", count: byAgg("failed"), tone: "bad" },
    { label: "已发布", count: byAgg("published"), tone: "ok" },
  ];
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
  max-width: 1200px;
  display: grid;
  gap: 26px;
}

.group-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.05em;
  color: var(--el-text-color-secondary);
  margin: 10px 0 14px;
}

/* 横向统计卡片：左侧色条 + 数值/标签，随内容自适应换行 */
.card-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: stretch;
}

.stat-card {
  flex: 0 0 auto;
  min-width: 158px;
  --el-card-padding: 0;
}
.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 20px;
}

.accent {
  flex-shrink: 0;
  width: 4px;
  height: 34px;
  border-radius: 4px;
  background: var(--el-color-primary);
}
.accent.ok {
  background: var(--el-color-success);
}
.accent.bad {
  background: var(--el-color-danger);
}
.accent.wait {
  background: var(--el-color-warning);
}

.stat-value {
  font-size: 25px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  margin-top: 5px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
</style>
