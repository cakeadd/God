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

    def validate_name(self, value):
        project = self.context.get('project')
        if project is None:
            return value

        # 测试用例名称是当前项目内的业务标识，创建和编辑都使用相同的唯一性规则。
        test_cases = TestCase.objects.filter(project=project, name=value)
        if self.instance is not None:
            test_cases = test_cases.exclude(pk=self.instance.pk)

        if test_cases.exists():
            raise serializers.ValidationError(
                '当前项目已存在同名测试用例，请修改用例名称后重试。'
            )
        return value

    def validate_assertions(self, assertions):
        if not isinstance(assertions, list):
            raise serializers.ValidationError('断言规则必须是列表')

        for index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                raise serializers.ValidationError(
                    f'第 {index + 1} 条断言必须是对象'
                )

            assertion_type = assertion.get('type')
            if assertion_type == 'status_code':
                if 'expected' not in assertion:
                    raise serializers.ValidationError(
                        f'第 {index + 1} 条断言缺少 expected'
                    )
                continue

            if assertion_type != 'json_field_equals':
                raise serializers.ValidationError(
                    f'第 {index + 1} 条断言类型只支持 '
                    'status_code 或 json_field_equals'
                )

            path = assertion.get('path')
            if not isinstance(path, str) or not path or any(
                not segment for segment in path.split('.')
            ):
                raise serializers.ValidationError(
                    f'第 {index + 1} 条断言的 path 必须是有效的点号路径'
                )

            if 'expected' not in assertion:
                raise serializers.ValidationError(
                    f'第 {index + 1} 条断言缺少 expected'
                )

        return assertions
