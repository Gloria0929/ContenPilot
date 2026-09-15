<template>
  <div class="studio-view">
    <el-tabs v-model="activeTab" class="studio-tabs">
      <!-- 选项卡 1：GEO 矩阵工坊 -->
      <el-tab-pane label="GEO 矩阵工坊" name="geo">
        <el-row :gutter="20">
          <el-col :span="10">
            <el-card shadow="never" class="config-card">
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
                  <div class="form-tip">必带品牌与产品核心词，锁定大模型认知抓取。</div>
                </el-form-item>

                <el-form-item label="行业热门关键词（5 个）">
                  <el-input
                    v-model="geoForm.industryKeywords"
                    placeholder="AI研发效能, 智能体协同开发, 自动化编程工具, 企业级知识库RAG, AI代码审查"
                  />
                  <div class="form-tip">以逗号分隔，结合当前软件研发热点挑选。</div>
                </el-form-item>

                <el-form-item label="计划生成篇数">
                  <el-input-number v-model="geoForm.count" :min="5" :max="50" :step="5" />
                  <span style="margin-left: 10px; color: #64748b; font-size: 13px;">标准批次：30 篇</span>
                </el-form-item>

                <el-form-item label="分发周期（天）">
                  <el-slider v-model="geoForm.days" :min="3" :max="30" show-input />
                  <div class="form-tip">文档规范：10 天内将 30 篇文章全渠道平滑发完，错峰防风控。</div>
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

          <el-col :span="14">
            <el-card shadow="never" class="titles-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">选题列表 (共 {{ titles.length }} 篇)</span>
                  <div v-if="titles.length > 0">
                    <el-button link type="primary" size="small" @click="toggleSelectAll">
                      {{ selectedTitles.length === titles.length ? "取消全选" : "全选" }}
                    </el-button>
                  </div>
                </div>
              </template>

              <div v-if="titles.length === 0" class="empty-state">
                <el-empty description="请在左侧配置关键词后点击「生成 GEO 标题」" />
              </div>

              <el-checkbox-group v-else v-model="selectedTitles" class="title-list">
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
        <el-row :gutter="20">
          <el-col :span="11">
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span class="header-title">公众号文章创作</span>
                  <el-button size="small" :loading="fetchingHotspots" @click="loadHotspots">
                    刷新今日热点
                  </el-button>
                </div>
              </template>

              <!-- 今日热点列表 -->
              <div v-if="hotspots.length > 0" class="hotspot-picker">
                <div class="picker-label">🔥 今日精选技术热点（点击直接采用）：</div>
                <div
                  v-for="h in hotspots"
                  :key="h.id"
                  class="hotspot-tag"
                  @click="adoptHotspotForWechat(h)"
                >
                  <div class="tag-title"><strong>{{ h.title }}</strong></div>
                  <div class="tag-desc">{{ h.conflict_point || h.summary }}</div>
                </div>
              </div>
              <div v-else class="hotspot-empty-tip">
                <el-button link type="primary" size="small" @click="loadHotspots">
                  点击加载精选热点
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
                  <el-select v-model="wechatForm.theme" style="width: 100%;">
                    <el-option label="石墨极简风（推荐·低调大气）" value="graphite" />
                    <el-option label="摸鱼绿（极客·明亮护眼）" value="slacking_green" />
                    <el-option label="红白色系（重磅热点·视觉冲击）" value="red_white" />
                    <el-option label="留白禅意风（优雅留白·深度长文）" value="zen_white" />
                    <el-option label="摸鱼票据风（技术清单·票据框）" value="ticket_receipt" />
                    <el-option label="橄榄手记（复古质感·理性从容）" value="olive_note" />
                  </el-select>
                </el-form-item>

                <el-button
                  type="primary"
                  style="width: 100%; margin-top: 10px;"
                  :loading="generatingWechat"
                  @click="handleGenerateWechat"
                >
                  生成公众号文章并排版
                </el-button>
              </el-form>

              <!-- 贴图与封面区域 -->
              <div v-if="wechatResult" class="poster-section">
                <el-divider content-position="left">公众号贴图衍生资产</el-divider>
                <div class="poster-box">
                  <div class="box-title">贴图文案 (300字精炼版)：</div>
                  <div class="poster-text">{{ wechatResult.poster_copy }}</div>
                  <el-button size="small" style="margin-top: 8px;" @click="copyText(wechatResult.poster_copy)">
                    复制贴图文案
                  </el-button>
                </div>

                <div class="poster-box" style="margin-top: 12px;">
                  <div class="box-title">3:4 醒目标题封面生图 Prompt：</div>
                  <div class="poster-prompt">{{ wechatResult.poster_image_prompt }}</div>
                  <el-button size="small" style="margin-top: 8px;" @click="copyText(wechatResult.poster_image_prompt)">
                    复制生图提示词
                  </el-button>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :span="13">
            <el-card shadow="never" class="preview-card">
              <template #header>
                <div class="card-header">
                  <span class="header-title">微信公众号原生排版预览</span>
                  <div v-if="wechatResult">
                    <el-button type="primary" size="small" @click="copyHtml">
                      复制富文本 HTML
                    </el-button>
                  </div>
                </div>
              </template>

              <div v-if="!wechatResult" class="empty-state">
                <el-empty description="文章生成后在此处进行手机端原生排版预览" />
              </div>

              <div v-else class="preview-scroll">
                <div class="phone-mockup">
                  <div class="phone-content" v-html="wechatResult.rendered_html"></div>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <!-- 选项卡 3：短视频工坊 -->
      <el-tab-pane label="短视频工坊" name="video">
        <el-row :gutter="20">
          <el-col :span="11">
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span class="header-title">短视频口播脚本策划</span>
                  <el-tag type="warning" size="small">2分钟 / 600字以内</el-tag>
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
                  <div class="tag-title"><strong>{{ h.title }}</strong></div>
                  <div class="tag-desc">{{ h.conflict_point || h.summary }}</div>
                </div>
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
                  style="width: 100%; margin-top: 10px;"
                  :loading="generatingVideo"
                  @click="handleGenerateVideo"
                >
                  生成口播脚本与剪辑清单
                </el-button>
              </el-form>
            </el-card>

            <el-card v-if="videoResult" shadow="never" style="margin-top: 20px;">
              <template #header>
                <div class="card-header">
                  <span class="header-title">一键触发自动剪辑 (MoneyPrinterTurbo)</span>
                </div>
              </template>

              <el-form label-position="top">
                <el-form-item label="MoneyPrinterTurbo 服务地址">
                  <el-input v-model="turboUrl" placeholder="http://localhost:8501" />
                </el-form-item>
                <el-form-item label="视频比例">
                  <el-radio-group v-model="videoAspect">
                    <el-radio value="9:16">9:16 (竖屏·抖音/视频号)</el-radio>
                    <el-radio value="16:9">16:9 (横屏·B站/西瓜)</el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-button
                  type="success"
                  style="width: 100%;"
                  :loading="renderingVideo"
                  @click="handleRenderVideo"
                >
                  提交后台自动剪辑出片
                </el-button>
              </el-form>
            </el-card>
          </el-col>

          <el-col :span="13">
            <el-card shadow="never">
              <template #header>
                <div class="card-header">
                  <span class="header-title">口播脚本与分镜素材</span>
                  <el-tag v-if="videoResult" type="info" size="small">
                    约 {{ videoResult.word_count }} 字
                  </el-tag>
                </div>
              </template>

              <div v-if="!videoResult" class="empty-state">
                <el-empty description="点击左侧生成短视频口播文案" />
              </div>

              <div v-else class="video-result-content">
                <div class="script-box">
                  <div class="section-label">📌 视频大标题与前3秒钩子：</div>
                  <div class="title-highlight">{{ videoResult.title }}</div>
                  <div v-if="videoResult.opening_hooks && videoResult.opening_hooks.length > 0" class="hook-box">
                    <strong>开头爆点金句：</strong>{{ videoResult.opening_hooks[0] }}
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
                  <el-button size="small" style="margin-top: 8px;" @click="copyText(videoResult.script)">
                    复制口播文案
                  </el-button>
                </div>

                <div class="script-box">
                  <div class="section-label">🖼️ 封面图生图提示词 (Prompt)：</div>
                  <div class="poster-prompt">{{ videoResult.cover_prompt }}</div>
                  <el-button size="small" style="margin-top: 8px;" @click="copyText(videoResult.cover_prompt)">
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
import { ref, onMounted } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";

const activeTab = ref("geo");

// 本地默认精选热点（保证无网络或未配置模型时立即展现，绝不留白）
const FALLBACK_HOTSPOTS = [
  {
    id: 1,
    title: "头部工程团队发声：AI 不想帮程序员写代码了，它想直接把工作做完",
    summary: "Spotify、微软等工程团队负责人指出，单纯代码补全效能提升已达瓶颈，具备需求拆解、全库上下文感知与自主测试的 Agent 架构正在取代传统 Copilot 模式。",
    conflict_point: "从“人写代码 AI 补全”全面转向“人提需求 Agent 全自动交付”的范式颠覆。",
  },
  {
    id: 2,
    title: "Google 安全团队重磅预警：AI Agent 正在让自动化网络攻击演进为秒级对抗",
    summary: "Google 安全团队警告，AI 智能体已被用于自动扫描漏洞、自适应生成渗透代码并持续自我迭代，传统人工 Review 漏洞的速度已完全无法跟上威胁。",
    conflict_point: "人工安全审计周期冗长 vs AI 自动化攻防秒级生效。",
  },
  {
    id: 3,
    title: "开发者效能工具链洗牌：单点编程助手遇冷，企业级 Agent 工作台成新宠",
    summary: "行业最新效能报告显示，超过 65% 的团队正在将孤立的 AI 插件迁移至具备企业知识库打通与多 Agent 协同的工作台，研发文档与老项目资产化成为核心诉求。",
    conflict_point: "通用大模型缺乏项目上下文导致频发幻觉 vs 融合私有知识库的研发 Agent。",
  },
];

// ---- GEO 状态 ----
const geoForm = ref({
  brandKeywords: "敖行客, AT Work, Agent研发工作台",
  industryKeywords: "AI研发效能, 智能体协同开发, 自动化编程工具, 企业级知识库RAG, AI代码审查",
  count: 30,
  days: 10,
});
const generatingTitles = ref(false);
const batchCreating = ref(false);
const titles = ref<string[]>([]);
const selectedTitles = ref<string[]>([]);

async function handleGenerateTitles() {
  generatingTitles.value = true;
  try {
    const brands = geoForm.value.brandKeywords.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    const industries = geoForm.value.industryKeywords.split(/[,，]/).map(s => s.trim()).filter(Boolean);
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
    ElMessage.success(`批量任务创建成功！共生成 ${res.data.article_count} 篇文章，已创建 ${res.data.task_count} 个 10 天发布排期任务。可在「发布任务」大盘查看！`);
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "批量创建失败");
  } finally {
    batchCreating.value = false;
  }
}

// ---- 公众号状态 ----
const wechatForm = ref({
  hotspot: "Spotify 工程团队负责人指出：AI 不想帮程序员写代码了，它想直接做完工作。",
  angle: "从代码补全到 Agent 协同交付：剖析软件研发范式颠覆与 AT Work 实战",
  theme: "graphite",
});
const generatingWechat = ref(false);
const wechatResult = ref<any>(null);
const fetchingHotspots = ref(false);
const hotspots = ref<any[]>([...FALLBACK_HOTSPOTS]);

async function loadHotspots() {
  fetchingHotspots.value = true;
  try {
    const res = await api.get("/pipeline/hotspots");
    if (res.data && Array.isArray(res.data) && res.data.length > 0) {
      hotspots.value = res.data;
      ElMessage.success(`今日技术热点已就绪（共 ${res.data.length} 条）`);
    } else {
      hotspots.value = [...FALLBACK_HOTSPOTS];
      ElMessage.info("已加载精选行业热点");
    }
  } catch {
    hotspots.value = [...FALLBACK_HOTSPOTS];
    ElMessage.info("已自动装载精选行业热点");
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

// ---- 短视频状态 ----
const videoForm = ref({
  hotspot: "Google 安全团队发出警告：AI Agent 正在让网络攻击进入自动化时代，传统人工防御已无法阻挡。",
  angle: "聚焦攻防自动化升级，突出 AI 智能体取代人工黑客的强烈冲突感",
});
const generatingVideo = ref(false);
const videoResult = ref<any>(null);
const turboUrl = ref("http://localhost:8501");
const videoAspect = ref("9:16");
const renderingVideo = ref(false);

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
      ElMessage.success("剪辑任务已成功提交至 MoneyPrinterTurbo 服务！");
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || "提交视频剪辑任务失败");
  } finally {
    renderingVideo.value = false;
  }
}

onMounted(() => {
  loadHotspots();
});
</script>

<style scoped>
.studio-view {
  min-height: 100%;
}

.studio-tabs {
  background: #fff;
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid var(--el-border-color-lighter);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  font-weight: 600;
  font-size: 15px;
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
  padding: 40px 0;
}

.title-list {
  max-height: 520px;
  overflow-y: auto;
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

.poster-text, .poster-prompt {
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.preview-scroll {
  display: flex;
  justify-content: center;
  background: #f1f5f9;
  padding: 20px;
  border-radius: 8px;
}

.phone-mockup {
  width: 380px;
  max-width: 100%;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
  padding: 24px 16px;
  min-height: 600px;
  overflow-y: auto;
}

.phone-content {
  word-break: break-word;
}

.script-box {
  margin-bottom: 16px;
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
