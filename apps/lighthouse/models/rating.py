from typing import Optional


class Rating:
    POOR = "poor"
    NEEDS_IMPROVEMENT = "needs-improvement"
    GOOD = "good"

    CHOICES = [
        ("poor", "Poor"),
        ("needs-improvement", "Needs Improvement"),
        ("good", "Good"),
    ]

    @classmethod
    def get_rating(cls, score: Optional[int]) -> Optional[str]:
        """Map a 0-100 score to a rating string.

        Returns None when score is None (audit not applicable).
        """
        if score is None:
            return None
        if score >= 90:
            return cls.GOOD
        if score >= 50:
            return cls.NEEDS_IMPROVEMENT
        return cls.POOR
