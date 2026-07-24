<script setup>
import { computed, provide, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, Connection, User } from '@element-plus/icons-vue'

import { getProject } from '../api/projects'
import { projectWorkspaceKey } from '../composables/projectWorkspace'

const route = useRoute()
const workspace = reactive({
  project: null,
  loading: true,
  error: false,
})

const roleLabels = {
  owner: '拥有者',
  member: '成员',
  viewer: '只读成员',
}

const roleLabel = computed(() => (
  roleLabels[workspace.project?.my_role] || workspace.project?.my_role || '-'
))

provide(projectWorkspaceKey, workspace)

async function loadProject(projectId) {
  workspace.loading = true
  workspace.error = false
  workspace.project = null

  try {
    const response = await getProject(projectId)
    workspace.project = response.data
  } catch {
    workspace.error = true
  } finally {
    workspace.loading = false
  }
}

watch(
  () => route.params.projectId,
  (projectId) => loadProject(projectId),
  { immediate: true },
)
</script>

<template>
  <section class="project-workspace" v-loading="workspace.loading">
    <el-result
      v-if="workspace.error"
      icon="warning"
      title="项目不存在或无权访问"
      sub-title="请返回项目列表重新选择项目"
    >
      <template #extra>
        <el-button type="primary" @click="$router.replace({ name: 'projects' })">
          返回项目列表
        </el-button>
      </template>
    </el-result>

    <template v-else-if="workspace.project">
      <div class="project-context">
        <RouterLink class="back-link" :to="{ name: 'projects' }">
          <el-icon><ArrowLeft /></el-icon>
          返回项目
        </RouterLink>
        <div class="project-context__copy">
          <div class="project-context__title">
            <h1>{{ workspace.project.name }}</h1>
            <el-tag effect="plain" type="success">{{ roleLabel }}</el-tag>
          </div>
          <p>{{ workspace.project.description || '暂无项目描述' }}</p>
        </div>
      </div>

      <div class="project-workspace__body">
        <nav class="project-navigation" aria-label="项目导航">
          <RouterLink
            class="project-navigation__item"
            :to="{ name: 'project-endpoints', params: { projectId: workspace.project.id } }"
          >
            <el-icon><Connection /></el-icon>
            接口定义
          </RouterLink>
          <RouterLink
            class="project-navigation__item"
            :to="{ name: 'project-members', params: { projectId: workspace.project.id } }"
          >
            <el-icon><User /></el-icon>
            项目成员
          </RouterLink>
        </nav>

        <div class="project-workspace__content">
          <RouterView />
        </div>
      </div>
    </template>
  </section>
</template>
