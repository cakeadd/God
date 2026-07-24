from django.db import models
from django.conf import settings

class Project(models.Model):
    name=models.CharField('项目名称',max_length=100)
    description=models.TextField('项目描述',blank=True)
    owner=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='创建者',
        on_delete=models.CASCADE,
        related_name='owned_projects',
    )
    is_archived=models.BooleanField('是否归档',default=False)
    created_at=models.DateTimeField('创建时间',auto_now_add=True)
    updated_at=models.DateTimeField('更新时间',auto_now=True)

    class Meta:
        db_table='projects_project'
        verbose_name='项目'
        verbose_name_plural='项目'
        ordering=['-created_at']

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        OWNER='owner','拥有者'
        MEMBER='member','成员'
        VIEWER='viewer','只读成员'


    project=models.ForeignKey(
        Project,
        verbose_name='项目',
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='成员',
        on_delete=models.CASCADE,
        related_name='project_memberships',
    )
    role=models.CharField('角色',max_length=20,choices=Role.choices)
    joined_at=models.DateTimeField('加入时间',auto_now_add=True)

    class Meta:
        db_table='projects_project_member'
        verbose_name='项目成员'
        verbose_name_plural='项目成员'
        unique_together=['project','user']

    def __str__(self):
        return f"{self.project.name} - {self.user.username} - {self.role}"
