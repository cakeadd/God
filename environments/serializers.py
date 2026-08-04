from rest_framework import serializers

from .models import Environment

class EnvironmentSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name', read_only=True)

    def validate_name(self, value):
        project = self.context.get('project')
        if project is None:
            return value

        # 项目由 URL 决定而不是客户端提交，因此在当前项目范围内校验环境名称。
        environments = Environment.objects.filter(project=project, name=value)
        if self.instance is not None:
            environments = environments.exclude(pk=self.instance.pk)

        if environments.exists():
            raise serializers.ValidationError(
                '当前项目已存在同名环境，请修改环境名称后重试。'
            )
        return value

    def validate_variables(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('环境变量必须是 JSON 对象')
        return value

    class Meta:
        model = Environment
        fields=[
            'id',
            'project',
            'project_name',
            'name',
            'base_url',
            'variables',
            'description',
            'is_default',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields=[
            'id',
            'project',
            'project_name',
            'is_active',
            'created_at',
            'updated_at',
        ]
