from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_role_and_teacher_profiles'),
    ]

    operations = [
        migrations.AddField(
            model_name='biopsychosocialprofile',
            name='last_generated_session_id',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='biopsychosocialprofile',
            name='last_generation_error',
            field=models.TextField(blank=True, default=''),
        ),
    ]
