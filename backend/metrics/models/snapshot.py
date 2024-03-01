import io
import os
import pathlib

from django.conf import settings
from django.core.files import File
from django.db import connection, models
from django.template.defaultfilters import date
from django.template.loader import get_template, render_to_string
from django.utils.translation import gettext_lazy as _

import plotly.graph_objects as go
import plotly.io as pio
from django_extensions.db.models import TimeStampedModel
from weasyprint import CSS, HTML

from .page import Page
from .rating import Rating

STYLESHEET_PATH = os.path.join(
    settings.BACKEND_DIR, "metrics/static/css/bootstrap.min.css"
)


def report_path(instance, filename):
    slug = instance.site.slug
    name, extension = os.path.splitext(os.path.basename(filename))
    year = instance.created.strftime("%Y")
    ymd = instance.created.strftime("%Y-%m-%d")
    name = "{}-{}{}".format(name, ymd, extension)
    return os.path.join("report", slug, year, name)


class Snapshot(TimeStampedModel, models.Model):
    class Meta:
        verbose_name = _("Snapshot")
        verbose_name_plural = _("Snapshots")

    report = models.FileField(
        upload_to=report_path,
        verbose_name=_("Report"),
        help_text=_("The PDF report for the site metrics"),
        null=True,
        blank=True,
    )

    site = models.ForeignKey(
        "Site",
        models.CASCADE,
        related_name="snapshots",
        verbose_name=_("Site"),
        help_text=_("The Site this Snapshot was created from"),
    )

    data = models.JSONField(
        verbose_name=_("Data"),
        help_text=_("Parameters for creating snapshots and Page summary metrics"),
        default=dict,
    )

    def create_pages(self):
        for url in self.site.get_urls():
            Page.objects.get_or_create(url=url, audited=False, snapshot=self)

    def get_page_keys(self):
        return self.pages.all().values_list("pk", flat=True)

    def get_number_of_pages(self) -> int:
        return int(self.pages.all().count())

    def get_ratings(self, prefix: str, key: str) -> list[int]:
        ratings: list[int] = []
        with connection.cursor() as cursor:
            for rating in Rating.values():
                cursor.execute(
                    f"select count(*) "
                    f"from metrics_page "
                    f"where audited=TRUE "
                    f"and snapshot_id={self.pk} "
                    f"and (data->'{prefix}'->'{key}'->'rating')::int={rating} "
                    f"and data->'{prefix}'->'{key}'->'rating' is not null"
                )
                ratings.append(cursor.fetchall()[0][0])
        return ratings

    def get_scores(self, prefix: str, key: str, groups: int) -> list[int]:
        scores: list[int] = [0] * groups
        interval = int(100 / groups)
        with connection.cursor() as cursor:
            cursor.execute(
                f"select "
                f"count(*), "
                f"((data->'{prefix}'->'{key}'->'score')::int/{interval})::int as score "
                f"from metrics_page "
                f"where audited=TRUE "
                f"and snapshot_id={self.pk} "
                f"and data->'{prefix}'->'{key}'->'score' is not null "
                f"group by score"
            )
            result = cursor.fetchall()

        # Scores are in the range 0..100, so the number of intervals
        # will be one more than the number of groups. As a result,
        # scores of 100 are added to the last group.

        for count, index in result:
            if index == groups:
                index = groups - 1
            scores[index] += count

        return scores

    def get_urls(self, prefix: str, key: str, limit: int) -> list[tuple[str, str, int]]:
        with connection.cursor() as cursor:
            cursor.execute(
                f"select url, (data->'{prefix}'->'{key}'->'score')::int as score "
                f"from metrics_page "
                f"where audited=TRUE "
                f"and snapshot_id={self.pk} "
                f"and data->'{prefix}'->'{key}'->'score' is not null "
                f"order by score "
                f"limit {limit}"
            )
            results = cursor.fetchall()
            results.reverse()
            return results

    def _collect_audit_metadata(self, data):
        results = {}
        for key, audit in data.items():
            results[key] = {
                "id": audit["id"],
                "title": audit["title"],
                "type": audit["type"],
            }
        self.data["audits"] = results

    def _collect_audit_metrics(self):
        for category in self.data["categories"].values():
            for key in category["audits"]:
                # viewport is lists in the auditRefs for the performance category
                # however it is an SEO audit.
                groups = (
                    20 if category["id"] == "performance" and key != "viewport" else 2
                )
                audit = self.data["audits"][key]
                audit["ratings"] = self.get_ratings("audits", key)
                audit["scores"] = self.get_scores("audits", key, groups)
                audit["urls"] = self.get_urls("audits", key, 20)

    def _collect_category_metadata(self, data):
        results = {}
        for key, category in data.items():
            results[key] = {
                "id": category["id"],
                "title": category["title"],
                "audits": category["audits"].copy(),
            }
        self.data["categories"] = results

    def _collect_category_metrics(self):
        for key, category in self.data["categories"].items():
            category["ratings"] = self.get_ratings("categories", key)
            category["scores"] = self.get_scores("categories", key, 20)
            category["urls"] = self.get_urls("categories", key, 20)

    def _collect_metadata(self):
        page: Page = self.pages.filter(audited=True).first()
        self._collect_category_metadata(page.data["categories"])
        self._collect_audit_metadata(page.data["audits"])

    def _delete_config_file(self):
        path = pathlib.Path(self.data.pop("config_file"))
        path.unlink()

    def collect_metrics(self):
        self._collect_metadata()
        self._collect_category_metrics()
        self._collect_audit_metrics()
        self._delete_config_file()
        self.save()

    def category_ratings_table(self, category: str) -> str:
        context = {
            "category": self.data["categories"][category]["title"],
            "scores": self.data["categories"][category]["ratings"],
        }
        template = "metrics/reports/category-ratings.html"
        return render_to_string(template, context)

    def get_category_score_graph(self, category: str) -> str:
        y = self.data["categories"][category]["scores"]
        interval = int(100 / len(y))
        x = [val for val in range(0, 100, interval)]

        fig = go.Figure(
            data=[go.Bar(x=x, y=y, showlegend=False, text=y)],
        )

        fig.update_layout(
            height=300,
            margin=dict(l=10, r=15, t=10, b=10),
            xaxis_title="Score",
            xaxis_title_font=dict(size=14),
            xaxis_rangemode="tozero",
            xaxis_dtick=interval,
            yaxis_title="No. of Pages",
            yaxis_title_font=dict(size=14),
        )

        template = "metrics/reports/category-score-graph.html"
        context = {
            "category": self.data["categories"][category]["title"],
            "graph": pio.to_image(fig, format="svg").decode(),
        }
        return render_to_string(template, context)

    def category_score_urls_table(self, category: str) -> str:
        context = {
            "category": self.data["categories"][category]["title"],
            "values": self.data["categories"][category]["urls"],
        }
        template = "metrics/reports/category-score-urls.html"
        return render_to_string(template, context)

    def audit_ratings_table(self, audit: str) -> str:
        context = {
            "audit": self.data["audits"][audit]["title"],
            "scores": self.data["audits"][audit]["ratings"],
        }
        template = "metrics/reports/audit-ratings.html"
        return render_to_string(template, context)

    def get_audit_score_graph(self, audit: str) -> str:
        y = self.data["audits"][audit]["scores"]
        interval = int(100 / len(y))
        x = [val for val in range(0, 100, interval)]
        fig = go.Figure(
            data=[go.Bar(x=x, y=y, showlegend=False, text=y)],
        )
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=15, t=10, b=10),
            xaxis_title="Score",
            xaxis_title_font=dict(size=14),
            xaxis_rangemode="tozero",
            xaxis_dtick=interval,
            yaxis_title="No. of Pages",
            yaxis_title_font=dict(size=14),
        )
        template = "metrics/reports/audit-score-graph.html"
        context = {
            "audit": self.data["audits"][audit]["title"],
            "graph": pio.to_image(fig, format="svg").decode(),
        }
        return render_to_string(template, context)

    def audit_score_urls_table(self, audit: str) -> str:
        context = {
            "audit": self.data["audits"][audit]["title"],
            "values": self.data["audits"][audit]["urls"],
        }
        template = "metrics/reports/audit-score-urls.html"
        return render_to_string(template, context)

    def category_checklist(self, category: str) -> str:
        values = []

        for audit in self.data["categories"][category]["audits"]:
            failed, passed = self.data["audits"][audit]["scores"]
            title = self.data["audits"][audit]["title"]
            values.append((title, failed))

        context = {
            "category": self.data["categories"][category]["title"],
            "values": values,
        }
        template = "metrics/reports/category-checklist.html"
        return render_to_string(template, context)

    def get_context(self):
        context = {
            "date": date(self.created, "jS F Y"),
            "time": date(self.created, "g:i a"),
            "url": self.site.url,
            "pages": self.get_number_of_pages(),
            "categories": [
                category["title"] for category in self.data["categories"].values()
            ],
            "platform": self.data["config"]["formFactor"],
        }

        for category in self.data["categories"].keys():
            key = f"{category}_ratings_table".replace("-", "_")
            context[key] = self.category_ratings_table(category)

        for category in self.data["categories"].keys():
            key = f"{category}_score_graph".replace("-", "_")
            context[key] = self.get_category_score_graph(category)

        for category in self.data["categories"].keys():
            key = f"{category}_score_urls_table".replace("-", "_")
            context[key] = self.category_score_urls_table(category)

        for audit in self.data["categories"]["performance"]["audits"]:
            key = f"{audit}_ratings_table".replace("-", "_")
            context[key] = self.audit_ratings_table(audit)
            key = f"{audit}_score_graph".replace("-", "_")
            context[key] = self.get_audit_score_graph(audit)
            key = f"{audit}_score_urls_table".replace("-", "_")
            context[key] = self.audit_score_urls_table(audit)

        for category in ("accessibility", "best-practices", "seo"):
            key = f"{category}_audits_checklist".replace("-", "_")
            context[key] = self.category_checklist(category)

        return context

    def publish_report(self):
        template = get_template("metrics/reports/index.html")
        html: str = template.render(self.get_context())
        document: HTML = HTML(string=html)
        pdf: bytes = document.write_pdf(stylesheets=[CSS(STYLESHEET_PATH)])
        fp = io.BytesIO(pdf)
        if self.report.name:
            self.report.delete()
        self.report.save("report.pdf", File(fp))
