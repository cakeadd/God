import { inject } from 'vue'

export const projectWorkspaceKey = Symbol('project-workspace')

export function useProjectWorkspace() {
  const workspace = inject(projectWorkspaceKey)

  if (!workspace) {
    throw new Error('Project workspace context is unavailable')
  }

  return workspace
}
