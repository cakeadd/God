from django.db import transaction
from django.utils import timezone

from projects.models import Project
from .models import Environment


class DefaultEnvironmentError(ValueError):
    pass


def _lock_project(project):
    # 锁定项目行，避免两个并发请求同时切换出多个默认环境。
    Project.objects.select_for_update().get(pk=project.pk)


def _unset_other_defaults(project, exclude_environment_id=None):
    environments = Environment.objects.filter(
        project=project,
        is_active=True,
        is_default=True,
    )
    if exclude_environment_id is not None:
        environments = environments.exclude(pk=exclude_environment_id)

    environments.update(
        is_default=False,
        updated_at=timezone.now(),
    )


@transaction.atomic
def create_environment(serializer, project):
    _lock_project(project)
    has_active_environment = Environment.objects.filter(
        project=project,
        is_active=True,
    ).exists()

    # 项目的第一个启用环境自动成为默认环境，后续环境尊重请求值。
    is_default = (
        serializer.validated_data.get('is_default', False)
        or not has_active_environment
    )

    if is_default:
        # 先取消旧默认，再保存新默认；整个过程处于同一事务中。
        _unset_other_defaults(project)

    return serializer.save(
        project=project,
        is_default=is_default,
    )


@transaction.atomic
def update_environment(serializer, environment):
    _lock_project(environment.project)
    requested_default = serializer.validated_data.get(
        'is_default',
        environment.is_default,
    )
    has_other_active_environment = Environment.objects.filter(
        project=environment.project,
        is_active=True,
    ).exclude(pk=environment.pk).exists()

    # 存在其他启用环境时，项目必须先指定新的默认环境。
    if (
        environment.is_default
        and not requested_default
        and has_other_active_environment
    ):
        raise DefaultEnvironmentError(
            '请先将其他环境设为默认环境'
        )

    if requested_default:
        # 切换默认环境时自动取消同项目的旧默认环境。
        _unset_other_defaults(
            environment.project,
            exclude_environment_id=environment.pk,
        )

    return serializer.save(is_default=requested_default)


@transaction.atomic
def deactivate_environment(environment):
    _lock_project(environment.project)
    has_other_active_environment = Environment.objects.filter(
        project=environment.project,
        is_active=True,
    ).exclude(pk=environment.pk).exists()

    # 禁止直接停用仍承担默认职责的环境，避免其他环境失去默认项。
    if environment.is_default and has_other_active_environment:
        raise DefaultEnvironmentError(
            '请先将其他环境设为默认环境，再停用当前默认环境'
        )

    environment.is_active=False
    environment.save(update_fields=['is_active','updated_at'])
