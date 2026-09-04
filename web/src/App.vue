<template>
  <el-config-provider :locale="zhCn">
    <div class="app">
      <el-container v-if="isLoggedIn" class="shell">
        <el-aside width="232px" class="sider">
          <div class="brand">
            <div class="logo" aria-hidden="true">
              <el-icon :size="18"><Promotion /></el-icon>
            </div>
            <div class="brand-text">
              <div class="brand-name">ContentPilot</div>
              <div class="brand-sub">AI 自动化运营平台</div>
            </div>
          </div>
          <el-menu
            class="side-menu"
            :default-active="currentPath"
            router
            :ellipsis="false"
          >
            <el-menu-item v-for="m in menuOptions" :key="m.key" :index="m.key">
              <el-icon><component :is="m.icon" /></el-icon>
              <span>{{ m.label }}</span>
            </el-menu-item>
          </el-menu>
          <div class="side-foot">v2.2.0</div>
        </el-aside>
        <el-container class="main">
          <el-header class="header">
            <div class="header-title">
              <span class="title-dot" aria-hidden="true"></span>
              {{ pageTitle }}
            </div>
            <el-button text class="logout-btn" @click="logout">
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-button>
          </el-header>
          <el-main class="content">
            <router-view />
          </el-main>
        </el-container>
      </el-container>
      <router-view v-else />
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ElConfigProvider,
  ElContainer,
  ElAside,
  ElHeader,
  ElMain,
  ElMenu,
  ElMenuItem,
  ElButton,
  ElIcon,
  ElMessageBox,
} from "element-plus";
import {
  SwitchButton,
  Promotion,
  Odometer,
  Document,
  Share,
  CircleCheck,
  Tickets,
  User,
  Monitor,
  Memo,
  Setting,
} from "@element-plus/icons-vue";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import { isLoggedIn, logout as doLogout } from "./auth";

const route = useRoute();
const router = useRouter();

const currentPath = computed(() => route.path);

const menuOptions = [
  { label: "工作台", key: "/", icon: Odometer },
  { label: "文章管理", key: "/articles", icon: Document },
  { label: "发布内容", key: "/publish", icon: Share },
  { label: "内容审核", key: "/review", icon: CircleCheck },
  { label: "发布任务", key: "/tasks", icon: Tickets },
  { label: "账号管理", key: "/accounts", icon: User },
  { label: "平台与会话", key: "/platforms", icon: Monitor },
  { label: "发布日志", key: "/logs", icon: Memo },
  { label: "设置", key: "/settings", icon: Setting },
];

const pageTitle = computed(() => {
  const map: Record<string, string> = {
    "/": "工作台",
    "/articles": "文章管理",
    "/publish": "发布内容",
    "/review": "内容审核",
    "/tasks": "发布任务",
    "/accounts": "账号管理",
    "/platforms": "平台与浏览器会话",
    "/logs": "发布日志",
    "/settings": "设置",
  };
  return map[route.path] || "";
});

async function logout() {
  try {
    await ElMessageBox.confirm("确定要退出登录吗？", "退出登录", {
      confirmButtonText: "退出",
      cancelButtonText: "取消",
      type: "warning",
      confirmButtonClass: "el-button--danger",
    });
  } catch {
    return;
  }
  await doLogout();
  router.push("/login");
}
</script>

<style>
/* 全局：锁定视口，页面级不出现滚动条（滚动只发生在内容区内部） */
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
}
</style>

<style scoped>
.app {
  min-height: 100dvh;
}

/* 外壳固定为一屏高：侧栏随之固定，不再跟随页面滚动 */
.shell {
  height: 100dvh;
}

/* ---- 浅色侧边栏 ---- */
.sider {
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid var(--el-border-color-lighter);
  box-sizing: border-box;
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 20px 18px 16px;
}

.logo {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: linear-gradient(135deg, #3fc3a1, #1f8a70);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 8px 18px -8px rgba(47, 169, 140, 0.6);
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.brand-sub {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.side-menu {
  flex: 1;
  padding: 6px 0;
  color: #94a3b8;
}

.side-foot {
  padding: 16px 22px;
  font-size: 11px;
  color: #475569;
}

/* ---- 白色顶栏 ---- */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 28px;
  height: 58px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: #fff;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--el-text-color-primary);
}

.title-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-color-primary);
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8);
}

.logout-btn {
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

/* 内容区占满剩余高度并内部滚动（侧栏/顶栏固定） */
.content {
  padding: 24px 28px;
  background: var(--el-bg-color-page);
  overflow: auto;
}

/* 响应式：窄屏收窄内边距 */
@media (max-width: 768px) {
  .header {
    padding: 0 16px;
  }
  .content {
    padding: 16px;
  }
}
@media (min-width: 1600px) {
  .content {
    padding: 28px 40px;
  }
}
</style>
