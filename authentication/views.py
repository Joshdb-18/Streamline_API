"""
Views module for handling API endpoints related to accounts.
"""

import logging
import time
import uuid

from datetime import timedelta, datetime
from urllib.parse import urlparse, unquote
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from bs4 import BeautifulSoup
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

import pytz

from .models import UserAccount
from .serializers import UserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


class RegistrationView(APIView):
    """
    API view for user registration.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """
        Handle POST request for user registration.
        """
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            try:
                user = serializer.save()
                token = uuid.uuid4()
                user.token = token
                user.save()
                site_url = request.headers.get("X-Requested-From")

                email_context = {
                    "user": user,
                    "site_url": site_url,
                    "token": token,
                }
                email_html = render_to_string("user/confirm_email.html", email_context)
                soup = BeautifulSoup(email_html, "html.parser")
                subject = soup.title.string.strip()

                message_elements = soup.find_all("td", class_="content-block")
                message_parts = [
                    element.get_text().strip() for element in message_elements
                ]
                message = "\n".join(message_parts)
                sender_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [email]
                success_message = (
                    "Registration successful. "
                    "Verify your account with the email sent to you."
                )

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=sender_email,
                    recipient_list=recipient_list,
                    html_message=email_html,
                    fail_silently=False,
                )
                response_data = {
                    "message": success_message,
                    "success": True,
                    "token": token,
                    "data": serializer.data,
                }
                return Response(response_data, status=status.HTTP_200_OK)

            # pylint: disable=broad-exception-caught
            except Exception as exception:
                try:
                    user = UserAccount.objects.get(email=email)
                    user.delete()
                # pylint: disable=E1101
                except UserAccount.DoesNotExist:
                    pass

                logger.error(str(exception))
                return Response(
                    {
                        "success": False,
                        "message": "An error occurred during registration.",
                    }
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequestNewLinkView(APIView):
    """
    API view for requesting a new email verification link.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """
        Handle POST request for requesting a new email verification link.
        """
        email = request.data.get("email")
        try:
            user = UserAccount.objects.get(email=email)
            if user.is_active:
                token = uuid.uuid4()
                user.token = token
                user.save()

                site_url = request.headers.get("X-Requested-From")
                email_context = {
                    "user": user,
                    "site_url": site_url,
                    "token": token,
                }
                email_html = render_to_string("user/confirm_email.html", email_context)
                soup = BeautifulSoup(email_html, "html.parser")
                subject = soup.title.string.strip()

                message_elements = soup.find_all("td", class_="content-block")
                message_parts = [
                    element.get_text().strip() for element in message_elements
                ]
                message = "\n".join(message_parts)
                sender_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = [email]
                success_message = (
                    "New email verification link has been sent. "
                    "Please check your email."
                )
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=sender_email,
                    recipient_list=recipient_list,
                    html_message=email_html,
                    fail_silently=False,
                )
                response_data = {
                    "message": success_message,
                    "success": True,
                    "token": token,
                }
                return Response(response_data, status=status.HTTP_200_OK)
            return Response({"success": False, "message": "User is not active."})
        # pylint: disable=E1101
        except UserAccount.DoesNotExist:
            return Response({"success": False, "message": "User does not exist."})


class LoginView(APIView):
    """
    API view for user login.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Handle POST request for user login.
        """
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(request, email=email, password=password)
        if user:
            if user.is_verified:
                login(request, user)
                # pylint: disable=E1101
                token, created = Token.objects.get_or_create(user=user)
                return Response(
                    {
                        "user": user.id,
                        "success": True,
                        "message": "Valid credentials",
                        "token": token.key,
                    },
                    status=status.HTTP_200_OK,
                )
            return Response({"success": False, "message": "User is not verified yet"})
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


class LogoutView(APIView):
    """
    API view for user logout.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Handle POST request for user logout.
        """
        request.user.auth_token.delete()
        logout(request)
        return Response({"message": None}, status=status.HTTP_204_NO_CONTENT)


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def verify(request):
    """
    View function for verifying user account.
    """
    token = request.data.get("token")

    try:
        user = UserAccount.objects.get(token=token)
    # pylint: disable=E1101
    except UserAccount.DoesNotExist:
        user = None

    if user is not None and not user.is_verified:
        if timezone.now() <= user.date_joined + timedelta(days=3):
            user.is_verified = True
            user.save()
            data = {"success": True, "message": "Your account is verified"}
        else:
            user.delete()
            data = {
                "success": False,
                "message": "Activation link has expired, Sign up again",
            }
    elif user is not None and user.is_verified:
        data = {"success": False, "message": "Your account is already active"}
    else:
        data = {"success": False, "message": "Invalid activation link"}

    return Response(data)


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset(request):
    """
    View function for requesting password reset.
    """
    email = request.data.get("email")
    try:
        user = UserAccount.objects.get(email=email)
    # pylint: disable=E1101
    except UserAccount.DoesNotExist:
        user = None

    if user is not None:
        timestamp = int(time.time())
        token = default_token_generator.make_token(user) + ":" + str(timestamp)
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))

        domain = request.headers.get("X-Requested-From")
        email_html = render_to_string(
            "user/password_reset_email.html",
            {
                "protocol": "https",
                "domain": domain,
                "uidb64": uidb64,
                "token": token,
            },
        )
        soup = BeautifulSoup(email_html, "html.parser")
        subject = soup.title.string.strip()
        message = soup.find_all("p")[0].get_text()
        sender_email = settings.DEFAULT_FROM_EMAIL
        to_email = [email]
        send_mail(
            subject=subject,
            message=message,
            from_email=sender_email,
            html_message=email_html,
            recipient_list=to_email,
            fail_silently=False,
        )
        success_message = "Password reset link has been sent to your email."
        data = {
            "success": True,
            "message": success_message,
            "uidb64": uidb64,
            "token": token,
        }
        return Response(data)
    error_message = "There is no user with that email."
    data = {
        "success": False,
        "message": error_message,
    }
    return Response(data)


@csrf_protect
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    View function for confirming password reset.
    """
    uidb64 = request.data.get("uidb64")
    token = request.data.get("token")

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = UserAccount.objects.get(pk=uid)
    # pylint: disable=E1101
    except (TypeError, ValueError, OverflowError, UserAccount.DoesNotExist):
        user = None

    if user is not None:
        token_parts = token.split(":")
        if len(token_parts) != 2:
            return Response(
                {"error": "Invalid password reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reset_token, timestamp = token_parts
        if default_token_generator.check_token(user, reset_token):
            timestamp = int(timestamp)
            time_threshold = datetime.now(pytz.utc) - timedelta(minutes=15)
            if datetime.fromtimestamp(timestamp, pytz.utc) >= time_threshold:
                password1 = request.data.get("password1")
                password2 = request.data.get("password2")

                if password1 != password2:
                    return Response(
                        {"error": "Passwords do not match."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                user.set_password(password1)
                user.save()
                user = authenticate(username=user.username, password=password1)
                return Response(
                    {"success": "Password reset successful."},
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"error": "Password reset link has expired. Request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"error": "Password link no longer valid."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"error": "Invalid password reset link."},
        status=status.HTTP_400_BAD_REQUEST,
    )


class DeleteUserDataView(APIView):
    """
    API view for deleting user data.
    """

    def delete(self, request):
        """
        Handle DELETE request for deleting user data.
        """
        user_id = request.data.get("user_id")
        user = get_object_or_404(UserAccount, id=user_id)

        # Check if the user has permission to delete the data
        if not request.user.is_superuser and request.user != user:
            return Response(
                {"error": "You do not have permission to delete this user data."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Logically delete user data
        user.is_deleted = True
        user.is_active = False  # Deactivate the user account
        user.save()

        return Response(
            {"message": "User data deleted successfully."},
            status=status.HTTP_200_OK,
        )
