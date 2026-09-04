import { ref } from 'vue'
import api from './api'

// session cookie 为 HttpOnly，JS 无法读取，登录态由该响应式状态维护
export const isLoggedIn = ref(false)

export async function checkAuth(): Promise<boolean> {
  if (isLoggedIn.value) return true
  try {
    await api.get('/auth/whoami')
    isLoggedIn.value = true
  } catch {
    isLoggedIn.value = false
  }
  return isLoggedIn.value
}

export async function login(username: string, password: string) {
  await api.post('/auth/login', { username, password })
  isLoggedIn.value = true
}

export async function logout() {
  try {
    await api.post('/auth/logout')
  } finally {
    isLoggedIn.value = false
  }
}
