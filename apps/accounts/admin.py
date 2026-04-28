from django.contrib import admin
from .models import BiopsychosocialProfile, User

@admin.register(BiopsychosocialProfile)
class BiopsychosocialProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "user", "teacher", "primary_disability_category")
    search_fields = ("user__username", "teacher__username", "student_name")
    list_filter = ("primary_disability_category", "teacher")

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "role", "is_pcd", "is_staff")
    list_filter = ("role", "is_pcd", "is_staff")
    search_fields = ("username",)
