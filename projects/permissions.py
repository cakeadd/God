from .models import ProjectMember

def get_project_membership(project,user):
    return ProjectMember.objects.filter(
        project=project,
        user=user
    ).first()

def has_project_role(project,user,roles):
    membership=get_project_membership(project,user)
    if not membership:
        return False

    return membership.role in roles

def is_project_owner(project,user):
    return has_project_role(
        project,
        user,
        [ProjectMember.Role.OWNER]
    )

def can_manage_project(project,user):
    return has_project_role(
        project,
        user,
        [ProjectMember.Role.OWNER,
         ProjectMember.Role.ADMIN]
    )

def can_edit_project_resource(project,user):
    return has_project_role(
        project,
        user,
        [ProjectMember.Role.OWNER,
         ProjectMember.Role.ADMIN,
         ProjectMember.Role.MEMBER]
    )