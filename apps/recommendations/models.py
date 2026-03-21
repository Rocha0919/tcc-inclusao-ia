from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import BiopsychosocialProfile
from apps.catalog.models import ResourceItem

class RecommendationSession(models.Model):
    profile = models.ForeignKey(BiopsychosocialProfile, on_delete=models.CASCADE, related_name='recommendation_sessions')
    ai_rationale = models.TextField()
    context_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sessão {self.id} - {self.profile.user.username} ({self.created_at.date()})"

class RecommendedItem(models.Model):
    session = models.ForeignKey(RecommendationSession, on_delete=models.CASCADE, related_name='recommended_items')
    resource = models.ForeignKey(ResourceItem, on_delete=models.CASCADE)
    ai_justification = models.TextField() # Aqui entra o "porquê" da IA

class Feedback(models.Model):
    session = models.ForeignKey(RecommendationSession, on_delete=models.CASCADE)
    resource = models.ForeignKey(ResourceItem, on_delete=models.CASCADE)
    score = models.IntegerField()
    user_comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('session', 'resource')

    def __str__(self):
        return f"Feedback {self.score} para {self.resource.name}"