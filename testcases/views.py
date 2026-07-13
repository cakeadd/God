from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from projects.permissions import can_edit_project_resource
from .serializers import TestCaseSerializer


class TestCaseListCreateView(APIView):
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

        test_cases=project.test_cases.filter(
            is_active=True,
        )
        serializer=TestCaseSerializer(
            test_cases,
            many=True,
            context={'request':request}
        )

        return Response(serializer.data)

    def post(self,request,project_id):
        project=self.get_project(request,project_id)

        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限在该项目下创建测试用例'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer=TestCaseSerializer(
            data=request.data,
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)

        endpoint=serializer.validated_data['endpoint']
        if endpoint.project_id != project.id or not endpoint.is_active:
            return Response(
                {'detail':'接口不属于当前项目，或接口已停用'},
                status=status.HTTP_400_BAD_REQUEST
            )

        environment=serializer.validated_data.get('environment')
        if environment is not None:
            if environment.project_id != project.id or not environment.is_active:
                return Response(
                    {'detail':'环境不属于当前项目，或环境已停用'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        test_case=serializer.save(
            project=project,
            created_by=request.user
        )

        output_serializer=TestCaseSerializer(
            test_case,
            context={'request':request}
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )


class TestCaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get_object(self,request,project_id,pk):
        project=self.get_project(request,project_id)
        return get_object_or_404(
            project.test_cases,
            pk=pk,
            is_active=True,
        )

    def get(self,request,project_id,pk):
        test_case=self.get_object(request,project_id,pk)
        serializer=TestCaseSerializer(
            test_case,
            context={'request':request}
        )
        return Response(serializer.data)

    def patch(self,request,project_id,pk):
        test_case=self.get_object(request,project_id,pk)

        if not can_edit_project_resource(test_case.project,request.user):
            return Response(
                {'detail':'你没有权限修改该测试用例'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer=TestCaseSerializer(
            test_case,
            data=request.data,
            partial=True,
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)

        endpoint = serializer.validated_data.get('endpoint')
        if endpoint is not None:
            if endpoint.project_id != test_case.project_id or not endpoint.is_active:
                return Response(
                    {'detail': '接口不属于当前项目，或接口已停用'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        environment = serializer.validated_data.get('environment')
        if environment is not None:
            if environment.project_id != test_case.project_id or not environment.is_active:
                return Response(
                    {'detail': '环境不属于当前项目，或环境已停用'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer.save()

        return Response(serializer.data)

    def delete(self,request,project_id,pk):
        test_case=self.get_object(request,project_id,pk)

        if not can_edit_project_resource(test_case.project,request.user):
            return Response(
                {'detail':'你没有权限停用该测试用例'},
                status=status.HTTP_403_FORBIDDEN
            )

        test_case.is_active=False
        test_case.save(update_fields=['is_active','updated_at'])

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )