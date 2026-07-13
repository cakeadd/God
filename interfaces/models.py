from django.db import models
from django.conf import settings

from projects.models import Project

class ApiEndpoint(models.Model):
    class Method(models.TextChoices):
        GET = 'GET','GET'
        POST = 'POST','POST'
        PUT = 'PUT','PUT'
        DELETE = 'DELETE','DELETE'
        PATCH = 'PATCH','PATCH'

    project=models.ForeignKey(
        Project,
        verbose_name='所属项目',
        on_delete=models.CASCADE,
        related_name='api_endpoints',
    )
    name=models.CharField('接口名称',max_length=100)
    method=models.CharField('请求方法',max_length=10,choices=Method.choices)
    path=models.CharField('接口路径',max_length=255)
    description=models.TextField('接口描述',blank=True)

    headers=models.JSONField('请求头',default=dict,blank=True)
    query_params=models.JSONField('Query参数',default=dict,blank=True)
    body=models.JSONField('请求体',default=dict,blank=True)

    created_by=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='创建人',
        on_delete=models.CASCADE,
        related_name='created_api_endpoints'
    )

    is_active=models.BooleanField('是否启用',default=True)
    created_at=models.DateTimeField('创建时间',auto_now_add=True)
    updated_at=models.DateTimeField('更新时间',auto_now=True)

    class Meta:
        db_table='interfaces_api_endpoint'
        verbose_name='接口'
        verbose_name_plural='接口'
        ordering=['-created_at']
        unique_together=['project','method','path']

    def __str__(self):
        return f"{self.method} {self.path}"