from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_biopsychosocialprofile_generation_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='biopsychosocialprofile',
            name='generation_cancel_requested',
            field=models.BooleanField(default=False),
        ),
    ]
