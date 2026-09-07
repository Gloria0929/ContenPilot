<template>
  <div class="login-page">
    <div class="deco" aria-hidden="true"></div>
    <main class="login-card">
      <div class="card-head">
        <div class="logo-mark" aria-hidden="true">
          <el-icon :size="30"><Promotion /></el-icon>
        </div>
        <h1 class="card-title">ContentPilot</h1>
        <p class="card-sub">AI 内容创作与多平台发布管理台</p>
      </div>

      <el-form @submit.prevent="onLogin" label-position="top" size="large">
        <el-form-item label="用户名">
          <el-input v-model="username" placeholder="admin" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            placeholder="请输入密码"
            @keyup.enter="onLogin"
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          class="login-btn"
          :loading="loading"
          @click="onLogin"
        >
          登 录
        </el-button>
        <transition name="fade">
          <p v-if="error" class="err" role="alert">{{ error }}</p>
        </transition>
      </el-form>

      <footer class="card-foot">v2.2.0 · © 2026 ContentPilot</footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElForm, ElFormItem, ElInput, ElButton } from "element-plus";
import { Promotion } from "@element-plus/icons-vue";
import { login } from "../auth";

const router = useRouter();
const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function onLogin() {
  loading.value = true;
  error.value = "";
  try {
    await login(username.value, password.value);
    router.push("/");
  } catch (e: any) {
    error.value = "登录失败：用户名或密码错误";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100dvh;
  padding: 32px 20px;
  background: #f4f5fa;
  overflow: hidden;
}

/* 轻量氛围：青绿径向光晕 + 细点阵 */
.deco {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(
      520px 360px at 18% 12%,
      rgba(47, 169, 140, 0.14),
      transparent 70%
    ),
    radial-gradient(
      560px 420px at 88% 88%,
      rgba(47, 169, 140, 0.1),
      transparent 70%
    );
}
.deco::after {
  content: "";
  position: absolute;
  inset: 0;
  background-image: radial-gradient(
    rgba(47, 169, 140, 0.1) 1px,
    transparent 1px
  );
  background-size: 26px 26px;
  -webkit-mask-image: radial-gradient(
    70% 60% at 50% 40%,
    #000,
    transparent 80%
  );
  mask-image: radial-gradient(70% 60% at 50% 40%, #000, transparent 80%);
}

.login-card {
  position: relative;
  width: 400px;
  max-width: 100%;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 18px;
  box-shadow: 0 24px 60px -24px rgba(15, 23, 42, 0.22);
  padding: 40px 36px 28px;
  box-sizing: border-box;
  animation: rise 0.5s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}

.card-head {
  text-align: center;
  margin-bottom: 30px;
}

.logo-mark {
  width: 56px;
  height: 56px;
  margin: 0 auto 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, #3fc3a1, #1f8a70);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 14px 30px -12px rgba(47, 169, 140, 0.55);
}

.card-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--el-text-color-primary);
  margin: 0 0 8px;
}

.card-sub {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}

.login-card :deep(.el-form-item) {
  margin-bottom: 18px;
}

.login-btn {
  width: 100%;
  margin-top: 6px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.err {
  margin: 16px 0 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-color-danger-light-9);
  border: 1px solid var(--el-color-danger-light-7);
  color: var(--el-color-danger);
  font-size: 13px;
}

.card-foot {
  margin-top: 26px;
  text-align: center;
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .login-card {
    animation: none;
  }
  .fade-enter-active,
  .fade-leave-active {
    transition: none;
  }
}
</style>
