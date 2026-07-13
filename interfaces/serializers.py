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