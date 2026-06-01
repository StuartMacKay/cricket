import django.db.models.deletion
import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Run',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('complete', 'Complete'), ('failed', 'Failed')], db_index=True, default='pending', max_length=10, verbose_name='Status')),
                ('page_count', models.IntegerField(blank=True, null=True, verbose_name='Page count')),
                ('scan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='headers_run', to='sites.scan', verbose_name='Scan')),
            ],
            options={
                'verbose_name': 'Run',
                'verbose_name_plural': 'Runs',
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='PageData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('final_url', models.URLField(blank=True, help_text='URL after following redirects; same as url if no redirect', max_length=2000, verbose_name='Final URL')),
                ('status_code', models.IntegerField(blank=True, null=True, verbose_name='Status code')),
                ('redirect_count', models.IntegerField(default=0, verbose_name='Redirect count')),
                ('headers', models.JSONField(default=dict, help_text='Response headers from the final URL, keys lowercased', verbose_name='Headers')),
                ('error', models.TextField(blank=True, help_text='Network or timeout error, if any', verbose_name='Error')),
                ('page', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='headers_data', to='sites.page', verbose_name='Page')),
            ],
            options={
                'verbose_name': 'Page Data',
                'verbose_name_plural': 'Page Data',
            },
        ),
    ]
