"""MIT attribution must travel with the *installed* package, not just the git tree.

PR #33 was found by the product repo once `dcf_fair_value` resolved into the
wheel: NOTICE.md + LICENSE-cookbooks were in source but omitted from
package-data. A version-literal bump does not catch that regression.
"""

from __future__ import annotations

from importlib.resources import files


def test_dcf_vendor_notice_and_license_are_importable_package_data():
    root = files("gesh_core.dcf.vendor")
    notice = root.joinpath("NOTICE.md")
    license_file = root.joinpath("LICENSE-cookbooks")
    assert notice.is_file(), "NOTICE.md missing from installed gesh_core.dcf.vendor"
    assert license_file.is_file(), "LICENSE-cookbooks missing from installed gesh_core.dcf.vendor"
    notice_text = notice.read_text(encoding="utf-8")
    license_text = license_file.read_text(encoding="utf-8")
    assert "anthropics/claude-cookbooks" in notice_text
    assert "MIT" in license_text
