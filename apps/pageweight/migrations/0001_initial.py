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
                ('scan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pageweight_run', to='sites.scan', verbose_name='Scan')),
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
                ('final_url', models.URLField(blank=True, max_length=2000, verbose_name='Final URL')),
                ('measured', models.BooleanField(default=False, help_text='True when Puppeteer completed without error', verbose_name='Measured')),
                ('total_transfer_size', models.BigIntegerField(default=0, help_text='Compressed bytes received over the network', verbose_name='Total transfer size (bytes)')),
                ('total_resource_size', models.BigIntegerField(default=0, help_text='Uncompressed resource size in bytes', verbose_name='Total resource size (bytes)')),
                ('resource_count', models.IntegerField(default=0, verbose_name='Resource count')),
                ('document_transfer', models.BigIntegerField(default=0)),
                ('stylesheet_transfer', models.BigIntegerField(default=0)),
                ('script_transfer', models.BigIntegerField(default=0)),
                ('image_transfer', models.BigIntegerField(default=0)),
                ('font_transfer', models.BigIntegerField(default=0)),
                ('other_transfer', models.BigIntegerField(default=0)),
                ('document_size', models.BigIntegerField(default=0)),
                ('stylesheet_size', models.BigIntegerField(default=0)),
                ('script_size', models.BigIntegerField(default=0)),
                ('image_size', models.BigIntegerField(default=0)),
                ('font_size', models.BigIntegerField(default=0)),
                ('other_size', models.BigIntegerField(default=0)),
                ('error', models.TextField(blank=True, verbose_name='Error')),
                ('page', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pageweight_data', to='sites.page', verbose_name='Page')),
            ],
            options={
                'verbose_name': 'Page Data',
                'verbose_name_plural': 'Page Data',
                'ordering': ['-total_transfer_size'],
                'indexes': [models.Index(fields=['page', 'total_transfer_size'], name='pw_pagedata_page_transfer_idx')],
            },
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('url', models.URLField(max_length=2000, verbose_name='URL')),
                ('resource_type', models.CharField(max_length=20, verbose_name='Type')),
                ('mime_type', models.CharField(blank=True, max_length=100, verbose_name='MIME type')),
                ('transfer_size', models.BigIntegerField(default=0, verbose_name='Transfer size (bytes)')),
                ('resource_size', models.BigIntegerField(default=0, verbose_name='Resource size (bytes)')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='sites.page', verbose_name='Page')),
            ],
            options={
                'verbose_name': 'Resource',
                'verbose_name_plural': 'Resources',
                'indexes': [
                    models.Index(fields=['page', 'resource_type'], name='pw_resource_page_type_idx'),
                    models.Index(fields=['page', 'transfer_size'], name='pw_resource_page_transfer_idx'),
                ],
            },
        ),
    ]
