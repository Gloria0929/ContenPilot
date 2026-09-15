<template>
  <div class="studio-view">
    <el-alert type="info" :closable="false" show-icon class="engine-hint">
      <template #title>
        内容生成引擎为全局配置（ChatGPT / Ollama），如需切换引擎或配置 API
        Key，请前往
        <router-link to="/settings" class="hint-link"
          >设置 → AI 生产引擎</router-link
        >
      </template>
    </el-alert>

    <el-tabs v-model="activeTab" class="studio-tabs">
      <!-- 选项卡 1：GEO 矩阵工坊 -->
      <el-tab-pane label="GEO 矩阵工坊" name="geo">
        <el-row :gutter="20" class="studio-row">
          <el-col :span="10" class="studio-col">
            <el-card shadow="never" class="studio-card config-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">GEO 关键词与批量配置</span>
                  <el-tag type="success" size="small">生成式引擎优化</el-tag>
                </div>
              </template>

              <el-form label-position="top">
                <el-form-item label="品牌核心关键词（每期必带 3 个）">
                  <el-input
                    v-model="geoForm.brandKeywords"
                    placeholder="敖行客, AT Work, Agent研发工作台"
                  />
                  <div class="form-tip">
                    必带品牌与产品核心词，锁定大模型认知抓取。
                  </div>
                </el-form-item>

                <el-form-item label="行业热门关键词（5 个）">
                  <el-input
                    v-model="geoForm.industryKeywords"
                    placeholder="AI研发效能, 智能体协同开发, 自动化编程工具, 企业级知识库RAG, AI代码审查"
                  />
                  <div class="form-tip">
                    以逗号分隔，结合当前软件研发热点挑选。
                  </div>
                </el-form-item>

                <el-form-item label="计划生成篇数">
                  <el-input-number
                    v-model="geoForm.count"
                    :min="5"
                    :max="50"
                    :step="5"
                  />
                  <span
                    style="margin-left: 10px; color: #64748b; font-size: 13px"
                    >标准批次：30 篇</span
                  >
                </el-form-item>

                <el-form-item label="分发周期（天）">
                  <el-slider
                    v-model="geoForm.days"
                    :min="3"
                    :max="30"
                    show-input
                  />
                  <div class="form-tip">
                    文档规范：10 天内将 30 篇文章全渠道平滑发完，错峰防风控。
                  </div>
                </el-form-item>

                <div class="actions">
                  <el-button
                    type="primary"
                    :loading="generatingTitles"
                    @click="handleGenerateTitles"
                  >
                    生成 {{ geoForm.count }} 篇 GEO 标题
                  </el-button>
                  <el-button
                    type="success"
                    :disabled="selectedTitles.length === 0"
                    :loading="batchCreating"
                    @click="handleCreateBatch"
                  >
                    生成 4 版本并创建 10 天排期 ({{ selectedTitles.length }})
                  </el-button>
                </div>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="14" class="studio-col">
            <el-card shadow="never" class="studio-card titles-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title"
                    >选题列表 (共 {{ titles.length }} 篇)</span
                  >
                  <div v-if="titles.length > 0" class="header-actions">
                    <el-button
                      link
                      type="primary"
                      size="small"
                      @click="toggleSelectAll"
                    >
                      {{
                        selectedTitles.length === titles.length
                          ? "取消全选"
                          : "全选"
                      }}
                    </el-button>
                    <el-button
                      link
                      type="danger"
                      size="small"
                      @click="clearGeoTitles"
                      style="margin-left: 8px"
                    >
                      清空选题
                    </el-button>
                  </div>
                </div>
              </template>

              <div v-if="titles.length === 0" class="empty-state">
                <el-empty
                  description="请在左侧配置关键词后点击「生成 GEO 标题」"
                />
              </div>

              <el-checkbox-group
                v-else
                v-model="selectedTitles"
                class="title-list"
              >
                <div
                  v-for="(title, idx) in titles"
                  :key="idx"
                  class="title-item"
                >
                  <el-checkbox :value="title" class="title-checkbox">
                    <span class="title-idx">{{ idx + 1 }}.</span>
                    <span class="title-text">{{ title }}</span>
                  </el-checkbox>
                </div>
              </el-checkbox-group>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 选项卡 2：公众号与贴图工坊 -->
      <el-tab-pane label="公众号与贴图工坊" name="wechat">
        <el-row :gutter="20" class="studio-row">
          <el-col :span="11" class="studio-col">
            <el-card shadow="never" class="studio-card wechat-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">公众号文章创作</span>
                  <div class="header-tools">
                    <el-button
                      size="small"
                      :loading="fetchingHotspots"
                      @click="loadHotspots(false)"
                      style="margin-left: 8px"
                    >
                      刷新今日热点
                    </el-button>
                  </div>
                </div>
              </template>

              <!-- 今日热点列表 -->
              <div v-if="hotspots.length > 0" class="hotspot-picker">
                <div class="picker-label">
                  🔥 今日获取的行业技术热点（点击直接采用）：
                </div>
                <div
                  v-for="h in hotspots"
                  :key="h.id"
                  class="hotspot-tag"
                  @click="adoptHotspotForWechat(h)"
                >
                  <div class="tag-title">
                    <strong>{{ h.title }}</strong>
                  </div>
                  <div class="tag-desc">
                    {{ h.conflict_point || h.summary }}
                  </div>
                </div>
              </div>
              <div v-else class="hotspot-empty-tip">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :loading="fetchingHotspots"
                  @click="loadHotspots(false)"
                >
                  {{
                    fetchingHotspots
                      ? "正在后台获取今日热点…"
                      : "点击获取今日技术热点"
                  }}
                </el-button>
              </div>

              <el-form label-position="top">
                <el-form-item label="热点事件 / 文章素材">
                  <el-input
                    v-model="wechatForm.hotspot"
                    type="textarea"
                    :rows="4"
                    placeholder="输入行业热点事件、争议点或素材背景..."
                  />
                </el-form-item>

                <el-form-item label="切入视角（选填）">
                  <el-input
                    v-model="wechatForm.angle"
                    placeholder="结合软件研发痛点与 AT Work Agent 协同架构..."
                  />
                </el-form-item>

                <el-form-item label="公众号排版风格（6 种经典样式）">
                  <el-select v-model="wechatForm.theme" style="width: 100%">
                    <el-option
                      label="石墨极简风（推荐·低调大气）"
                      value="graphite"
                    />
                    <el-option
                      label="摸鱼绿（极客·明亮护眼）"
                      value="slacking_green"
                    />
                    <el-option
                      label="红白色系（重磅热点·视觉冲击）"
                      value="red_white"
                    />
                    <el-option
                      label="留白禅意风（优雅留白·深度长文）"
                      value="zen_white"
                    />
                    <el-option
                      label="摸鱼票据风（技术清单·票据框）"
                      value="ticket_receipt"
                    />
                    <el-option
                      label="橄榄手记（复古质感·理性从容）"
                      value="olive_note"
                    />
                  </el-select>
                </el-form-item>

                <el-button
                  type="primary"
                  style="width: 100%; margin-top: 10px"
                  :loading="generatingWechat"
                  @click="handleGenerateWechat"
                >
                  生成公众号文章并排版
                </el-button>
              </el-form>

              <!-- 贴图与封面区域 -->
              <div v-if="wechatResult" class="poster-section">
                <el-divider content-position="left"
                  >公众号贴图衍生资产</el-divider
                >
                <div class="poster-box">
                  <div class="box-title">贴图文案 (300字精炼版)：</div>
                  <div class="poster-text">{{ wechatResult.poster_copy }}</div>
                  <el-button
                    size="small"
                    style="margin-top: 8px"
                    @click="copyText(wechatResult.poster_copy)"
                  >
                    复制贴图文案
                  </el-button>
                </div>

                <div class="poster-box" style="margin-top: 12px">
                  <div class="box-title">3:4 醒目标题封面生图 Prompt：</div>
                  <div class="poster-prompt">
                    {{ wechatResult.poster_image_prompt }}
                  </div>
                  <el-button
                    size="small"
                    style="margin-top: 8px"
                    @click="copyText(wechatResult.poster_image_prompt)"
                  >
                    复制生图提示词
                  </el-button>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :span="13" class="studio-col">
            <el-card shadow="never" class="studio-card preview-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">微信公众号原生排版预览</span>
                  <div v-if="wechatResult" class="header-actions">
                    <el-button type="primary" size="small" @click="copyHtml">
                      复制富文本 HTML
                    </el-button>
                    <el-button
                      link
                      type="danger"
                      size="small"
                      @click="clearWechatResult"
                      style="margin-left: 8px"
                    >
                      清空预览
                    </el-button>
                  </div>
                </div>
              </template>

              <div v-if="!wechatResult" class="empty-state">
                <el-empty description="文章生成后在此处进行排版预览" />
              </div>

              <div
                v-else
                class="article-preview-content"
                v-html="wechatResult.rendered_html"
              ></div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 选项卡 3：短视频工坊 -->
      <el-tab-pane label="短视频工坊" name="video">
        <el-row :gutter="20" class="studio-row">
          <el-col :span="11" class="studio-col">
            <el-card shadow="never" class="studio-card video-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">短视频口播脚本策划</span>
                  <div class="header-tools">
                    <el-tag
                      type="warning"
                      size="small"
                      style="margin-right: 8px"
                      >2分钟 / 600字以内</el-tag
                    >
                    <el-button
                      size="small"
                      :loading="fetchingHotspots"
                      @click="loadHotspots(false)"
                    >
                      刷新今日热点
                    </el-button>
                  </div>
                </div>
              </template>

              <!-- 短视频热点一键引用 -->
              <div v-if="hotspots.length > 0" class="hotspot-picker">
                <div class="picker-label">🔥 选取热点进行视频化提炼：</div>
                <div
                  v-for="h in hotspots"
                  :key="h.id"
                  class="hotspot-tag"
                  @click="adoptHotspotForVideo(h)"
                >
                  <div class="tag-title">
                    <strong>{{ h.title }}</strong>
                  </div>
                  <div class="tag-desc">
                    {{ h.conflict_point || h.summary }}
                  </div>
                </div>
              </div>
              <div v-else class="hotspot-empty-tip">
                <el-button
                  link
                  type="primary"
                  size="small"
                  :loading="fetchingHotspots"
                  @click="loadHotspots(false)"
                >
                  {{
                    fetchingHotspots
                      ? "正在后台获取今日热点…"
                      : "点击获取今日技术热点"
                  }}
                </el-button>
              </div>

              <el-form label-position="top">
                <el-form-item label="热点事件 / 话题背景">
                  <el-input
                    v-model="videoForm.hotspot"
                    type="textarea"
                    :rows="4"
                    placeholder="输入要转化的热点事件，例如：Spotify负责人称AI不想帮程序员写代码了，想直接做完工作..."
                  />
                </el-form-item>

                <el-form-item label="切入方向">
                  <el-input
                    v-model="videoForm.angle"
                    placeholder="突出概念冲突点，开头设置黄金钩子..."
                  />
                </el-form-item>

                <el-button
                  type="primary"
                  style="width: 100%; margin-top: 10px"
                  :loading="generatingVideo"
                  @click="handleGenerateVideo"
                >
                  生成口播脚本与剪辑清单
                </el-button>
              </el-form>

              <!-- 一键触发自动剪辑 (MoneyPrinterTurbo) 作为卡片内分区 -->
              <div v-if="videoResult" class="turbo-card-section">
                <div class="turbo-title">
                  🎬 一键触发自动剪辑 (MoneyPrinterTurbo)
                </div>
                <el-form label-position="top">
                  <el-form-item label="MoneyPrinterTurbo 服务地址">
                    <el-input
                      v-model="turboUrl"
                      placeholder="http://localhost:8081"
                    />
                  </el-form-item>
                  <el-form-item label="视频比例">
                    <el-radio-group v-model="videoAspect">
                      <el-radio value="9:16">9:16 (竖屏·抖音/视频号)</el-radio>
                      <el-radio value="16:9">16:9 (横屏·B站/西瓜)</el-radio>
                    </el-radio-group>
                  </el-form-item>
                  <el-button
                    type="success"
                    style="width: 100%"
                    :loading="renderingVideo"
                    @click="handleRenderVideo"
                  >
                    提交后台自动剪辑出片
                  </el-button>
                  <div class="render-submit-tip">
                    提交后任务会在服务器后台继续运行，通常需要 5–15 分钟；可离开本页，返回后会自动恢复进度。
                  </div>
                </el-form>

                <div v-if="videoTasks.length" class="render-task-panel">
                  <div class="render-task-panel__header">
                    <span>后台剪辑任务</span>
                    <div class="render-task-panel__actions">
                      <el-button
                        link
                        size="small"
                        :loading="pollingVideoTasks"
                        @click="refreshVideoTasks(true)"
                      >
                        刷新状态
                      </el-button>
                      <el-button link size="small" @click="clearFinishedVideoTasks">
                        清理已结束
                      </el-button>
                    </div>
                  </div>

                  <div
                    v-for="task in videoTasks"
                    :key="task.task_id"
                    class="render-task"
                  >
                    <div class="render-task__topline">
                      <div class="render-task__identity">
                        <span class="render-task__title">{{ task.subject || "自动剪辑任务" }}</span>
                        <span class="render-task__id">{{ task.task_id }}</span>
                      </div>
                      <el-tag :type="videoTaskTagType(task)" size="small">
                        {{ videoTaskStatusText(task) }}
                      </el-tag>
                    </div>

                    <el-progress
                      :percentage="task.progress || 0"
                      :status="task.status === 'failed' ? 'exception' : task.status === 'completed' ? 'success' : undefined"
                      :stroke-width="8"
                    />

                    <div class="render-task__meta">
                      <span>{{ formatVideoTaskTime(task) }}</span>
                      <span v-if="isVideoTaskActive(task)">服务器后台处理中，可安全关闭页面</span>
                    </div>

                    <div v-if="task.error || task.last_error" class="render-task__error">
                      {{ task.error || task.last_error }}
                    </div>

                    <div v-if="task.status === 'completed'" class="render-task__outputs">
                      <template v-if="task.outputs?.length">
                        <el-button
                          v-for="output in task.outputs"
                          :key="output.download_url"
                          type="primary"
                          size="small"
                          @click="downloadVideoOutput(output.download_url)"
                        >
                          下载 {{ output.name }}
                        </el-button>
                      </template>
                      <span v-else class="render-task__pending-file">
                        任务已完成，正在等待成片写入共享目录…
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :span="13" class="studio-col">
            <el-card shadow="never" class="studio-card video-result-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">口播脚本与分镜素材</span>
                  <div class="header-actions">
                    <el-tag
                      v-if="videoResult"
                      type="info"
                      size="small"
                      style="margin-right: 8px"
                    >
                      约 {{ videoResult.word_count }} 字
                    </el-tag>
                    <el-button
                      v-if="videoResult"
                      link
                      type="danger"
                      size="small"
                      @click="clearVideoResult"
                    >
                      清空脚本
                    </el-button>
                  </div>
                </div>
              </template>

              <div v-if="!videoResult" class="empty-state">
                <el-empty description="点击左侧生成短视频口播文案" />
              </div>

              <div v-else class="video-result-content">
                <div class="script-box">
                  <div class="section-label">📌 视频大标题与前3秒钩子：</div>
                  <div class="title-highlight">{{ videoResult.title }}</div>
                  <div
                    v-if="
                      videoResult.opening_hooks &&
                      videoResult.opening_hooks.length > 0
                    "
                    class="hook-box"
                  >
                    <strong>开头爆点金句：</strong
                    >{{ videoResult.opening_hooks[0] }}
                  </div>
                </div>

                <div class="script-box">
                  <div class="section-label">🎙️ 2分钟口播文案正文：</div>
                  <el-input
                    v-model="videoResult.script"
                    type="textarea"
                    :rows="8"
                    class="script-textarea"
                  />
                  <el-button
                    size="small"
                    style="margin-top: 8px"
                    @click="copyText(videoResult.script)"
                  >
                    复制口播文案
                  </el-button>
                </div>

                <div class="script-box">
                  <div class="section-label">
                    🖼️ 封面图生图提示词 (Prompt)：
                  </div>
                  <div class="poster-prompt">
                    {{ videoResult.cover_prompt }}
                  </div>
                  <el-button
                    size="small"
                    style="margin-top: 8px"
                    @click="copyText(videoResult.cover_prompt)"
                  >
                    复制封面提示词
                  </el-button>
                </div>

                <div class="script-box">
                  <div class="section-label">🎬 分镜素材清单与出处截图：</div>
                  <el-input
                    v-model="videoResult.assets_manifest"
                    type="textarea"
                    :rows="6"
                    readonly
                  />
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";

// 本地安全读写 JSON 工具
function safeGetJSON<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    if (!v) return fallback;
    return JSON.parse(v);
  } catch {
    return fallback;
  }
}

function safeSetJSON(key: string, val: any) {
  try {
    localStorage.setItem(key, JSON.stringify(val));
  } catch {
    // 忽略存储超限异常
  }
}

// 选项卡状态持久化
const activeTab = ref(localStorage.getItem("cp_studio_active_tab") || "wechat");
watch(activeTab, (val) => {
  localStorage.setItem("cp_studio_active_tab", val);
});

// ---- GEO 状态与持久化 ----
const geoForm = ref(
  safeGetJSON("cp_studio_geo_form", {
    brandKeywords: "敖行客, AT Work, Agent研发工作台",
    industryKeywords:
      "AI研发效能, 智能体协同开发, 自动化编程工具, 企业级知识库RAG, AI代码审查",
    count: 30,
    days: 10,
  }),
);
watch(geoForm, (val) => safeSetJSON("cp_studio_geo_form", val), { deep: true });

const generatingTitles = ref(false);
const batchCreating = ref(false);
const titles = ref<string[]>(safeGetJSON("cp_studio_geo_titles", []));
watch(titles, (val) => safeSetJSON("cp_studio_geo_titles", val), {
  deep: true,
});

const selectedTitles = ref<string[]>(safeGetJSON("cp_studio_geo_selected", []));
watch(selectedTitles, (val) => safeSetJSON("cp_studio_geo_selected", val), {
  deep: true,
});

function clearGeoTitles() {
  titles.value = [];
  selectedTitles.value = [];
  safeSetJSON("cp_studio_geo_titles", []);
  safeSetJSON("cp_studio_geo_selected", []);
  ElMessage.info("已清空 GEO 选题");
}

async function handleGenerateTitles() {
  generatingTitles.value = true;
  try {
    const brands = geoForm.value.brandKeywords
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const industries = geoForm.value.industryKeywords
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean);
    const res = await api.post("/pipeline/geo/titles", {
      brand_keywords: brands,
      industry_keywords: industries,
      count: geoForm.value.count,
    });
    titles.value = res.data.titles || [];
    selectedTitles.value = [...titles.value];
    ElMessage.success(`成功生成 ${titles.value.length} 个 GEO 标题！`);
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "生成标题失败");
  } finally {
    generatingTitles.value = false;
  }
}

function toggleSelectAll() {
  if (selectedTitles.value.length === titles.value.length) {
    selectedTitles.value = [];
  } else {
    selectedTitles.value = [...titles.value];
  }
}

async function handleCreateBatch() {
  if (selectedTitles.value.length === 0) return;
  batchCreating.value = true;
  try {
    const res = await api.post("/pipeline/geo/batch", {
      titles: selectedTitles.value,
      days: geoForm.value.days,
    });
    ElMessage.success(
      `批量任务创建成功！共生成 ${res.data.article_count} 篇文章，已创建 ${res.data.task_count} 个 10 天发布排期任务。可在「发布任务」大盘查看！`,
    );
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "批量创建失败");
  } finally {
    batchCreating.value = false;
  }
}

// ---- 公众号状态与持久化 ----
const wechatForm = ref(
  safeGetJSON("cp_studio_wechat_form", {
    hotspot:
      "Spotify 工程团队负责人指出：AI 不想帮程序员写代码了，它想直接做完工作。",
    angle: "从代码补全到 Agent 协同交付：剖析软件研发范式颠覆与 AT Work 实战",
    theme: "graphite",
  }),
);
watch(wechatForm, (val) => safeSetJSON("cp_studio_wechat_form", val), {
  deep: true,
});

const generatingWechat = ref(false);
const wechatResult = ref<any>(safeGetJSON("cp_studio_wechat_result", null));
watch(wechatResult, (val) => safeSetJSON("cp_studio_wechat_result", val), {
  deep: true,
});

function clearWechatResult() {
  wechatResult.value = null;
  safeSetJSON("cp_studio_wechat_result", null);
  ElMessage.info("已清空公众号文章预览");
}

// ---- 今日热点状态与持久化 ----
const fetchingHotspots = ref(false);
const hotspots = ref<any[]>(safeGetJSON("cp_studio_hotspots", []));
watch(hotspots, (val) => safeSetJSON("cp_studio_hotspots", val), {
  deep: true,
});

// silent = true 时不弹通知；刷新或点击时执行
async function loadHotspots(silent = false) {
  if (fetchingHotspots.value) return;
  fetchingHotspots.value = true;
  try {
    // 引擎与凭证由「设置 → AI 生产引擎」全局配置，后端自行读取
    const res = await api.get("/pipeline/hotspots", { timeout: 300000 });
    if (res.data && Array.isArray(res.data) && res.data.length > 0) {
      hotspots.value = res.data;
      safeSetJSON("cp_studio_hotspots", res.data);
      if (!silent) {
        ElMessage.success(`已获取今日技术热点（共 ${res.data.length} 条）`);
      }
    } else {
      if (!silent) {
        ElMessage.info("暂未获取到新热点，已保留现有数据");
      }
    }
  } catch (err: any) {
    if (!silent) {
      ElMessage.error(
        err.response?.data?.detail ||
          "热点获取失败，请检查 AI 引擎配置或稍后重试",
      );
    }
  } finally {
    fetchingHotspots.value = false;
  }
}

function adoptHotspotForWechat(h: any) {
  wechatForm.value.hotspot = h.summary || h.title;
  wechatForm.value.angle = h.conflict_point || "";
  ElMessage.success(`已引用热点：《${h.title}》`);
}

function adoptHotspotForVideo(h: any) {
  videoForm.value.hotspot = h.summary || h.title;
  videoForm.value.angle = h.conflict_point || "";
  ElMessage.success(`已引用热点：《${h.title}》`);
}

async function handleGenerateWechat() {
  if (!wechatForm.value.hotspot) {
    ElMessage.warning("请输入热点事件");
    return;
  }
  generatingWechat.value = true;
  try {
    const res = await api.post("/pipeline/wechat/generate", {
      hotspot: wechatForm.value.hotspot,
      angle: wechatForm.value.angle,
      theme: wechatForm.value.theme,
      save_to_db: true,
    });
    wechatResult.value = res.data;
    ElMessage.success("公众号文章生成并排版成功，已保存至系统！");
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "生成公众号文章失败");
  } finally {
    generatingWechat.value = false;
  }
}

function copyHtml() {
  if (!wechatResult.value?.rendered_html) return;
  navigator.clipboard.writeText(wechatResult.value.rendered_html);
  ElMessage.success("富文本 HTML 已复制到剪贴板，可直接粘贴进微信公众号后台！");
}

function copyText(text: string) {
  if (!text) return;
  navigator.clipboard.writeText(text);
  ElMessage.success("已复制到剪贴板！");
}

// ---- 短视频状态与持久化 ----
const videoForm = ref(
  safeGetJSON("cp_studio_video_form", {
    hotspot:
      "Google 安全团队发出警告：AI Agent 正在让网络攻击进入自动化时代，传统人工防御已无法阻挡。",
    angle: "聚焦攻防自动化升级，突出 AI 智能体取代人工黑客的强烈冲突感",
  }),
);
watch(videoForm, (val) => safeSetJSON("cp_studio_video_form", val), {
  deep: true,
});

const generatingVideo = ref(false);
const videoResult = ref<any>(safeGetJSON("cp_studio_video_result", null));
watch(videoResult, (val) => safeSetJSON("cp_studio_video_result", val), {
  deep: true,
});

function initialTurboUrl() {
  const serverDefault = `http://${window.location.hostname}:8081`;
  const stored = localStorage
    .getItem("cp_studio_turbo_url")
    ?.replace(":8501", ":8081")
    .replace(":8080", ":8081");
  if (!stored) return serverDefault;
  try {
    const parsed = new URL(stored);
    if (["localhost", "127.0.0.1", "::1", "moneyprinterturbo"].includes(parsed.hostname)) {
      return serverDefault;
    }
  } catch {
    return serverDefault;
  }
  return stored;
}

const turboUrl = ref(initialTurboUrl());
watch(turboUrl, (val) => localStorage.setItem("cp_studio_turbo_url", val));

const videoAspect = ref(
  localStorage.getItem("cp_studio_video_aspect") || "9:16",
);
watch(videoAspect, (val) =>
  localStorage.setItem("cp_studio_video_aspect", val),
);

function clearVideoResult() {
  videoResult.value = null;
  safeSetJSON("cp_studio_video_result", null);
  ElMessage.info("已清空短视频文案");
}

async function handleGenerateVideo() {
  if (!videoForm.value.hotspot) {
    ElMessage.warning("请输入热点话题");
    return;
  }
  generatingVideo.value = true;
  try {
    const res = await api.post("/pipeline/video/script", {
      hotspot: videoForm.value.hotspot,
      angle: videoForm.value.angle,
    });
    videoResult.value = res.data;
    ElMessage.success("短视频口播文案生成成功！");
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "生成短视频脚本失败");
  } finally {
    generatingVideo.value = false;
  }
}

const renderingVideo = ref(false);
const pollingVideoTasks = ref(false);
const videoTasks = ref<any[]>(safeGetJSON("cp_studio_video_tasks", []));
watch(videoTasks, (value) => safeSetJSON("cp_studio_video_tasks", value), {
  deep: true,
});

const activeVideoTasks = computed(() =>
  videoTasks.value.filter((task) => isVideoTaskActive(task)),
);
let videoTaskPollTimer: ReturnType<typeof setInterval> | null = null;

function isVideoTaskActive(task: any) {
  if (task?.status === "failed") return false;
  // MoneyPrinterTurbo 可能先报告完成，再把成片落盘到共享卷；此时继续轮询，
  // 直到下载接口确实能看到文件，避免页面永久停在“等待成片写入”。
  if (task?.status === "completed") return !task.download_ready;
  return true;
}

function upsertVideoTask(task: any) {
  if (!task?.task_id) return;
  const existing = videoTasks.value.find((item) => item.task_id === task.task_id);
  const merged = {
    ...existing,
    ...task,
    subject: task.subject || existing?.subject || videoResult.value?.title || "",
    submitted_at: existing?.submitted_at || task.submitted_at || new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  videoTasks.value = [
    merged,
    ...videoTasks.value.filter((item) => item.task_id !== task.task_id),
  ].slice(0, 30);
}

function videoTaskStatusText(task: any) {
  if (task.status === "completed") return "已完成";
  if (task.status === "failed") return "生成失败";
  if (task.status === "unavailable") return "等待服务恢复";
  if ((task.progress || 0) > 0) return `处理中 ${task.progress}%`;
  return "已提交";
}

function videoTaskTagType(task: any) {
  if (task.status === "completed") return "success";
  if (task.status === "failed") return "danger";
  if (task.status === "unavailable") return "warning";
  return "primary";
}

function formatVideoTaskTime(task: any) {
  const value = task.updated_at || task.submitted_at;
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `更新于 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
}

async function refreshVideoTask(task: any, notify = false) {
  const previousStatus = task.status;
  try {
    const response = await api.get(`/pipeline/video/tasks/${task.task_id}`, {
      params: { money_printer_url: turboUrl.value },
      timeout: 20000,
    });
    upsertVideoTask({ ...response.data, last_error: "" });
    if (notify && response.data.status === "completed") {
      ElMessage.success("视频已生成，可以下载");
    } else if (previousStatus !== "completed" && response.data.status === "completed") {
      ElMessage.success(`剪辑任务 ${task.task_id.slice(0, 8)} 已完成`);
    } else if (notify) {
      ElMessage.info(`任务进度：${response.data.progress || 0}%`);
    }
  } catch (err: any) {
    upsertVideoTask({
      task_id: task.task_id,
      status: "unavailable",
      last_error: err.response?.data?.detail || "暂时无法查询任务，稍后会自动重试",
    });
    if (notify) {
      ElMessage.warning(err.response?.data?.detail || "暂时无法查询任务状态");
    }
  }
}

async function refreshVideoTasks(notify = false) {
  if (pollingVideoTasks.value) return;
  pollingVideoTasks.value = true;
  try {
    const tasks = notify ? videoTasks.value : activeVideoTasks.value;
    await Promise.all(tasks.map((task) => refreshVideoTask(task, false)));
    if (notify) ElMessage.success("任务状态已刷新");
  } finally {
    pollingVideoTasks.value = false;
  }
}

async function loadServerVideoTasks() {
  try {
    const response = await api.get("/pipeline/video/tasks", {
      params: { page: 1, page_size: 20, money_printer_url: turboUrl.value },
      timeout: 20000,
    });
    for (const task of response.data?.tasks || []) upsertVideoTask(task);
  } catch {
    // 保留浏览器已缓存的任务，后台服务恢复后轮询会继续。
  }
}

function startVideoTaskPolling() {
  if (videoTaskPollTimer) return;
  videoTaskPollTimer = setInterval(() => {
    if (activeVideoTasks.value.length) refreshVideoTasks(false);
  }, 10000);
}

function clearFinishedVideoTasks() {
  videoTasks.value = videoTasks.value.filter(
    (task) => !["completed", "failed"].includes(task?.status),
  );
}

function downloadVideoOutput(url: string) {
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

async function handleRenderVideo() {
  if (!videoResult.value?.script) return;
  renderingVideo.value = true;
  try {
    const res = await api.post("/pipeline/video/render", {
      video_script: videoResult.value.script,
      video_subject: videoResult.value.title,
      video_aspect_ratio: videoAspect.value,
      money_printer_url: turboUrl.value,
    });
    if (res.data?.error) {
      ElMessage.warning(res.data.message || res.data.error);
    } else {
      const taskData = res.data?.data || res.data;
      const taskId = taskData?.task_id;
      if (!taskId) {
        ElMessage.warning("MoneyPrinterTurbo 未返回任务 ID，无法跟踪进度");
        return;
      }
      upsertVideoTask({
        task_id: taskId,
        subject: videoResult.value.title,
        state: 4,
        status: "processing",
        progress: 0,
        outputs: [],
      });
      startVideoTaskPolling();
      ElMessage.success("剪辑任务已提交到后台，可离开本页，完成后回来下载");
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "提交视频剪辑任务失败");
  } finally {
    renderingVideo.value = false;
  }
}

onMounted(() => {
  // 严格遵循需求：刷新页面时保留现有数据，绝不自动请求覆盖；
  // 仅当本地从来没有热点缓存数据时，才初次静默获取一次
  if (!hotspots.value || hotspots.value.length === 0) {
    loadHotspots(true);
  }
  loadServerVideoTasks().finally(() => {
    refreshVideoTasks(false);
    startVideoTaskPolling();
  });
});

onBeforeUnmount(() => {
  if (videoTaskPollTimer) clearInterval(videoTaskPollTimer);
});
</script>

<style scoped>
.studio-view {
  min-height: 100%;
}

.engine-hint {
  margin-bottom: 16px;
}

.hint-link {
  color: var(--el-color-primary);
  font-weight: 600;
  text-decoration: none;
}

.hint-link:hover {
  text-decoration: underline;
}

.studio-tabs {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

/* 两侧栏目等高与内部滚动核心样式 */
.studio-row {
  display: flex !important;
  align-items: stretch !important;
}

.studio-col {
  display: flex !important;
  flex-direction: column !important;
}

.studio-card {
  height: 100% !important;
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  overflow: hidden !important;
}

.studio-card :deep(.el-card__header) {
  flex-shrink: 0 !important;
  padding: 14px 20px !important;
  border-bottom: 1px solid var(--el-border-color-lighter) !important;
}

.studio-card :deep(.el-card__body) {
  height: calc(100vh - 250px) !important;
  min-height: 520px !important;
  max-height: 680px !important;
  overflow-y: auto !important;
  padding: 18px 20px !important;
  box-sizing: border-box !important;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 28px;
}

.header-title {
  font-weight: 600;
  font-size: 15px;
}

.header-tools,
.header-actions {
  display: flex;
  align-items: center;
}

.form-tip {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
  margin-top: 4px;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}

.empty-state {
  margin: auto;
  padding: 40px 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.title-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-item {
  padding: 8px 12px;
  border-radius: 6px;
  background: #f8fafc;
  transition: all 0.2s;
}

.title-item:hover {
  background: #f1f5f9;
}

.title-checkbox {
  display: flex;
  align-items: center;
  width: 100%;
}

.title-idx {
  font-weight: bold;
  color: #64748b;
  margin-right: 6px;
}

.title-text {
  font-size: 14px;
  color: #1e293b;
}

.hotspot-picker {
  margin-bottom: 16px;
}

.picker-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 8px;
}

.hotspot-tag {
  background: #f8fafc;
  border-left: 3px solid var(--el-color-primary);
  padding: 10px 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border-top: 1px solid #f1f5f9;
  border-right: 1px solid #f1f5f9;
  border-bottom: 1px solid #f1f5f9;
}

.hotspot-tag:hover {
  background: #eff6ff;
  border-left-color: #2563eb;
}

.tag-title {
  font-size: 14px;
  color: #0f172a;
  margin-bottom: 4px;
}

.tag-desc {
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
}

.hotspot-empty-tip {
  margin-bottom: 12px;
  padding: 8px;
  background: #f8fafc;
  border-radius: 4px;
  text-align: center;
}

.poster-section {
  margin-top: 20px;
}

.poster-box {
  background: #f8fafc;
  padding: 12px;
  border-radius: 6px;
  border: 1px dashed #cbd5e1;
}

.box-title {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
  color: #334155;
}

.poster-text,
.poster-prompt {
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.article-preview-content {
  width: 100%;
  box-sizing: border-box;
  word-break: break-word;
  line-height: 1.8;
  color: #334155;
}

.turbo-card-section {
  margin-top: 20px;
  background: #f8fafc;
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px dashed #cbd5e1;
}

.turbo-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 12px;
}

.render-submit-tip {
  margin-top: 10px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.render-task-panel {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.render-task-panel__header,
.render-task__topline,
.render-task__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.render-task-panel__header {
  margin-bottom: 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
}

.render-task-panel__actions {
  display: flex;
  align-items: center;
}

.render-task {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.render-task + .render-task {
  margin-top: 10px;
}

.render-task__identity {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.render-task__title {
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.render-task__id {
  color: #94a3b8;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 10px;
}

.render-task :deep(.el-progress) {
  margin-top: 10px;
}

.render-task__meta {
  margin-top: 7px;
  color: #94a3b8;
  font-size: 11px;
}

.render-task__error {
  margin-top: 8px;
  padding: 7px 9px;
  border-radius: 5px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.45;
}

.render-task__outputs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.render-task__pending-file {
  color: #64748b;
  font-size: 12px;
}

.video-result-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.script-box {
  background: #f8fafc;
  padding: 12px 14px;
  border-radius: 6px;
  border: 1px solid #f1f5f9;
}

.section-label {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
  color: #1e293b;
}

.title-highlight {
  font-size: 16px;
  font-weight: bold;
  color: var(--el-color-primary);
  margin-bottom: 6px;
}

.hook-box {
  background: #fef2f2;
  border-left: 3px solid #ef4444;
  padding: 8px 10px;
  font-size: 13px;
  color: #991b1b;
  border-radius: 4px;
}
</style>
