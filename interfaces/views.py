from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.models import Project
from projects.permissions import can_edit_project_resource
from .serializers import ApiEndpointSerializer

class ApiEndpointListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            id=project_id,
            memberships__user=request.user,
            is_archived=False
        )

    def post(self,request,project_id):
        project=self.get_project(request,project_id)

        if not can_edit_project_resource(project,request.user):
            return Response(
                {'detail':'你没有权限在该项目下创建接口'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer=ApiEndpointSerializer(
            data=request.data,
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)

        method = serializer.validated_data['method']
        path = serializer.validated_data['path']

        if project.api_endpoints.filter(method=method, path=path).exists():
            return Response(
                {'detail': '该项目下已存在相同请求方法和路径的接口'},
                status=status.HTTP_400_BAD_REQUEST,
            )


        endpoint=serializer.save(
            project=project,
            created_by=request.user
        )
        output_serializer=ApiEndpointSerializer(
            endpoint,
            context={'request':request}
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )

    def get(self,request,project_id):
        project=self.get_project(request,project_id)

        endpoints=project.api_endpoints.filter(
            is_active=True,
        )
        serializer=ApiEndpointSerializer(
            endpoints,
            many=True,
            context={'request':request}
        )

        return Response(
            serializer.data
        )


class ApiEndpointDetailView(APIView):
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
            project.api_endpoints,
            pk=pk,
            is_active=True,
        )

    def get(self, request, project_id, pk):
        endpoint = self.get_object(request, project_id, pk)

        serializer = ApiEndpointSerializer(
            endpoint,
            context={'request': request},
        )

        return Response(serializer.data)

    def patch(self,request,project_id,pk):
        endpoint=self.get_object(request,project_id,pk)

        if not can_edit_project_resource(endpoint.project,request.user):
            return Response(
                {'detail':'你没有权限修改该接口'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer=ApiEndpointSerializer(
            endpoint,
            data=request.data,
            partial=True,
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self,request,project_id,pk):
        endpoint=self.get_object(request,project_id,pk)
        if not can_edit_project_resource(endpoint.project,request.user):
            return Response(
                {'detail':'你没有权限停用该接口'},
                status=status.HTTP_403_FORBIDDEN
            )
        endpoint.is_active=False
        endpoint.save(update_fields=['is_active','updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)