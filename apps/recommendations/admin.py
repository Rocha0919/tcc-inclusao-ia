from django.contrib import admin
from .models import RecommendationSession, Feedback

@admin.register(RecommendationSession)
class RecommendationSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "created_at")
    search_fields = ("profile__user__username",)
    readonly_fields = ("ai_rationale",)

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "resource", "score")
    list_filter = ("score",)