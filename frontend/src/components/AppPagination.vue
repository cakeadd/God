<script setup>
defineProps({
  total: {
    type: Number,
    required: true,
  },
  currentPage: {
    type: Number,
    required: true,
  },
  pageSize: {
    type: Number,
    required: true,
  },
  pageSizes: {
    type: Array,
    default: () => [10, 20, 50],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['page-change', 'page-size-change'])
</script>

<template>
  <div class="app-pagination">
    <el-pagination
      background
      layout="total, sizes, prev, pager, next"
      :total="total"
      :current-page="currentPage"
      :page-size="pageSize"
      :page-sizes="pageSizes"
      :disabled="disabled"
      @current-change="$emit('page-change', $event)"
      @size-change="$emit('page-size-change', $event)"
    />
  </div>
</template>
