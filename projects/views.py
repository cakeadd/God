from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404


from .models import ProjectMember,Project
from .serializers import ProjectSerializer
from .permissions import is_project_owner,can_manage_project

class ProjectListCreateView(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request):
        serializer=ProjectSerializer(
            data=request.data,
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)
        project=serializer.save(owner=request.user)

        ProjectMember.objects.create(
            project=project,
            user=request.user,
            role=ProjectMember.Role.OWNER
        )

        output_serializer=ProjectSerializer(
            project,
            context={'request':request}
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )

    def get(self,request):
        projects=Project.objects.filter(
            memberships__user=request.user,
            is_archived=False
        ).distinct()

        serializer=ProjectSerializer(
            projects,
            many=True,
            context={'request':request}
        )

        return Response(
            serializer.data,
        )

class ProjectDetailView(APIView):
    permission_classes=[IsAuthenticated]

    def get_object(self,request,pk):
        return get_object_or_404(
            Project,
            pk=pk,
            memberships__user=request.user,
            is_archived=False
        )

    def get(self,request,pk):
        project=self.get_object(request,pk)
        serializer=ProjectSerializer(
            project,
            context={'request':request}
        )
        return Response(serializer.data)

    def patch(self,request,pk):
        project=self.get_object(request,pk)

        if not can_manage_project(project,request.user):
            return Response(
                {'detail':'只有拥有者和管理员可以修改项目'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer=ProjectSerializer(
            project,
            data=request.data,
            partial=True,
            context={'request':request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    def delete(self,request,pk):
        project=self.get_object(request,pk)

        if not is_project_owner(project,request.user):
            return Response(
                {'detail':'只有拥有者可以归档项目'},
                status=status.HTTP_403_FORBIDDEN,
            )

        project.is_archived=True
        project.save(update_fields=['is_archived','updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)