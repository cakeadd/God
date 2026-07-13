from django.db import models

from projects.models import Project

class Environment(models.Model):
    project=models.ForeignKey(
        Project,
        verbose_name='所属项目',
        on_delete=models.CASCADE,
        related_name='environments',
    )
    name=models.CharField('环境名称', max_length=100)
    base_url=models.URLField('基础地址')
    variables=models.JSONField('环境变量',default=dict,blank=True)
    description=models.TextField('环境描述',blank=True)
    is_default=models.BooleanField('是否默认环境',default=False)
    is_active=models.BooleanField('是否启用',default=True)
    created_at=models.DateTimeField('创建时间',auto_now_add=True)
    updated_at=models.DateTimeField('更新时间',auto_now=True)

    class Meta:
        db_table='environments_environment'
        verbose_name='环境'
        verbose_name_plural='环境'
        ordering=['-created_at']
        unique_together=['project','name']

    def __str__(self):
        return  f"{self.project.name} - {self.name}"