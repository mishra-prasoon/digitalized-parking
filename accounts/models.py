from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        STAFF = 'staff', 'Staff'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    phone_number = models.CharField(max_length=15, blank=True)

    @property
    def is_staff_member(self):
        return self.role == self.Role.STAFF