from django.contrib.auth import get_user_model
from rest_framework import serializers


User=get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'nickname',
            'phone',
            'avatar',
        ]
        read_only_fields = [
            'id',
            'username',
        ]

class RegisterSerializer(serializers.ModelSerializer):
    password=serializers.CharField(
        write_only=True,
        min_length=8,
        label='密码',
    )
    password_confirm=serializers.CharField(
        write_only=True,
        min_length=8,
        label='确认密码'
    )
    class Meta:
        model=User
        fields=[
            "username",
            "email",
            "nickname",
            'phone',
            'avatar',
            'password',
            'password_confirm',
        ]

    def validate(self,attrs):
        if attrs['password']!=attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm':'两次输入的密码不一样'
            })
        return attrs

    def create(self,validated_data):
        validated_data.pop('password_confirm')
        password=validated_data.pop('password')
        user=User.objects.create_user(
            password=password,
            **validated_data,
        )
        return user