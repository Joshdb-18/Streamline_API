"""
URL configuration module for the auth app.
"""

from rest_framework.authtoken.views import obtain_auth_token
from django.urls import path
from . import views

app_name = "authentication"

urlpatterns = [
    path("api-token-auth/", obtain_auth_token, name="api_token_auth"),
    path("api/v1/register/", views.RegistrationView.as_view(), name="register"),
    path("api/v1/login/", views.LoginView.as_view(), name="login"),
    path("api/v1/logout/", views.LogoutView.as_view(), name="logout"),
    path(
        "api/v1/request-new-email/",
        views.RequestNewLinkView.as_view(),
        name="request-new-link",
    ),
    path("api/v1/verify/", views.verify, name="verify"),
    path("api/v1/reset_password/", views.password_reset, name="password_reset"),
    path(
        "api/v1/reset_confirm/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path(
        "api/v1/delete_user_data/",
        views.DeleteUserDataView.as_view(),
        name="delete-user-data",
    ),
]
