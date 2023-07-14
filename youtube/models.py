from django.db import models
from authentication.models import UserAccount


class OAuthState(models.Model):
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE)
    state = models.CharField(max_length=255)
    credentials = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.state
