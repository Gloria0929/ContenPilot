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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { ElCard, ElSwitch, ElMessage } from "element-plus";
import api from "../api";

const items = ref<any[]>([]);
const loading = ref(false);
const saving = ref("");

async function load() {
  loading.value = true;
  try {
    const r = await api.get("/settings");
    items.value = r.data;
  } finally {
    loading.value = false;
  }
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

onMounted(load);
</script>

<style scoped>
.settings {
  max-width: 720px;
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
