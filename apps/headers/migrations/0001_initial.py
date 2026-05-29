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
            name='Snapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('complete', 'Complete'), ('failed', 'Failed')], db_index=True, default='pending', max_length=10, verbose_name='Status')),
                ('page_count', models.IntegerField(blank=True, null=True, verbose_name='Page count')),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='header_snapshots', to='sites.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Snapshot',
                'verbose_name_plural': 'Snapshots',
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
                ('final_url', models.URLField(blank=True, help_text='URL after following redirects; same as url if no redirect', max_length=2000, verbose_name='Final URL')),
                ('status_code', models.IntegerField(blank=True, null=True, verbose_name='Status code')),
                ('redirect_count', models.IntegerField(default=0, verbose_name='Redirect count')),
                ('headers', models.JSONField(default=dict, help_text='Response headers from the final URL, keys lowercased', verbose_name='Headers')),
                ('error', models.TextField(blank=True, help_text='Network or timeout error, if any', verbose_name='Error')),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='headers.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Page',
                'verbose_name_plural': 'Pages',
                'ordering': ['url'],
                'indexes': [models.Index(fields=['snapshot', 'url'], name='headers_pag_snapsho_ee8d8f_idx')],
            },
        ),
    ]
