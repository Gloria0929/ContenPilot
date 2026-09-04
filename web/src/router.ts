import { createRouter, createWebHistory } from "vue-router";
import { checkAuth } from "./auth";

const routes = [
  {
    path: "/login",
    name: "login",
    component: () => import("./views/Login.vue"),
  },
  {
    path: "/",
    name: "dashboard",
    component: () => import("./views/Dashboard.vue"),
  },
  {
    path: "/articles",
    name: "articles",
    component: () => import("./views/Articles.vue"),
  },
  {
    path: "/platforms",
    name: "platforms",
    component: () => import("./views/Platforms.vue"),
  },
  {
    path: "/publish",
    name: "publish",
    component: () => import("./views/Publish.vue"),
  },
  {
    path: "/review",
    name: "review",
    component: () => import("./views/Review.vue"),
  },
  {
    path: "/tasks",
    name: "tasks",
    component: () => import("./views/Tasks.vue"),
  },
  {
    path: "/accounts",
    name: "accounts",
    component: () => import("./views/Accounts.vue"),
  },
  {
    path: "/logs",
    name: "logs",
    component: () => import("./views/Logs.vue"),
  },
  {
    path: "/settings",
    name: "settings",
    component: () => import("./views/Settings.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  if (to.name === "login") return true;
  const authed = await checkAuth();
  if (!authed) {
    return { name: "login" };
  }
  return true;
});

export default router;
