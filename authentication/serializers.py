"""
Serializers for handling data serialization and deserialization.
"""
from rest_framework import serializers
from .models import UserAccount


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the User model.
    """

    class Meta:
        """
        Meta class for UserSerializer.
        """

        model = UserAccount
        fields = ["email", "password", "username"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        """
        Create a new user with the validated data.
        """
        user = UserAccount.objects.create_user(**validated_data)
        return user
