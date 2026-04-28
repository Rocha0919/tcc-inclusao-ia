from django.db import migrations


def sync_legacy_generation_error_column(apps, schema_editor):
    profile_model = apps.get_model('accounts', 'BiopsychosocialProfile')
    table_name = profile_model._meta.db_table
    quote_name = schema_editor.quote_name

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

        has_legacy_column = 'generation_error' in columns
        has_current_column = 'last_generation_error' in columns

        if has_legacy_column and has_current_column:
            cursor.execute(
                f"""
                UPDATE {quote_name(table_name)}
                SET {quote_name('last_generation_error')} = COALESCE(
                    NULLIF({quote_name('last_generation_error')}, ''),
                    {quote_name('generation_error')},
                    ''
                )
                """
            )
            cursor.execute(
                f"ALTER TABLE {quote_name(table_name)} DROP COLUMN {quote_name('generation_error')}"
            )
            has_legacy_column = False

        if has_legacy_column and not has_current_column:
            cursor.execute(
                f"""
                ALTER TABLE {quote_name(table_name)}
                RENAME COLUMN {quote_name('generation_error')}
                TO {quote_name('last_generation_error')}
                """
            )
            has_current_column = True

        if has_current_column:
            cursor.execute(
                f"""
                UPDATE {quote_name(table_name)}
                SET {quote_name('last_generation_error')} = ''
                WHERE {quote_name('last_generation_error')} IS NULL
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {quote_name(table_name)}
                ALTER COLUMN {quote_name('last_generation_error')} SET DEFAULT ''
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {quote_name(table_name)}
                ALTER COLUMN {quote_name('last_generation_error')} SET NOT NULL
                """
            )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_biopsychosocialprofile_generation_cancel_requested'),
    ]

    operations = [
        migrations.RunPython(
            sync_legacy_generation_error_column,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
