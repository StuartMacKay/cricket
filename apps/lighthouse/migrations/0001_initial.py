import django.db.models.deletion
import django_extensions.db.fields
import lighthouse.models.page
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditDefinition',
            fields=[
                ('audit_id', models.CharField(help_text="The Lighthouse audit identifier, e.g. 'first-contentful-paint'", max_length=100, primary_key=True, serialize=False, verbose_name='Audit ID')),
                ('category_id', models.CharField(db_index=True, help_text='The primary category this audit belongs to', max_length=50, verbose_name='Category ID')),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('weight', models.FloatField(default=0, help_text='Weight of this audit within its category (0 for binary audits)', verbose_name='Weight')),
            ],
            options={
                'verbose_name': 'Audit Definition',
                'verbose_name_plural': 'Audit Definitions',
                'ordering': ['category_id', 'audit_id'],
            },
        ),
        migrations.CreateModel(
            name='Snapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('complete', 'Complete'), ('failed', 'Failed')], db_index=True, default='pending', max_length=10, verbose_name='Status')),
                ('page_count', models.IntegerField(blank=True, help_text='Total number of pages audited; populated when complete', null=True, verbose_name='Page count')),
                ('config_file', models.CharField(blank=True, help_text='Temporary path to the Lighthouse config file', max_length=500, verbose_name='Config file')),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lighthouse_snapshots', to='sites.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Snapshot',
                'verbose_name_plural': 'Snapshots',
            },
        ),
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('url', models.URLField(help_text='The URL of the page from the Site', verbose_name='URL')),
                ('report', models.FileField(blank=True, help_text='The raw Lighthouse JSON report; pruned after 90 days', null=True, upload_to=lighthouse.models.page.audit_report_path, verbose_name='Report')),
                ('html_report', models.FileField(blank=True, help_text="The self-contained Lighthouse HTML report, identical to Chrome's Lighthouse panel output", null=True, upload_to=lighthouse.models.page.audit_report_path, verbose_name='HTML Report')),
                ('audited', models.BooleanField(help_text='The page was audited successfully, with no errors or warnings reported', verbose_name='Audited')),
                ('snapshot', models.ForeignKey(help_text='The Snapshot that this Page belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='lighthouse.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Page',
                'verbose_name_plural': 'Pages',
            },
        ),
        migrations.CreateModel(
            name='PageAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField(blank=True, help_text='0–100 score, or null when not applicable', null=True, verbose_name='Score')),
                ('rating', models.CharField(blank=True, choices=[('poor', 'Poor'), ('needs-improvement', 'Needs Improvement'), ('good', 'Good')], max_length=20, null=True, verbose_name='Rating')),
                ('value', models.FloatField(blank=True, help_text='Numeric value (e.g. milliseconds for timing audits)', null=True, verbose_name='Value')),
                ('units', models.CharField(blank=True, max_length=50, verbose_name='Units')),
                ('details', models.JSONField(blank=True, help_text='Failing items from the audit details section', null=True, verbose_name='Details')),
                ('audit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='page_audits', to='lighthouse.auditdefinition', verbose_name='Audit')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audits', to='lighthouse.page', verbose_name='Page')),
            ],
            options={
                'verbose_name': 'Page Audit',
                'verbose_name_plural': 'Page Audits',
                'indexes': [models.Index(fields=['audit', 'rating'], name='lighthouse__audit_i_a8cc94_idx')],
                'unique_together': {('page', 'audit')},
            },
        ),
        migrations.CreateModel(
            name='PageCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category_id', models.CharField(max_length=50, verbose_name='Category ID')),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('score', models.IntegerField(help_text='0–100 score for this category', verbose_name='Score')),
                ('rating', models.CharField(choices=[('poor', 'Poor'), ('needs-improvement', 'Needs Improvement'), ('good', 'Good')], max_length=20, verbose_name='Rating')),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categories', to='lighthouse.page', verbose_name='Page')),
            ],
            options={
                'verbose_name': 'Page Category',
                'verbose_name_plural': 'Page Categories',
                'indexes': [models.Index(fields=['category_id', 'score'], name='lighthouse__categor_91b0d4_idx'), models.Index(fields=['category_id', 'rating'], name='lighthouse__categor_136421_idx')],
                'unique_together': {('page', 'category_id')},
            },
        ),
        migrations.CreateModel(
            name='SnapshotAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('poor_count', models.IntegerField(default=0, verbose_name='Poor count')),
                ('needs_count', models.IntegerField(default=0, verbose_name='Needs Improvement count')),
                ('good_count', models.IntegerField(default=0, verbose_name='Good count')),
                ('audit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='snapshot_audits', to='lighthouse.auditdefinition', verbose_name='Audit')),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_results', to='lighthouse.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Snapshot Audit',
                'verbose_name_plural': 'Snapshot Audits',
                'ordering': ['audit__category_id', 'audit__audit_id'],
                'unique_together': {('snapshot', 'audit')},
            },
        ),
        migrations.CreateModel(
            name='SnapshotCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category_id', models.CharField(max_length=50, verbose_name='Category ID')),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('poor_count', models.IntegerField(default=0, verbose_name='Poor count')),
                ('needs_count', models.IntegerField(default=0, verbose_name='Needs Improvement count')),
                ('good_count', models.IntegerField(default=0, verbose_name='Good count')),
                ('score_avg', models.FloatField(blank=True, null=True, verbose_name='Average score')),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_results', to='lighthouse.snapshot', verbose_name='Snapshot')),
            ],
            options={
                'verbose_name': 'Snapshot Category',
                'verbose_name_plural': 'Snapshot Categories',
                'ordering': ['category_id'],
                'unique_together': {('snapshot', 'category_id')},
            },
        ),
    ]
