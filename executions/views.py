from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from projects.permissions import can_edit_project_resource
from testcases.models import TestCase
from .serializers import TestExecutionListSerializer, TestExecutionSerializer
from .services import execute_test_case

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
            'executed_by',
        )
        serializer=TestExecutionListSerializer(
            executions,
            many=True,
            context={'request':request}
        )

        return Response(
            serializer.data
        )


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
                'executed_by',
            ),
            pk=pk,
        )
        serializer=TestExecutionSerializer(
            execution,
            context={'request':request},
        )

        return Response(serializer.data)
