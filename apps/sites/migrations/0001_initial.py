import django.db.models.deletion
import django_extensions.db.fields
import sites.models.site
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(help_text='The name of the site', max_length=100, verbose_name='Name')),
                ('slug', models.SlugField(help_text='The slug uniquely identifying the Site', max_length=100, unique=True, verbose_name='Slug')),
                ('url', models.URLField(help_text="The site's homepage", verbose_name='URL')),
                ('description', models.TextField(blank=True, help_text='A description of the Site', verbose_name='Description')),
                ('sitemap_url', models.URLField(blank=True, help_text="The URL to the site's sitemap", verbose_name='Sitemap URL')),
                ('sitemap_file', models.FileField(blank=True, help_text='A file containing the sitemap for the Site', null=True, upload_to=sites.models.site.sitemap_path, verbose_name='Sitemap file')),
                ('platform', models.CharField(choices=[('mobile', 'Mobile'), ('desktop', 'Desktop')], default='mobile', help_text='The device form factor Lighthouse uses when auditing this site', max_length=10, verbose_name='Platform')),
                ('extra_config', models.JSONField(blank=True, default=dict, help_text='Additional Lighthouse config options (JSON). The Platform field above is always applied automatically; use this only for advanced overrides.', verbose_name='Extra config')),
                ('crontab', models.CharField(blank=True, help_text='Crontab entry which defines the time a Snapshot will be taken', max_length=100, validators=[sites.models.site.validate_crontab], verbose_name='Crontab')),
                ('snapped', models.DateTimeField(blank=True, help_text='The date and time the last Snapshot was taken', null=True, verbose_name='Snapped')),
                ('enabled', models.BooleanField(help_text='Is the site active', verbose_name='Enabled')),
            ],
            options={
                'verbose_name': 'Site',
                'verbose_name_plural': 'Sites',
            },
        ),
        migrations.CreateModel(
            name='Snapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('platform', models.CharField(max_length=10, verbose_name='Platform')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('complete', 'Complete'), ('failed', 'Failed')], db_index=True, default='pending', max_length=10, verbose_name='Status')),
                ('webhook_url', models.URLField(blank=True, help_text='Optional URL to POST to when the snapshot completes', verbose_name='Webhook URL')),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='snapshots', to='sites.site', verbose_name='Site')),
            ],
            options={
                'verbose_name': 'Snapshot',
                'verbose_name_plural': 'Snapshots',
                'ordering': ['-created'],
            },
        ),
        migrations.AddField(
            model_name='site',
            name='current_snapshot',
            field=models.ForeignKey(blank=True, help_text='The most recently completed Snapshot for this site', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='sites.snapshot', verbose_name='Current snapshot'),
        ),
    ]
