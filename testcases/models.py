from django.db import models
from django.conf import settings

from environments.models import Environment
from projects.models import Project
from interfaces.models import ApiEndpoint


class TestCase(models.Model):
    project=models.ForeignKey(
        Project,
        verbose_name='所属项目',
        on_delete=models.CASCADE,
        related_name='test_cases',
    )
    endpoint=models.ForeignKey(
        ApiEndpoint,
        verbose_name='关联接口',
        on_delete=models.CASCADE,
        related_name='test_cases',
    )
    environment=models.ForeignKey(
        Environment,
        verbose_name='运行环境',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='test_cases',
    )
    name=models.CharField('用例名称',max_length=100)
    description=models.TextField('用例描述',blank=True)

    headers=models.JSONField('请求头覆盖',default=dict,blank=True)
    query_params=models.JSONField('Query 参数覆盖',default=dict,blank=True)
    body=models.JSONField('请求体覆盖',default=dict,blank=True)

    expected_status_code=models.PositiveIntegerField('期望状态码',default=200)
    assertions=models.JSONField('断言规则',default=list,blank=True)

    created_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='创建人',
        on_delete=models.CASCADE,
        related_name="created_test_cases"
    )
    is_active=models.BooleanField('是否启用',default=True)
    created_at=models.DateTimeField('创建时间',auto_now_add=True)
    updated_at=models.DateTimeField('更新时间',auto_now=True)

    class Meta:
        db_table='testcases_test_case'
        verbose_name='测试用例'
        verbose_name_plural='测试用例'
        ordering=['-created_at']
        unique_together=['project','name']

    def __str__(self):
        return self.name