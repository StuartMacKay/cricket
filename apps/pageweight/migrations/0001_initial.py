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
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weight_snapshots', to='sites.snapshot', verbose_name='Snapshot')),
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
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='pageweight.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Page',
                'verbose_name_plural': 'Pages',
                'ordering': ['-total_transfer_size'],
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
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resources', to='pageweight.page', verbose_name='Page')),
            ],
            options={
                'verbose_name': 'Resource',
                'verbose_name_plural': 'Resources',
            },
        ),
        migrations.AddIndex(
            model_name='page',
            index=models.Index(fields=['snapshot', 'url'], name='pageweight__snapsho_89d705_idx'),
        ),
        migrations.AddIndex(
            model_name='page',
            index=models.Index(fields=['snapshot', 'total_transfer_size'], name='pageweight__snapsho_a07ea1_idx'),
        ),
        migrations.AddIndex(
            model_name='resource',
            index=models.Index(fields=['page', 'resource_type'], name='pageweight__page_id_cf752b_idx'),
        ),
        migrations.AddIndex(
            model_name='resource',
            index=models.Index(fields=['page', 'transfer_size'], name='pageweight__page_id_ba5eb9_idx'),
        ),
    ]
