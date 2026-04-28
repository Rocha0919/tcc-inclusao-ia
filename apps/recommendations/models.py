from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import BiopsychosocialProfile

class RecommendationSession(models.Model):
    profile = models.ForeignKey(BiopsychosocialProfile, on_delete=models.CASCADE)
    justificativa_geral = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sessão de {self.profile.user.username} - {self.created_at.strftime('%d/%m/%Y')}"

class GeneratedTechnology(models.Model):
    session = models.ForeignKey(RecommendationSession, on_delete=models.CASCADE, related_name='technologies')
    name = models.CharField(max_length=255)
    what_is_it = models.TextField()
    purpose = models.TextField()
    justification = models.TextField() # Personalizada para o usuário
    video_search_term = models.CharField(max_length=255)
    ai_model = models.CharField(max_length=50, default='llama3')
    
    # Removi score e user_comment daqui para evitar duplicidade com a tabela Feedback

    def __str__(self):
        return self.name

class Feedback(models.Model):
    # Relacionamos com a sessão e com a tecnologia gerada
    session = models.ForeignKey(RecommendationSession, on_delete=models.CASCADE, related_name='feedbacks')
    resource = models.ForeignKey(GeneratedTechnology, on_delete=models.CASCADE, related_name='item_feedbacks')
    
    # Adicionei validadores para garantir que a nota seja sempre entre 1 e 5
    score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    user_comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Garante que o usuário só avalie cada item daquela sessão uma única vez
        unique_together = ('session', 'resource')

    def __str__(self):
        return f"Nota {self.score} para {self.resource.name} ({self.session.profile.user.username})"


def _recommendation_session_str(self):
    return f"Sessão de {self.profile.display_name} - {self.created_at.strftime('%d/%m/%Y')}"


def _feedback_str(self):
    return f"Nota {self.score} para {self.resource.name} ({self.session.profile.display_name})"


RecommendationSession.__str__ = _recommendation_session_str
Feedback.__str__ = _feedback_str
