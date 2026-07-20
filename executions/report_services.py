from .models import TestExecution, TestRun


def _calculate_rate(count, total):
    if total == 0:
        return 0.0
    return round(count / total * 100, 2)


def _get_result(test_run):
    # 批次尚未结束时只展示当前进度，不能提前判断最终测试结果。
    if test_run.status in {
        TestRun.Status.PENDING,
        TestRun.Status.RUNNING,
    }:
        return 'incomplete'

    if (
        test_run.status == TestRun.Status.COMPLETED
        and test_run.failed_count == 0
        and test_run.error_count == 0
    ):
        return 'passed'

    return 'failed'


def _execution_summary(execution):
    return {
        'execution_id':execution.id,
        'test_case_id':execution.test_case_id,
        'test_case_name':execution.test_case.name,
        'status':execution.status,
        'response_status_code':execution.response_status_code,
        'duration_ms':execution.duration_ms,
        'failure_message':execution.failure_message,
        'error_message':execution.error_message,
    }


def build_test_run_report(test_run):
    executions=list(test_run.executions.all())
    durations=[
        execution.duration_ms
        for execution in executions
        if execution.duration_ms is not None
    ]

    # 只对已经完成的用例计算结果比例，未执行用例不应被算作失败。
    completed_count=test_run.completed_count
    completion_rate=_calculate_rate(
        completed_count,
        test_run.total_count,
    )
    pass_rate=_calculate_rate(test_run.passed_count,completed_count)
    failure_rate=_calculate_rate(test_run.failed_count,completed_count)
    error_rate=_calculate_rate(test_run.error_count,completed_count)

    # 慢用例只比较有实际耗时的数据，环境配置错误等可能没有 duration_ms。
    slowest_executions=sorted(
        (
            execution
            for execution in executions
            if execution.duration_ms is not None
        ),
        key=lambda execution:execution.duration_ms,
        reverse=True,
    )[:5]
    problem_executions=[
        execution
        for execution in executions
        if execution.status in {
            TestExecution.Status.FAILED,
            TestExecution.Status.ERROR,
        }
    ]

    return {
        'test_run_id':test_run.id,
        'name':test_run.name,
        'status':test_run.status,
        'result':_get_result(test_run),
        'total_count':test_run.total_count,
        'completed_count':completed_count,
        'passed_count':test_run.passed_count,
        'failed_count':test_run.failed_count,
        'error_count':test_run.error_count,
        'completion_rate':completion_rate,
        'pass_rate':pass_rate,
        'failure_rate':failure_rate,
        'error_rate':error_rate,
        'total_duration_ms':test_run.duration_ms or 0,
        'average_duration_ms':(
            round(sum(durations) / len(durations),2)
            if durations
            else 0.0
        ),
        'max_duration_ms':max(durations) if durations else 0,
        'slowest_executions':[
            _execution_summary(execution)
            for execution in slowest_executions
        ],
        'problem_executions':[
            _execution_summary(execution)
            for execution in problem_executions
        ],
    }
