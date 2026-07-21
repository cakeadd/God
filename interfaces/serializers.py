from rest_framework import serializers

from .models import ApiEndpoint

class ApiEndpointSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    created_by_username=serializers.CharField(source='created_by.username',read_only=True)

    class Meta:
        model=ApiEndpoint
        fields=[
            'id',
            'project',
            'project_name',
            'name',
            'method',
            'path',
            'description',
            'headers',
            'query_params',
            'body',
            'created_by',
            'created_by_username',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields=[
            'id',
            'project',
            'project_name',
            'created_by',
            'created_by_username',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        errors = {}

        # 执行服务会把接口配置与用例覆盖值按字典合并，因此这里只接受 JSON 对象。
        for field_name in ('headers', 'query_params', 'body'):
            if field_name in attrs and not isinstance(attrs[field_name], dict):
                errors[field_name] = '必须是 JSON 对象'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
