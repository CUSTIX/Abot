from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers


class SignUpSerializer(serializers.Serializer):
    username = serializers.RegexField(r"^[A-Za-z0-9_.-]{3,30}$", max_length=30)
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    first_name = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate_username(self, value):
        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)


class MeSerializer(serializers.ModelSerializer):
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "first_name", "is_demo"]

    def get_is_demo(self, user) -> bool:
        return user.username == settings.DEMO_USERNAME
