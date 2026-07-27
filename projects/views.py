from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Case,Exists,IntegerField,OuterRef,Q,Subquery,Value,When


from .models import ProjectMember,Project
from .serializers import (
    ProjectMemberCandidateSerializer,
    ProjectMemberCreateSerializer,
    ProjectMemberRoleSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
)
from .permissions import is_project_owner,can_manage_project
from God.pagination import StandardPageNumberPagination

User=get_user_model()

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

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            pk=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get(self,request,project_id):
        # 先限定当前用户可访问的项目，避免通过项目 ID 跨项目读取成员。
        project=self.get_project(request,project_id)
        members=project.memberships.select_related('user').annotate(
            role_order=Case(
                When(role=ProjectMember.Role.OWNER,then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )

        search=request.query_params.get('search','').strip()
        if search:
            members=members.filter(
                Q(user__username__icontains=search)
                | Q(user__nickname__icontains=search)
            )

        members=members.order_by('role_order','joined_at','id')
        paginator=StandardPageNumberPagination()
        page=paginator.paginate_queryset(members,request,view=self)

        serializer=ProjectMemberSerializer(page,many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self,request,project_id):
        project=self.get_project(request,project_id)
        if not is_project_owner(project,request.user):
            return Response(
                {'detail':'只有拥有者可以增加项目成员'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer=ProjectMemberCreateSerializer(
            data=request.data,
            context={'project':project},
        )
        serializer.is_valid(raise_exception=True)
        member=serializer.save(project=project)

        output_serializer=ProjectMemberSerializer(member)
        return Response(output_serializer.data,status=status.HTTP_201_CREATED)


class ProjectMemberCandidateListView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self,request,project_id):
        project=get_object_or_404(
            Project,
            pk=project_id,
            memberships__user=request.user,
            is_archived=False,
        )
        if not is_project_owner(project,request.user):
            return Response(
                {'detail':'只有拥有者可以查看可添加用户'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 用子查询一次性标记项目成员状态，弹窗可以展示全部用户且无需逐行查询。
        membership=ProjectMember.objects.filter(
            project=project,
            user=OuterRef('pk'),
        )
        users=User.objects.annotate(
            is_project_member=Exists(membership),
            project_role=Subquery(membership.values('role')[:1]),
        ).order_by('username')

        serializer=ProjectMemberCandidateSerializer(users,many=True)
        return Response(serializer.data)


class ProjectMemberDetailView(APIView):
    permission_classes=[IsAuthenticated]

    def get_project(self,request,project_id):
        return get_object_or_404(
            Project,
            pk=project_id,
            memberships__user=request.user,
            is_archived=False,
        )

    def get_member(self,project,member_id):
        return get_object_or_404(
            ProjectMember.objects.select_related('user'),
            pk=member_id,
            project=project,
        )

    def patch(self,request,project_id,member_id):
        # 先限定操作者可访问的项目，再校验 owner 权限和目标成员归属。
        project=self.get_project(request,project_id)

        if not is_project_owner(project,request.user):
            return Response(
                {'detail':'只有拥有者可以修改成员身份'},
                status=status.HTTP_403_FORBIDDEN,
            )

        member=self.get_member(project,member_id)
        serializer=ProjectMemberRoleSerializer(
            member,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        output_serializer=ProjectMemberSerializer(member)
        return Response(output_serializer.data)

    def delete(self,request,project_id,member_id):
        project=self.get_project(request,project_id)

        if not is_project_owner(project,request.user):
            return Response(
                {'detail':'只有拥有者可以移除项目成员'},
                status=status.HTTP_403_FORBIDDEN,
            )

        member=self.get_member(project,member_id)
        # 项目拥有者同时由 Project.owner 和成员角色标识，任一条件命中都禁止移除。
        if member.user_id == project.owner_id or member.role == ProjectMember.Role.OWNER:
            return Response(
                {'detail':'不能移除项目拥有者'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
