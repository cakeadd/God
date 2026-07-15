import logging

from django.db import transaction
from django.utils import timezone

from .models import TestExecution, TestRun
from .services import create_error_execution, execute_test_case


logger = logging.getLogger(__name__)


@transaction.atomic
def create_test_run(project, user, test_cases, name=''):
    test_run = TestRun.objects.create(
        project=project,
        name=name,
        total_count=len(test_cases),
        executed_by=user,
    )
    # 先保存本次计划执行的用例，Worker 中途退出时仍能还原任务范围。
    test_run.test_cases.set(test_cases)
    return test_run


def _update_test_run_counts(test_run):
    executions = test_run.executions.all()
    test_run.completed_count = executions.count()
    test_run.passed_count = executions.filter(
        status=TestExecution.Status.PASSED,
    ).count()
    test_run.failed_count = executions.filter(
        status=TestExecution.Status.FAILED,
    ).count()
    test_run.error_count = executions.filter(
        status=TestExecution.Status.ERROR,
    ).count()
    test_run.save(update_fields=[
        'completed_count',
        'passed_count',
        'failed_count',
        'error_count',
    ])


def _finish_test_run(test_run, status, error_message=''):
    finished_at = timezone.now()
    test_run.status = status
    test_run.finished_at = finished_at
    test_run.error_message = error_message
    if test_run.started_at:
        test_run.duration_ms = int(
            (finished_at - test_run.started_at).total_seconds() * 1000
        )
    test_run.save(update_fields=[
        'status',
        'duration_ms',
        'error_message',
        'finished_at',
    ])


def _record_case_error(test_run, test_case, error_message):
    execution = test_run.executions.filter(test_case=test_case).first()
    if execution is None:
        return create_error_execution(
            test_case,
            test_run.executed_by,
            error_message,
            environment=test_case.environment,
            test_run=test_run,
        )

    # 单用例可能已经创建 running 记录，直接更新可避免重复记录。
    execution.status = TestExecution.Status.ERROR
    execution.error_message = error_message
    execution.finished_at = timezone.now()
    execution.save(update_fields=[
        'status',
        'error_message',
        'finished_at',
    ])
    return execution


def execute_test_run(test_run_id):
    # 锁定批次并只允许 pending -> running，防止同一 Celery 消息重复消费。
    with transaction.atomic():
        test_run = TestRun.objects.select_for_update().select_related(
            'executed_by',
        ).get(pk=test_run_id)
        if test_run.status != TestRun.Status.PENDING:
            return test_run

        test_run.status = TestRun.Status.RUNNING
        test_run.started_at = timezone.now()
        test_run.save(update_fields=['status','started_at'])

    try:
        test_cases = test_run.test_cases.select_related(
            'project',
            'endpoint',
            'environment',
        ).order_by('id')

        for test_case in test_cases:
            try:
                if not test_case.is_active:
                    _record_case_error(
                        test_run,
                        test_case,
                        '测试用例已停用',
                    )
                else:
                    # 单用例执行逻辑保持唯一入口，继续复用环境、变量和断言能力。
                    execute_test_case(
                        test_case,
                        test_run.executed_by,
                        test_run=test_run,
                    )
            except Exception as exc:
                logger.exception(
                    '批次 %s 执行用例 %s 时发生未处理异常',
                    test_run.pk,
                    test_case.pk,
                )
                _record_case_error(
                    test_run,
                    test_case,
                    f'批量执行用例时发生异常：{exc}',
                )

            # 每完成一条就更新计数，前端轮询时可以看到真实进度。
            _update_test_run_counts(test_run)

        _finish_test_run(test_run, TestRun.Status.COMPLETED)
    except Exception as exc:
        logger.exception('批次 %s 执行失败', test_run.pk)
        _update_test_run_counts(test_run)
        _finish_test_run(
            test_run,
            TestRun.Status.ERROR,
            str(exc),
        )
        raise

    return test_run
