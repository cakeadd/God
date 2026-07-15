from rest_framework import serializers

from .models import TestExecution


class TestExecutionListSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    test_case_name=serializers.CharField(source='test_case.name',read_only=True)
    environment_name=serializers.SerializerMethodField()
    executed_by_username=serializers.CharField(source='executed_by.username',read_only=True)

    class Meta:
        model = TestExecution
        fields=[
            'id',
            'project',
            'project_name',
            'test_case',
            'test_case_name',
            'environment',
            'environment_name',
            'status',
            'response_status_code',
            'duration_ms',
            'failure_message',
            'error_message',
            'executed_by',
            'executed_by_username',
            'started_at',
            'finished_at',
            'created_at',
        ]
        read_only_fields=fields

    def get_environment_name(self,obj):
        if not obj.environment:
            return None
        return obj.environment.name


class TestExecutionSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    test_case_name=serializers.CharField(source='test_case.name',read_only=True)
    environment_name=serializers.SerializerMethodField()
    executed_by_username=serializers.CharField(source='executed_by.username',read_only=True)

    class Meta:
        model = TestExecution
        fields=[
            'id',
            'project',
            'project_name',
            'test_case',
            'test_case_name',
            'environment',
            'environment_name',
            'status',
            'request_method',
            'request_url',
            'request_headers',
            'request_query_params',
            'request_body',
            'response_status_code',
            'response_headers',
            'response_body',
            'duration_ms',
            'failure_message',
            'error_message',
            'executed_by',
            'executed_by_username',
            'started_at',
            'finished_at',
            'created_at',
        ]
        read_only_fields=[
            'id',
            'project',
            'project_name',
            'test_case_name',
            'environment_name',
            'status',
            'request_method',
            'request_url',
            'request_headers',
            'request_query_params',
            'request_body',
            'response_status_code',
            'response_headers',
            'response_body',
            'duration_ms',
            'failure_message',
            'error_message',
            'executed_by',
            'executed_by_username',
            'started_at',
            'finished_at',
            'created_at',
        ]

    def get_environment_name(self,obj):
        if not obj.environment:
            return None
        return obj.environment.name
