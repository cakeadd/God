from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Case,IntegerField,Value,When


from .models import ProjectMember,Project
from .serializers import (
    ProjectMemberRoleSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
)
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
                {'detail':'只有拥有者可以修改项目'},
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


class ProjectMemberListView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self,request,project_id):
        # 先限定当前用户可访问的项目，避免通过项目 ID 跨项目读取成员。
        project=get_object_or_404(
            Project,
            pk=project_id,
            memberships__user=request.user,
            is_archived=False,
        )
        members=project.memberships.select_related('user').annotate(
            role_order=Case(
                When(role=ProjectMember.Role.OWNER,then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('role_order','joined_at')

        serializer=ProjectMemberSerializer(members,many=True)
        return Response(serializer.data)


class ProjectMemberDetailView(APIView):
    permission_classes=[IsAuthenticated]

    def patch(self,request,project_id,member_id):
        # 先限定操作者可访问的项目，再校验 owner 权限和目标成员归属。
        project=get_object_or_404(
            Project,
            pk=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

        if not is_project_owner(project,request.user):
            return Response(
                {'detail':'只有拥有者可以修改成员身份'},
                status=status.HTTP_403_FORBIDDEN,
            )

        member=get_object_or_404(
            ProjectMember.objects.select_related('user'),
            pk=member_id,
            project=project,
        )
        serializer=ProjectMemberRoleSerializer(
            member,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output_serializer=ProjectMemberSerializer(member)
        return Response(output_serializer.data)
