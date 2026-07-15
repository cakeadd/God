from rest_framework import serializers

from .models import TestExecution, TestRun


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
            'test_run',
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
            'test_run',
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
            'test_run',
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


class TestRunCreateSerializer(serializers.Serializer):
    name=serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default='',
    )
    test_case_ids=serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=20,
    )

    def validate_test_case_ids(self, test_case_ids):
        if len(test_case_ids) != len(set(test_case_ids)):
            raise serializers.ValidationError('测试用例 ID 不能重复')
        return test_case_ids


class TestRunListSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    executed_by_username=serializers.CharField(
        source='executed_by.username',
        read_only=True,
    )

    class Meta:
        model=TestRun
        fields=[
            'id',
            'project',
            'project_name',
            'name',
            'status',
            'total_count',
            'completed_count',
            'passed_count',
            'failed_count',
            'error_count',
            'duration_ms',
            'error_message',
            'executed_by',
            'executed_by_username',
            'started_at',
            'finished_at',
            'created_at',
        ]
        read_only_fields=fields


class TestRunDetailSerializer(TestRunListSerializer):
    test_cases=serializers.SerializerMethodField()
    executions=TestExecutionListSerializer(many=True,read_only=True)

    class Meta(TestRunListSerializer.Meta):
        fields=TestRunListSerializer.Meta.fields + [
            'test_cases',
            'executions',
        ]

    def get_test_cases(self,obj):
        return [
            {
                'id': test_case.id,
                'name': test_case.name,
            }
            for test_case in obj.test_cases.all()
        ]
