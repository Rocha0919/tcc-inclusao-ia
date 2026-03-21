from django.contrib import admin
from .models import BiopsychosocialProfile, User

@admin.register(BiopsychosocialProfile)
class BiopsychosocialProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "primary_disability_category")
    search_fields = ("user__username",)

admin.site.register(User)