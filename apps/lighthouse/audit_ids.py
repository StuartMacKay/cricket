"""
Cricket-owned stable audit ID mapping.

Lighthouse occasionally renames or replaces audit IDs across major versions
(e.g. first-input-delay was replaced by interaction-to-next-paint in LH 12).
Storing Lighthouse's internal IDs directly would silently orphan historical data
when a version upgrade changes an ID.

This module maps Lighthouse internal IDs → cricket stable slugs. For the vast
majority of audits the mapping is an identity (slug == lighthouse ID). Only
audits that have actually changed in Lighthouse history need explicit entries.

When Lighthouse renames an audit in a future version, add the old ID here
pointing to the current stable slug. Both old and new Lighthouse versions will
then produce data stored under the same slug.
"""

# Lighthouse internal ID → cricket stable slug.
# Add entries when Lighthouse renames or replaces an audit.
AUDIT_ID_MAP: dict[str, str] = {
    # FID (first-input-delay) was replaced by INP in Lighthouse 12.
    "first-input-delay": "interaction-to-next-paint",
}


def stable_audit_id(lighthouse_id: str) -> str:
    """Return cricket's stable slug for a Lighthouse internal audit ID."""
    return AUDIT_ID_MAP.get(lighthouse_id, lighthouse_id)
