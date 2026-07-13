from django.db import models
from django.contrib.auth.models import AbstractUser



class User(AbstractUser):
    nickname=models.CharField('昵称',max_length=50,blank=True)
    phone=models.CharField('手机号',max_length=20,unique=True,null=True,blank=True)
    avatar=models.URLField('头像',blank=True)

    class Meta:
        db_table='users_user'
        verbose_name='用户'
        verbose_name_plural='用户'

    def __str__(self):
        return self.username