"""Tests for the Lighthouse audit ID stabilisation mapping."""

from lighthouse.audit_ids import stable_audit_id


class TestStableAuditId:
    def test_unknown_id_returned_unchanged(self):
        assert stable_audit_id("color-contrast") == "color-contrast"

    def test_unknown_future_id_returned_unchanged(self):
        assert stable_audit_id("some-hypothetical-new-audit") == "some-hypothetical-new-audit"

    def test_fid_maps_to_inp(self):
        """FID was replaced by INP in Lighthouse 12; both should produce the same slug."""
        assert stable_audit_id("first-input-delay") == "interaction-to-next-paint"

    def test_inp_maps_to_itself(self):
        assert stable_audit_id("interaction-to-next-paint") == "interaction-to-next-paint"
