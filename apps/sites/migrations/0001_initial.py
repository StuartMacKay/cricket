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
                ('crontab', models.CharField(blank=True, help_text='Crontab entry which defines the time a Scan will be taken', max_length=100, validators=[sites.models.site.validate_crontab], verbose_name='Crontab')),
                ('snapped', models.DateTimeField(blank=True, help_text='The date and time the last Scan was taken', null=True, verbose_name='Snapped')),
                ('enabled', models.BooleanField(help_text='Is the site active', verbose_name='Enabled')),
                ('enable_lighthouse', models.BooleanField(default=True, help_text='Run Lighthouse audits when this site is scanned', verbose_name='Enable Lighthouse')),
                ('enable_headers', models.BooleanField(default=True, help_text='Run HTTP header audits when this site is scanned', verbose_name='Enable headers')),
                ('enable_pageweight', models.BooleanField(default=True, help_text='Run page weight measurements when this site is scanned', verbose_name='Enable page weight')),
                ('enable_toolbar', models.BooleanField(default=False, help_text='Run Django Debug Toolbar data collection when this site is scanned', verbose_name='Enable toolbar')),
            ],
            options={
                'verbose_name': 'Site',
                'verbose_name_plural': 'Sites',
            },
        ),
        migrations.CreateModel(
            name='Scan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('platform', models.CharField(max_length=10, verbose_name='Platform')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('complete', 'Complete'), ('failed', 'Failed')], db_index=True, default='pending', max_length=10, verbose_name='Status')),
                ('webhook_url', models.URLField(blank=True, help_text='Optional URL to POST to when the scan completes', verbose_name='Webhook URL')),
                ('environment', models.CharField(blank=True, choices=[('local', 'Local'), ('staging', 'Staging'), ('production', 'Production')], help_text='The environment this scan was collected from', max_length=20, verbose_name='Environment')),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scans', to='sites.site', verbose_name='Site')),
            ],
            options={
                'verbose_name': 'Scan',
                'verbose_name_plural': 'Scans',
                'ordering': ['-created'],
            },
        ),
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('url', models.URLField(max_length=2000, verbose_name='URL')),
                ('scan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='sites.scan', verbose_name='Scan')),
            ],
            options={
                'verbose_name': 'Page',
                'verbose_name_plural': 'Pages',
                'unique_together': {('scan', 'url')},
            },
        ),
        migrations.AddField(
            model_name='site',
            name='current_scan',
            field=models.ForeignKey(blank=True, help_text='The most recently completed Scan for this site', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='sites.scan', verbose_name='Current scan'),
        ),
    ]
