from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerOperationalError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from God.pagination import StandardPageNumberPagination
from projects.models import Project
from projects.permissions import can_edit_project_resource
from testcases.models import TestCase
from .models import TestExecution, TestRun
from .report_services import build_test_run_report
from .run_services import create_test_run
from .serializers import (
    TestExecutionListSerializer,
    TestExecutionSerializer,
    TestRunCreateSerializer,
    TestRunDetailSerializer,
    TestRunListSerializer,
    TestRunReportSerializer,
)
from .services import execute_test_case
from .tasks import execute_test_run_task


def _enqueue_test_run(test_run):
    try:
        # 批次提交数据库后再发送 ID，Worker 才能稳定读取到记录。
        execute_test_run_task.delay(test_run.id)
    except BrokerOperationalError:
        test_run.status=TestRun.Status.ERROR
        test_run.error_message='任务提交失败，请检查 Redis 服务'
        test_run.finished_at=timezone.now()
        test_run.save(update_fields=[
            'status',
            'error_message',
            'finished_at',
        ])
        return False
    return True


class TestCaseExecuteView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False
        )

    def get_test_case(self,project,testcase_id):
        return get_object_or_404(
            TestCase,
            id=testcase_id,
            project=project,
            is_active=True
        )

    def post(self,request,project_id,testcase_id):
        project=self.get_project(request,project_id)

        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限执行该测试用例'},
                status=status.HTTP_403_FORBIDDEN
            )

        test_case=self.get_test_case(project,testcase_id)

        execution=execute_test_case(
            test_case=test_case,
            user=request.user
        )

        serializer=TestExecutionSerializer(
            execution,
            context={'request':request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

class TestExecutionListView(APIView):
    permission_classes = [IsAuthenticated]

    status_search_values = {
        '等待中': TestExecution.Status.PENDING,
        '执行中': TestExecution.Status.RUNNING,
        '通过': TestExecution.Status.PASSED,
        '失败': TestExecution.Status.FAILED,
        '异常': TestExecution.Status.ERROR,
    }

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False
        )
    def get(self,request,project_id):
        project=self.get_project(request,project_id)

        executions=project.test_executions.select_related(
            'project',
            'test_case',
            'environment',
            'test_run',
            'executed_by',
        )

        search=request.query_params.get('search','').strip()
        if search:
            # 状态使用精确匹配，其余展示字段使用模糊匹配。
            normalized_status=self.status_search_values.get(
                search,
                search.lower(),
            )
            executions=executions.filter(
                Q(status__iexact=normalized_status)
                | Q(test_case__name__icontains=search)
                | Q(executed_by__username__icontains=search)
            )

        # 执行记录会持续累积，必须在序列化前完成服务端分页。
        paginator=StandardPageNumberPagination()
        page=paginator.paginate_queryset(executions,request)
        serializer=TestExecutionListSerializer(
            page,
            many=True,
            context={'request':request}
        )

        return paginator.get_paginated_response(serializer.data)


class TestExecutionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get(self,request,project_id,pk):
        project=self.get_project(request,project_id)
        execution=get_object_or_404(
            project.test_executions.select_related(
                'project',
                'test_case',
                'environment',
                'test_run',
                'executed_by',
            ),
            pk=pk,
        )
        serializer=TestExecutionSerializer(
            execution,
            context={'request':request},
        )

        return Response(serializer.data)


class TestRunListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get(self,request,project_id):
        project=self.get_project(request,project_id)
        test_runs=project.test_runs.select_related(
            'project',
            'executed_by',
        ).order_by('-created_at','-id')

        # 批次历史会持续累积，先在服务端分页再序列化。
        paginator=StandardPageNumberPagination()
        page=paginator.paginate_queryset(test_runs,request,view=self)
        serializer=TestRunListSerializer(
            page,
            many=True,
            context={'request':request},
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self,request,project_id):
        project=self.get_project(request,project_id)
        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限发起批量执行'},
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer=TestRunCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        test_case_ids=input_serializer.validated_data['test_case_ids']
        test_cases=list(
            project.test_cases.filter(
                id__in=test_case_ids,
                is_active=True,
            )
        )
        found_ids={test_case.id for test_case in test_cases}
        invalid_ids=[
            test_case_id
            for test_case_id in test_case_ids
            if test_case_id not in found_ids
        ]
        if invalid_ids:
            return Response(
                {
                    'detail':'部分测试用例不属于当前项目或已停用',
                    'invalid_test_case_ids':invalid_ids,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_run=create_test_run(
            project=project,
            user=request.user,
            test_cases=test_cases,
            name=input_serializer.validated_data['name'],
        )

        if not _enqueue_test_run(test_run):
            serializer=TestRunListSerializer(test_run)
            return Response(
                serializer.data,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer=TestRunListSerializer(
            test_run,
            context={'request':request},
        )
        return Response(
            serializer.data,
            status=status.HTTP_202_ACCEPTED,
        )


class TestRunRerunView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def post(self,request,project_id,pk):
        project=self.get_project(request,project_id)
        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限再次执行该批次'},
                status=status.HTTP_403_FORBIDDEN,
            )

        source_test_run=get_object_or_404(
            project.test_runs,
            pk=pk,
        )
        if source_test_run.status not in [
            TestRun.Status.COMPLETED,
            TestRun.Status.ERROR,
        ]:
            return Response(
                {'detail':'只有已完成或异常的历史批次可以再次执行'},
                status=status.HTTP_409_CONFLICT,
            )

        test_cases=list(source_test_run.test_cases.all().order_by('id'))
        if len(test_cases) != source_test_run.total_count:
            return Response(
                {'detail':'历史批次中的部分测试用例已不存在，无法再次执行'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= len(test_cases) <= 20:
            return Response(
                {'detail':'历史批次的测试用例数量必须在 1 至 20 条之间'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        inactive_test_cases=[
            {'id':test_case.id,'name':test_case.name}
            for test_case in test_cases
            if not test_case.is_active
        ]
        if inactive_test_cases:
            inactive_names='、'.join(
                test_case['name']
                for test_case in inactive_test_cases
            )
            return Response(
                {
                    'detail':f'历史批次包含已停用的测试用例：{inactive_names}，无法再次执行',
                    'inactive_test_cases':inactive_test_cases,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 历史批次只作为用例集合模板，新批次拥有独立状态和执行结果。
        test_run=create_test_run(
            project=project,
            user=request.user,
            test_cases=test_cases,
            name=source_test_run.name,
        )
        if not _enqueue_test_run(test_run):
            serializer=TestRunListSerializer(test_run)
            return Response(
                serializer.data,
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer=TestRunListSerializer(
            test_run,
            context={'request':request},
        )
        return Response(
            serializer.data,
            status=status.HTTP_202_ACCEPTED,
        )


class TestRunDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get(self,request,project_id,pk):
        project=self.get_project(request,project_id)
        execution_queryset=TestExecution.objects.select_related(
            'project',
            'test_case',
            'environment',
            'test_run',
            'executed_by',
        )
        test_run=get_object_or_404(
            project.test_runs.select_related(
                'project',
                'executed_by',
            ).prefetch_related(
                'test_cases',
                Prefetch('executions',queryset=execution_queryset),
            ),
            pk=pk,
        )
        serializer=TestRunDetailSerializer(
            test_run,
            context={'request':request},
        )
        return Response(serializer.data)


class TestRunReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get(self,request,project_id,pk):
        project=self.get_project(request,project_id)
        execution_queryset=TestExecution.objects.select_related(
            'test_case',
        )
        test_run=get_object_or_404(
            project.test_runs.prefetch_related(
                Prefetch('executions',queryset=execution_queryset),
            ),
            pk=pk,
        )
        report=build_test_run_report(test_run)
        serializer=TestRunReportSerializer(report)
        return Response(serializer.data)
