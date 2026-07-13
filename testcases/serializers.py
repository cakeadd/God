from rest_framework import serializers

from .models import TestCase

class TestCaseSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    endpoint_name=serializers.CharField(source='endpoint.name',read_only=True)
    environment_name=serializers.SerializerMethodField()
    created_by_username=serializers.CharField(source='created_by.username',read_only=True)

    class Meta:
        model=TestCase
        fields = [
            'id',
            'project',
            'project_name',
            'endpoint',
            'endpoint_name',
            'environment',
            'environment_name',
            'name',
            'description',
            'headers',
            'query_params',
            'body',
            'expected_status_code',
            'assertions',
            'created_by',
            'created_by_username',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'project',
            'project_name',
            'endpoint_name',
            'environment_name',
            'created_by',
            'created_by_username',
            'is_active',
            'created_at',
            'updated_at',
        ]

    def get_environment_name(self, obj):
        if obj.environment is None:
            return None

        return obj.environment.name