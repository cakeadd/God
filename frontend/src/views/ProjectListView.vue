<script setup>
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { getProjects } from '../api/projects'

const projects = ref([])
const loading = ref(false)
const loadError = ref(false)

const roleLabels = {
  owner: '拥有者',
  admin: '管理员',
  member: '成员',
  viewer: '访客',
}

const hasProjects = computed(() => projects.value.length > 0)

function formatTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

async function loadProjects() {
  loading.value = true
  loadError.value = false
  try {
    const response = await getProjects()
    projects.value = response.data
  } catch {
    loadError.value = true
    ElMessage.error('项目列表加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadProjects)
</script>

<template>
  <section class="workspace-section">
    <div class="page-heading">
      <div>
        <h1>项目</h1>
        <p>你参与的接口测试项目</p>
      </div>
      <el-tooltip content="刷新项目列表" placement="bottom">
        <el-button :icon="Refresh" circle :loading="loading" aria-label="刷新项目列表" @click="loadProjects" />
      </el-tooltip>
    </div>

    <div class="data-surface" v-loading="loading">
      <el-alert
        v-if="loadError"
        title="项目列表暂时无法加载"
        type="error"
        :closable="false"
        show-icon
      />

      <el-table v-else-if="hasProjects" :data="projects" class="project-table" row-key="id">
        <el-table-column label="项目" min-width="260">
          <template #default="{ row }">
            <div class="project-name-cell">
              <RouterLink
                :to="{ name: 'project-endpoints', params: { projectId: row.id } }"
              >
                {{ row.name }}
              </RouterLink>
              <span>{{ row.description || '暂无描述' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag effect="plain" type="success">{{ roleLabels[row.my_role] || row.my_role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner_username" label="拥有者" width="150" />
        <el-table-column label="更新时间" width="190">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="进入" width="72" align="center">
          <template #default="{ row }">
            <el-tooltip content="进入项目" placement="left">
              <el-button
                :icon="ArrowRight"
                circle
                text
                aria-label="进入项目"
                @click="$router.push({ name: 'project-endpoints', params: { projectId: row.id } })"
              />
            </el-tooltip>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-else :image-size="72" description="你还没有参与任何项目" />
    </div>
  </section>
</template>
