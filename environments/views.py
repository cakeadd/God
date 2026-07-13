from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.permissions import can_edit_project_resource
from projects.models import Project
from .serializers import EnvironmentSerializer

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
        )
        serializer=EnvironmentSerializer(
            environments,
            many=True,
            context={'request':request}
        )
        return Response(serializer.data)

    def post(self,request,project_id):
        project=self.get_project(request,project_id)

        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限在该项目下创建环境'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer=EnvironmentSerializer(
            data=request.data,
            context={'request':request}
        )

        serializer.is_valid(raise_exception=True)

        environment=serializer.save(project=project)
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
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self,request,project_id,pk):
        environment=self.get_object(request,project_id,pk)

        if not can_edit_project_resource(environment.project,request.user):
            return Response(
                {'detail':'你没有权限停用该环境'},
                status=status.HTTP_403_FORBIDDEN
            )

        environment.is_active=False
        environment.save(update_fields=['is_active','updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)