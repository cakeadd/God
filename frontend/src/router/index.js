import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const AppLayout = () => import('../layouts/AppLayout.vue')
const ProjectWorkspaceLayout = () => import('../layouts/ProjectWorkspaceLayout.vue')
const LoginView = () => import('../views/LoginView.vue')
const ProjectListView = () => import('../views/ProjectListView.vue')
const EndpointListView = () => import('../views/EndpointListView.vue')
const ProjectMemberListView = () => import('../views/ProjectMemberListView.vue')
const EnvironmentListView = () => import('../views/EnvironmentListView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { guestOnly: true },
    },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/projects' },
        {
          path: 'projects',
          name: 'projects',
          component: ProjectListView,
        },
        {
          path: 'projects/:projectId',
          component: ProjectWorkspaceLayout,
          children: [
            {
              path: '',
              redirect: (to) => ({
                name: 'project-endpoints',
                params: { projectId: to.params.projectId },
              }),
            },
            {
              path: 'endpoints',
              name: 'project-endpoints',
              component: EndpointListView,
            },
            {
              path: 'members',
              name: 'project-members',
              component: ProjectMemberListView,
            },
            {
              path: 'environments',
              name: 'project-environments',
              component: EnvironmentListView,
            },
          ],
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/projects' },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  // 首次进入页面时先恢复认证状态，再决定放行或跳转，避免路由误判。
  await authStore.initialize()

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return { name: 'projects' }
  }

  return true
})

export default router
