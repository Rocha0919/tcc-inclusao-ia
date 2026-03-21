from django.db import models

class ResourceItem(models.Model):
    CATEGORY_CHOICES = [
        ('TA', 'Tecnologia Assistiva'),
        ('MDA', 'Material Didático Acessível'),
    ]
    
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=3, choices=CATEGORY_CHOICES)
    
    description = models.TextField(blank=True) 
    
    technical_requirements = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Ex: {'SO': 'Windows', 'RAM': '4GB'}"
    )
    metadata_tags = models.JSONField(
        default=list, 
        blank=True,
        help_text="Armazena os perfis atendidos (ex: ['TEA', 'TDAH'])"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'category'], 
                name='unique_resource_per_category'
            )
        ]

    def __str__(self):
        return f"[{self.category}] {self.name}"