from typing import Optional

from django.utils.translation import gettext_lazy as _


class Rating:
    POOR = 0
    NEEDS_IMPROVEMENT = 1
    GOOD = 2

    VALUES = [POOR, NEEDS_IMPROVEMENT, GOOD]

    RANGES = {
        POOR: (0, 49),
        NEEDS_IMPROVEMENT: (50, 89),
        GOOD: (90, 100),
    }

    NAMES = {
        POOR: _("Poor"),
        NEEDS_IMPROVEMENT: _("Needs Improvement"),
        GOOD: _("Good"),
    }

    @classmethod
    def values(cls):
        return cls.VALUES

    @classmethod
    def ranges(cls):
        return cls.RANGES.values()

    @classmethod
    def names(cls):
        return cls.NAMES.values()

    @classmethod
    def get_rating(cls, score: Optional[int]) -> Optional[int]:
        if score is not None:
            for rating, (lower, upper) in cls.RANGES.items():
                if lower <= score <= upper:
                    return rating
