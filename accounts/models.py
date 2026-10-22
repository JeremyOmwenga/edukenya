from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        email = self.normalize_email(email).lower() if email else None
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        """Platform super admin. Only meaningful in the public schema."""
        extra.update(is_staff=True, is_superuser=True, role=User.Role.PLATFORM_ADMIN)
        if not password:
            raise ValueError("Super admins must have a password.")
        return self._create(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    One table per schema:
      public schema  -> platform super admins only
      school schemas -> that school's admins, teachers, parents and students

    Because each school has its own table, an account from one school simply
    does not exist in another school's database schema.

    Adults sign in with email. Students will sign in with admission number +
    PIN (added with the student flow), so email is optional at the DB level.
    """

    class Role(models.TextChoices):
        PLATFORM_ADMIN = "platform_admin", "Platform admin"
        SCHOOL_ADMIN = "school_admin", "School admin"
        TEACHER = "teacher", "Teacher"
        PARENT = "parent", "Parent"
        STUDENT = "student", "Student"

    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            # Every non-student account must have an email to sign in with.
            models.CheckConstraint(
                condition=Q(role="student") | Q(email__isnull=False),
                name="adult_accounts_have_email",
            ),
        ]

    def __str__(self):
        return self.email or f"user-{self.pk}"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
