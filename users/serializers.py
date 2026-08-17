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


class UserProfileSerializer(serializers.ModelSerializer):
    phone=serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=20,
        validators=[],
    )

    class Meta:
        model=User
        fields=[
            'id',
            'username',
            'email',
            'nickname',
            'phone',
            'avatar',
        ]
        read_only_fields=[
            'id',
            'username',
            'avatar',
        ]

    def validate_phone(self,value):
        # 空手机号统一保存为 NULL，避免唯一字段保存多个空字符串时冲突。
        phone=value.strip() if value else ''
        if not phone:
            return None

        queryset=User.objects.filter(phone=phone)
        if self.instance:
            queryset=queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError('该手机号已被其他用户使用')

        return phone


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        label='原密码',
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        label='新密码',
    )

    def validate(self, attrs):
        user = self.context['request'].user

        if not user.check_password(attrs['old_password']):
            raise serializers.ValidationError({
                'old_password': '原密码错误',
            })

        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({
                'new_password': '新密码不能与原密码相同',
            })

        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user

class RegisterSerializer(serializers.ModelSerializer):
    nickname = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=50,
        label='昵称',
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        label='邮箱',
    )
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=20,
        validators=[],
        label='手机号',
    )
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
            'password',
            'password_confirm',
        ]

    def validate(self,attrs):
        if attrs['password']!=attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm':'两次输入的密码不一样'
            })
        return attrs

    def validate_phone(self, value):
        # 空手机号统一保存为 NULL，避免唯一字段保存多个空字符串时冲突。
        phone = value.strip() if value else ''
        if not phone:
            return None

        if User.objects.filter(phone=phone).exists():
            raise serializers.ValidationError('该手机号已被其他用户使用')

        return phone

    def create(self,validated_data):
        validated_data.pop('password_confirm')
        password=validated_data.pop('password')
        user=User.objects.create_user(
            password=password,
            **validated_data,
        )
        return user
