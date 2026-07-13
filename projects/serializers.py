from rest_framework import serializers
from .models import Project,ProjectMember

class ProjectSerializer(serializers.ModelSerializer):
    owner_username=serializers.CharField(source='owner.username',read_only=True)
    my_role=serializers.SerializerMethodField()

    class Meta:
        model=Project
        fields=[
            'id',
            'name',
            'description',
            'owner',
            'owner_username',
            'my_role',
            'is_archived',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'owner',
            'owner_username',
            'my_role',
            'is_archived',
            'created_at',
            'updated_at',
        ]

    def get_my_role(self,obj):
        request=self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        membership=ProjectMember.objects.filter(
            project=obj,
            user=request.user,
        ).first()

        if not membership:
            return None

        return membership.role