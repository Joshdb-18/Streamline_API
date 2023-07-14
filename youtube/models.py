from django.db import models
from authentication.models import User


class OAuthState(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    state = models.CharField(max_length=255)
    credentials = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.state
