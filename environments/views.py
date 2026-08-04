from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.permissions import can_edit_project_resource
from projects.models import Project
from God.pagination import StandardPageNumberPagination
from .serializers import EnvironmentSerializer
from .services import (
    DefaultEnvironmentError,
    create_environment,
    deactivate_environment,
    update_environment,
)

class EnvironmentListCreateView(APIView):
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
        environments=project.environments.filter(
            is_active=True
        ).select_related('project')
        search=request.query_params.get('search','').strip()
        if search:
            environments=environments.filter(name__icontains=search)
        # 先完成项目和启用状态过滤，再固定排序后分页，避免翻页时记录重复或遗漏。
        environments=environments.order_by('-is_default','-updated_at','-id')
        paginator=StandardPageNumberPagination()
        page=paginator.paginate_queryset(environments,request,view=self)
        serializer=EnvironmentSerializer(
            page,
            many=True,
            context={'request':request}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self,request,project_id):
        project=self.get_project(request,project_id)

        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限在该项目下创建环境'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer=EnvironmentSerializer(
            data=request.data,
            context={'request':request, 'project':project}
        )

        serializer.is_valid(raise_exception=True)

        environment=create_environment(serializer,project)
        output_serializer=EnvironmentSerializer(
            environment,
            context={'request':request}
        )
        return  Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )

class EnvironmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False
        )

    def get_object(self,request,project_id,pk):
        project=self.get_project(request,project_id)
        return get_object_or_404(
            project.environments,
            pk=pk,
            is_active=True
        )

    def get(self,request,project_id,pk):
        environment=self.get_object(request,project_id,pk)
        serializer=EnvironmentSerializer(
            environment,
            context={'request':request}
        )
        return Response(serializer.data)

    def patch(self,request,project_id,pk):
        environment=self.get_object(request,project_id,pk)

        if not can_edit_project_resource(environment.project,request.user):
            return Response(
                {'detail':'你没有权限修改该环境'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer=EnvironmentSerializer(
            environment,
            data=request.data,
            partial=True,
            context={'request':request, 'project':environment.project}
        )
        serializer.is_valid(raise_exception=True)
        try:
            update_environment(serializer,environment)
        except DefaultEnvironmentError as exc:
            return Response(
                {'detail':str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(serializer.data)

    def delete(self,request,project_id,pk):
        environment=self.get_object(request,project_id,pk)

        if not can_edit_project_resource(environment.project,request.user):
            return Response(
                {'detail':'你没有权限停用该环境'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            deactivate_environment(environment)
        except DefaultEnvironmentError as exc:
            return Response(
                {'detail':str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
