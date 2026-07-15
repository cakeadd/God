import time
import re
import json

import requests
from django.utils import timezone

from environments.models import Environment
from .models import TestExecution

VARIABLE_PATTERN = re.compile(r'{{\s*([^{}\s]+)\s*}}')
SENSITIVE_HEADER_NAMES = {
    'authorization',
    'proxy-authorization',
    'cookie',
    'set-cookie',
    'x-api-key',
    'api-key',
    'x-auth-token',
}


class VariableSubstitutionError(ValueError):
    pass


class JsonFieldLookupError(ValueError):
    pass


class EnvironmentResolutionError(ValueError):
    pass


def substitute_variables(data, variables):
    if not isinstance(variables, dict):
        raise VariableSubstitutionError('环境变量必须是 JSON 对象')

    if isinstance(data, dict):
        return {
            key: substitute_variables(value, variables)
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [substitute_variables(item, variables) for item in data]

    if not isinstance(data, str):
        return data

    full_match = VARIABLE_PATTERN.fullmatch(data)
    if full_match:
        variable_name = full_match.group(1)
        if variable_name not in variables:
            raise VariableSubstitutionError(
                f'环境变量 {variable_name} 未定义'
            )
        return variables[variable_name]

    def replace_match(match):
        variable_name = match.group(1)
        if variable_name not in variables:
            raise VariableSubstitutionError(
                f'环境变量 {variable_name} 未定义'
            )
        return str(variables[variable_name])

    return VARIABLE_PATTERN.sub(replace_match, data)


def mask_sensitive_headers(headers):
    masked_headers = {}

    for name, value in headers.items():
        if name.lower() in SENSITIVE_HEADER_NAMES:
            if isinstance(value, str) and ' ' in value:
                scheme = value.split(' ', 1)[0]
                masked_headers[name] = f'{scheme} ***'
            else:
                masked_headers[name] = '***'
        else:
            masked_headers[name] = value

    return masked_headers


def build_request_url(environment, path):
    if environment is None or not environment.base_url:
        return ''

    if not isinstance(path, str):
        raise VariableSubstitutionError('接口路径替换后必须是字符串')

    return f"{environment.base_url.rstrip('/')}/{path.lstrip('/')}"


def get_json_field_value(data, path):
    current_value = data

    for segment in path.split('.'):
        if isinstance(current_value, dict):
            if segment not in current_value:
                raise JsonFieldLookupError(f'字段 {segment} 不存在')
            current_value = current_value[segment]
        elif isinstance(current_value, list):
            if not segment.isdigit():
                raise JsonFieldLookupError(f'{segment} 不是有效的数组下标')

            index = int(segment)
            if index >= len(current_value):
                raise JsonFieldLookupError(f'数组下标 {index} 超出范围')
            current_value = current_value[index]
        else:
            raise JsonFieldLookupError(
                f'无法从 {segment} 之前的值继续读取字段'
            )

    return current_value


def evaluate_json_assertions(response_body, assertions):
    failure_messages = []

    for assertion in assertions:
        path = assertion['path']
        expected = assertion['expected']

        try:
            actual = get_json_field_value(response_body, path)
        except JsonFieldLookupError as exc:
            failure_messages.append(
                f'JSON 字段断言失败：{path}，{exc}'
            )
            continue

        if actual != expected:
            failure_messages.append(
                'JSON 字段断言失败：'
                f'{path} 期望 {json.dumps(expected, ensure_ascii=False)}，'
                f'实际 {json.dumps(actual, ensure_ascii=False)}'
            )

    return failure_messages


def evaluate_legacy_status_code_assertions(response_status_code, assertions):
    failure_messages = []

    for assertion in assertions:
        if assertion['type'] != 'status_code':
            continue

        if response_status_code != assertion['expected']:
            failure_messages.append(
                f'状态码断言失败：期望 {assertion["expected"]}，'
                f'实际 {response_status_code}'
            )

    return failure_messages


def resolve_execution_environment(test_case):
    if test_case.environment_id is not None:
        if not test_case.environment.is_active:
            raise EnvironmentResolutionError('测试用例绑定的环境已停用')
        return test_case.environment

    environment = Environment.objects.filter(
        project=test_case.project,
        is_active=True,
        is_default=True,
    ).first()
    if environment is None:
        raise EnvironmentResolutionError(
            '测试用例未绑定环境，项目也没有可用的默认环境'
        )

    return environment


def create_error_execution(
    test_case,
    user,
    error_message,
    environment=None,
    test_run=None,
):
    now = timezone.now()
    return TestExecution.objects.create(
        project=test_case.project,
        test_case=test_case,
        environment=environment,
        test_run=test_run,
        status=TestExecution.Status.ERROR,
        request_method=test_case.endpoint.method,
        error_message=error_message,
        executed_by=user,
        started_at=now,
        finished_at=now,
    )


def execute_test_case(test_case,user,test_run=None):
    endpoint=test_case.endpoint

    try:
        environment=resolve_execution_environment(test_case)
    except EnvironmentResolutionError as exc:
        return create_error_execution(
            test_case,
            user,
            str(exc),
            environment=test_case.environment,
            test_run=test_run,
        )

    variables=environment.variables if environment else {}

    request_method=endpoint.method

    try:
        request_path=substitute_variables(endpoint.path,variables)
        request_url=build_request_url(environment,request_path)
        request_headers=substitute_variables(
            {**endpoint.headers, **test_case.headers},
            variables,
        )
        request_query_params=substitute_variables(
            {**endpoint.query_params, **test_case.query_params},
            variables,
        )
        request_body=substitute_variables(
            {**endpoint.body, **test_case.body},
            variables,
        )
    except VariableSubstitutionError as exc:
        return create_error_execution(
            test_case,
            user,
            str(exc),
            environment=environment,
            test_run=test_run,
        )

    execution=TestExecution.objects.create(
        project=test_case.project,
        test_case=test_case,
        environment=environment,
        test_run=test_run,
        status=TestExecution.Status.RUNNING,
        request_method=request_method,
        request_url=request_url,
        request_headers=mask_sensitive_headers(request_headers),
        request_query_params=request_query_params,
        request_body=request_body,
        executed_by=user,
        started_at=timezone.now()
    )

    if not request_url:
        execution.status=TestExecution.Status.ERROR
        execution.error_message='测试用例没有可用的运行环境或 base_url'
        execution.finished_at=timezone.now()
        execution.save(update_fields=[
            'status',
            'error_message',
            'finished_at',
        ])
        return execution

    start_time=time.perf_counter()

    try:
        response=requests.request(
            method=request_method,
            url=request_url,
            headers=request_headers,
            params=request_query_params,
            json=request_body if request_body else None,
            timeout=10
        )
        duration_ms=int((time.perf_counter()-start_time)*1000)

        response_is_json = True
        try:
            response_body=response.json()
        except ValueError:
            response_is_json = False
            response_body={
                'text': response.text,
            }

        execution.response_status_code=response.status_code
        execution.response_headers=dict(response.headers)
        execution.response_body=response_body
        execution.duration_ms=duration_ms
        execution.finished_at=timezone.now()

        failure_messages = []
        if response.status_code != test_case.expected_status_code:
            failure_messages.append(
                f'状态码断言失败：期望 {test_case.expected_status_code}，'
                f'实际 {response.status_code}'
            )

        if test_case.assertions:
            failure_messages.extend(
                evaluate_legacy_status_code_assertions(
                    response.status_code,
                    test_case.assertions,
                )
            )
            json_assertions = [
                assertion
                for assertion in test_case.assertions
                if assertion['type'] == 'json_field_equals'
            ]
            if json_assertions and response_is_json:
                failure_messages.extend(
                    evaluate_json_assertions(
                        response_body,
                        json_assertions,
                    )
                )
            elif json_assertions:
                failure_messages.append('JSON 字段断言失败：响应不是有效 JSON')

        failure_messages = list(dict.fromkeys(failure_messages))

        if failure_messages:
            execution.status=TestExecution.Status.FAILED
            execution.failure_message='\n'.join(failure_messages)
        else:
            execution.status=TestExecution.Status.PASSED

        execution.save(
            update_fields=[
                'status',
                'response_status_code',
                'response_headers',
                'response_body',
                'duration_ms',
                'failure_message',
                'finished_at',
            ]
        )

    except requests.RequestException as exc:
        duration_ms=int((time.perf_counter()-start_time)*1000)

        execution.status = TestExecution.Status.ERROR
        execution.duration_ms = duration_ms
        execution.error_message = str(exc)
        execution.finished_at = timezone.now()
        execution.save(update_fields=[
            'status',
            'duration_ms',
            'error_message',
            'finished_at',
        ])

    return execution
