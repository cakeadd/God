import time
import re

import requests
from django.utils import timezone

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


def create_variable_error_execution(test_case, user, error_message):
    now = timezone.now()
    return TestExecution.objects.create(
        project=test_case.project,
        test_case=test_case,
        environment=test_case.environment,
        status=TestExecution.Status.ERROR,
        request_method=test_case.endpoint.method,
        error_message=error_message,
        executed_by=user,
        started_at=now,
        finished_at=now,
    )


def execute_test_case(test_case,user):
    endpoint=test_case.endpoint
    environment=test_case.environment
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
        return create_variable_error_execution(
            test_case,
            user,
            str(exc),
        )

    execution=TestExecution.objects.create(
        project=test_case.project,
        test_case=test_case,
        environment=environment,
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

        try:
            response_body=response.json()
        except ValueError:
            response_body={
                'text': response.text,
            }

        execution.response_status_code=response.status_code
        execution.response_headers=dict(response.headers)
        execution.response_body=response_body
        execution.duration_ms=duration_ms
        execution.finished_at=timezone.now()

        if response.status_code==test_case.expected_status_code:
            execution.status=TestExecution.Status.PASSED
        else:
            execution.status=TestExecution.Status.FAILED

        execution.save(
            update_fields=[
                'status',
                'response_status_code',
                'response_headers',
                'response_body',
                'duration_ms',
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
