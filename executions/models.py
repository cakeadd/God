from django.conf import settings
from django.db import models
from django.db.models import Q

from environments.models import Environment
from projects.models import Project
from testcases.models import TestCase


class TestRun(models.Model):
    class Status(models.TextChoices):
        PENDING='pending','等待中'
        RUNNING='running','执行中'
        COMPLETED='completed','已完成'
        ERROR='error','异常'

    project=models.ForeignKey(
        Project,
        verbose_name='所属项目',
        on_delete=models.CASCADE,
        related_name='test_runs',
    )
    name=models.CharField('批次名称',max_length=100,blank=True)
    test_cases=models.ManyToManyField(
        TestCase,
        verbose_name='测试用例',
        related_name='test_runs',
    )
    status=models.CharField(
        '批次状态',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    total_count=models.PositiveIntegerField('总用例数',default=0)
    completed_count=models.PositiveIntegerField('已完成数',default=0)
    passed_count=models.PositiveIntegerField('通过数',default=0)
    failed_count=models.PositiveIntegerField('失败数',default=0)
    error_count=models.PositiveIntegerField('异常数',default=0)
    duration_ms=models.PositiveIntegerField('总耗时毫秒',null=True,blank=True)
    error_message=models.TextField('批次错误信息',blank=True)
    executed_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='发起人',
        on_delete=models.CASCADE,
        related_name='test_runs',
    )
    started_at=models.DateTimeField('开始时间',null=True,blank=True)
    finished_at=models.DateTimeField('结束时间',null=True,blank=True)
    created_at=models.DateTimeField('创建时间',auto_now_add=True)

    class Meta:
        db_table='executions_test_run'
        verbose_name='测试批次'
        verbose_name_plural='测试批次'
        ordering=['-created_at']

    def __str__(self):
        return self.name or f'测试批次 {self.pk}'


class TestExecution(models.Model):
    class Status(models.TextChoices):
        PENDING='pending','等待中'
        RUNNING='running','执行中'
        PASSED='passed','通过'
        FAILED='failed','失败'
        ERROR='error','异常'

    project=models.ForeignKey(
        Project,
        verbose_name='所属项目',
        on_delete=models.CASCADE,
        related_name='test_executions',
    )
    test_case=models.ForeignKey(
        TestCase,
        verbose_name='测试用例',
        on_delete=models.CASCADE,
        related_name='executions',
    )
    environment=models.ForeignKey(
        Environment,
        verbose_name='运行环境',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_executions',
    )
    # 单独执行时为空；批量执行时关联所属批次，用于汇总和报告。
    test_run=models.ForeignKey(
        TestRun,
        verbose_name='所属批次',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executions',
    )

    status=models.CharField(
        '执行状态',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    request_method=models.CharField('请求方法',max_length=10,blank=True)
    request_url=models.URLField('请求 URL',max_length=500,blank=True)
    request_headers=models.JSONField('请求头',default=dict,blank=True)
    request_query_params=models.JSONField('Query 参数',default=dict,blank=True)
    request_body=models.JSONField('请求体',default=dict,blank=True)

    response_status_code=models.PositiveIntegerField(
        '响应状态码',
        null=True,
        blank=True,
    )
    response_headers=models.JSONField('响应头',default=dict,blank=True)
    response_body=models.JSONField('响应体',default=dict,blank=True)

    duration_ms=models.PositiveIntegerField(
        '耗时毫秒',
        null=True,
        blank=True,
    )
    failure_message=models.TextField('断言失败原因',blank=True)
    error_message=models.TextField('错误信息',blank=True)

    executed_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='执行人',
        on_delete=models.CASCADE,
        related_name='test_executions',
    )
    started_at=models.DateTimeField('开始时间',null=True,blank=True)
    finished_at=models.DateTimeField('结束时间',null=True,blank=True)
    created_at=models.DateTimeField('创建时间',auto_now_add=True)

    class Meta:
        db_table='executions_test_execution'
        verbose_name='测试执行记录'
        verbose_name_plural='测试执行记录'
        ordering=['-created_at']
        constraints=[
            models.UniqueConstraint(
                fields=['test_run','test_case'],
                condition=Q(test_run__isnull=False),
                name='unique_test_case_per_test_run',
            ),
        ]

    def __str__(self):
        return f"{self.test_case.name} - {self.status}"
