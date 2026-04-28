from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    field_order = ['username', 'role', 'password1', 'password2']

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        label='Tipo de conta',
        help_text='Escolha professor para gerenciar alunos ou aluno/usuário comum para usar o próprio perfil.'
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'role')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']
        user.is_pcd = user.role == User.ROLE_STUDENT
        if commit:
            user.save()
        return user
