from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Project,ProjectMember

User=get_user_model()

class ProjectSerializer(serializers.ModelSerializer):
    owner_username=serializers.CharField(source='owner.username',read_only=True)
    my_role=serializers.SerializerMethodField()

    class Meta:
        model=Project
        fields=[
            'id',
            'name',
            'description',
            'owner',
            'owner_username',
            'my_role',
            'is_archived',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'owner',
            'owner_username',
            'my_role',
            'is_archived',
            'created_at',
            'updated_at',
        ]

    def get_my_role(self,obj):
        request=self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        membership=ProjectMember.objects.filter(
            project=obj,
            user=request.user,
        ).first()

        if not membership:
            return None

        return membership.role


class ProjectMemberSerializer(serializers.ModelSerializer):
    username=serializers.CharField(source='user.username',read_only=True)
    nickname=serializers.CharField(source='user.nickname',read_only=True)

    class Meta:
        model=ProjectMember
        fields=[
            'id',
            'user',
            'username',
            'nickname',
            'role',
            'joined_at',
        ]
        read_only_fields=fields


class ProjectMemberCandidateSerializer(serializers.ModelSerializer):
    is_project_member=serializers.BooleanField(read_only=True)
    project_role=serializers.CharField(read_only=True,allow_null=True)

    class Meta:
        model=User
        fields=[
            'id',
            'username',
            'nickname',
            'is_project_member',
            'project_role',
        ]
        read_only_fields=fields


class ProjectMemberCreateSerializer(serializers.ModelSerializer):
    role=serializers.ChoiceField(choices=[
        (ProjectMember.Role.MEMBER,ProjectMember.Role.MEMBER.label),
        (ProjectMember.Role.VIEWER,ProjectMember.Role.VIEWER.label),
    ])

    class Meta:
        model=ProjectMember
        fields=['user','role']

    def validate_user(self,value):
        project=self.context['project']
        if ProjectMember.objects.filter(project=project,user=value).exists():
            raise serializers.ValidationError('该用户已经是项目成员')
        return value


class ProjectMemberRoleSerializer(serializers.ModelSerializer):
    role=serializers.ChoiceField(choices=[
        (ProjectMember.Role.MEMBER,ProjectMember.Role.MEMBER.label),
        (ProjectMember.Role.VIEWER,ProjectMember.Role.VIEWER.label),
    ])

    class Meta:
        model=ProjectMember
        fields=['role']

    def validate_role(self,value):
        if self.instance.role == ProjectMember.Role.OWNER:
            raise serializers.ValidationError('不能修改项目拥有者的身份')
        return value
