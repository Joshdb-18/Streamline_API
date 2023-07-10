"""
Model representing the user authentication
"""

import uuid
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager,
)
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """
    Custom user manager for managing user creation and authentication.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Creates a new user with email and password fields
        """
        if not email:
            raise ValueError("Email field shouldn't be empty")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates a superuser
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        return self.create_user(email, password, **extra_fields)


class UserAccount(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model
    """

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=178, unique=True)
    password = models.CharField(max_length=178)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        """
        Override the __str__ method to return the email as a
        string representation.
        """
        return self.email

    def set_password(self, password):
        """
        Sets and hash the password
        """
        self.password = make_password(password)

    def check_password(self, password):
        """
        Make sure the password matches
        """
        return check_password(password, self.password)

    class Meta:
        """
        Specifies verbose name
        """

        verbose_name = "User Account"
        verbose_name_plural = "User Accounts"
