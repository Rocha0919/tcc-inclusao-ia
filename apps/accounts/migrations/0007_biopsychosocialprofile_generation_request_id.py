from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_fix_legacy_generation_error_column'),
    ]

    operations = [
        migrations.AddField(
            model_name='biopsychosocialprofile',
            name='generation_request_id',
            field=models.PositiveBigIntegerField(default=0),
        ),
    ]
