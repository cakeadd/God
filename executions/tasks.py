from celery import shared_task

from .run_services import execute_test_run


@shared_task(name='executions.execute_test_run')
def execute_test_run_task(test_run_id):
    # Redis 中只传批次 ID，Worker 自己从数据库加载最新数据。
    test_run = execute_test_run(test_run_id)
    return test_run.id
