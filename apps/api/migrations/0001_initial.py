import api.models
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
            name='APIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(help_text='Human-readable name shown in agent-context responses', max_length=100, unique=True, verbose_name='Name')),
                ('key', models.CharField(default=api.models._generate_key, max_length=64, unique=True, verbose_name='Key')),
                ('is_admin', models.BooleanField(default=False, help_text='Admin keys can read feedback and manage other resources', verbose_name='Admin key')),
                ('last_used', models.DateTimeField(blank=True, null=True, verbose_name='Last used')),
                ('site', models.ForeignKey(blank=True, help_text='Limit this key to a single site; leave blank for all sites', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='api_keys', to='sites.site', verbose_name='Site scope')),
            ],
            options={
                'verbose_name': 'API Key',
                'verbose_name_plural': 'API Keys',
            },
        ),
        migrations.CreateModel(
            name='APIFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('endpoint', models.CharField(blank=True, help_text='The endpoint that caused friction', max_length=200, verbose_name='Endpoint')),
                ('message', models.TextField(verbose_name='Message')),
                ('api_key', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedback', to='api.apikey', verbose_name='API Key')),
            ],
            options={
                'verbose_name': 'API Feedback',
                'verbose_name_plural': 'API Feedback',
                'ordering': ['-created'],
            },
        ),
    ]
