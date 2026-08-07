from rest_framework import serializers

from .models import TestCase

class TestCaseSerializer(serializers.ModelSerializer):
    project_name=serializers.CharField(source='project.name',read_only=True)
    endpoint_name=serializers.CharField(source='endpoint.name',read_only=True)
    endpoint_method=serializers.CharField(source='endpoint.method',read_only=True)
    endpoint_path=serializers.CharField(source='endpoint.path',read_only=True)
    endpoint_is_active=serializers.BooleanField(source='endpoint.is_active',read_only=True)
    environment_name=serializers.SerializerMethodField()
    environment_is_active=serializers.SerializerMethodField()
    assertion_count=serializers.SerializerMethodField()
    created_by_username=serializers.CharField(source='created_by.username',read_only=True)

    class Meta:
        model=TestCase
        fields = [
            'id',
            'project',
            'project_name',
            'endpoint',
            'endpoint_name',
            'endpoint_method',
            'endpoint_path',
            'endpoint_is_active',
            'environment',
            'environment_name',
            'environment_is_active',
            'name',
            'description',
            'headers',
            'query_params',
            'body',
            'expected_status_code',
            'assertions',
            'assertion_count',
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
            'endpoint_method',
            'endpoint_path',
            'endpoint_is_active',
            'environment_name',
            'environment_is_active',
            'assertion_count',
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

    def get_environment_is_active(self, obj):
        if obj.environment is None:
            return None
        return obj.environment.is_active

    def get_assertion_count(self, obj):
        return len(obj.assertions) if isinstance(obj.assertions, list) else 0

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

    def validate(self, attrs):
        errors = {}

        # 执行服务会把接口配置与用例覆盖值按字典合并，因此这里只接受 JSON 对象。
        for field_name in ('headers', 'query_params', 'body'):
            if field_name in attrs and not isinstance(attrs[field_name], dict):
                errors[field_name] = '必须是 JSON 对象'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def validate_expected_status_code(self, value):
        if not 100 <= value <= 599:
            raise serializers.ValidationError('HTTP 状态码必须在 100 到 599 之间')
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
                expected = assertion['expected']
                if (
                    not isinstance(expected, int)
                    or isinstance(expected, bool)
                    or not 100 <= expected <= 599
                ):
                    raise serializers.ValidationError(
                        f'第 {index + 1} 条状态码断言的 expected '
                        '必须是 100 到 599 之间的整数'
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
