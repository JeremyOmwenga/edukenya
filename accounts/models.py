import secrets
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):

    def create_user(self, email, name, password, role):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user  = self.model(email=email, name=name, role=role)
        user.set_password(password)   # hashes with PBKDF2 automatically
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password, role='admin'):
        user = self.create_user(email, name, password, role)
        user.is_staff     = True
        user.is_superuser = True
        user.is_active    = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):

    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('admin',   'School Administrator'),
    ]

    email             = models.EmailField(unique=True)
    name              = models.CharField(max_length=150)
    role              = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_email_verified = models.BooleanField(default=False)
    is_active         = models.BooleanField(default=False)  # False until email confirmed
    is_staff          = models.BooleanField(default=False)
    date_joined       = models.DateTimeField(auto_now_add=True)

    objects  = UserManager()

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email


class EmailVerificationToken(models.Model):

    user       = models.OneToOneField(User, on_delete=models.CASCADE,
                                      related_name='verification_token')
    token      = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'email_verification_tokens'

    @staticmethod
    def generate():
        """Returns a cryptographically secure random URL-safe string."""
        return secrets.token_urlsafe(32)
