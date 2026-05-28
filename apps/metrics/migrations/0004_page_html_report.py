from django.db import migrations, models

import metrics.models.page


class Migration(migrations.Migration):

    dependencies = [
        ("metrics", "0003_alter_page_id_alter_site_config_alter_site_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="page",
            name="html_report",
            field=models.FileField(
                blank=True,
                help_text="The self-contained Lighthouse HTML report for this Page, identical to Chrome's Lighthouse panel output",
                null=True,
                upload_to=metrics.models.page.audit_report_path,
                verbose_name="HTML Report",
            ),
        ),
    ]
