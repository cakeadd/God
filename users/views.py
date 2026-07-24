from rest_framework.views import APIView
from rest_framework.response import Response
# from django.contrib.auth import get_user_model
from rest_framework.permissions import IsAuthenticated,AllowAny
from .serializers import RegisterSerializer,UserProfileSerializer,UserSerializer
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

# User = get_user_model()

class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    def get(self,request):
        return Response({
            'status': 'OK',
            'message': 'API is running',
        })

# class UserListView(APIView):
#     def get(self,request):
#         users=User.objects.all()
#         serializer=UserSerializer(users,many=True)
#         return Response(serializer.data)

class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self,request):
        serializer=UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self,request):
        serializer=UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    def post(self,request):
        serializer=RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user=serializer.save()

        refresh=RefreshToken.for_user(user)

        return Response({
            'user':UserSerializer(user).data,
            'refresh':str(refresh),
            'access':str(refresh.access_token),
        },
            status=status.HTTP_201_CREATED,
        )
