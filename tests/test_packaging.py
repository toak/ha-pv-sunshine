"""Release metadata and translated forms stay internally consistent."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components/pv_sunshine"


def test_metadata_and_translations():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    assert manifest["domain"] == "pv_sunshine"
    assert manifest["version"] == "0.2.1"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "calculated"
    assert manifest["requirements"] == []
    assert manifest["codeowners"] == ["@toak"]
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["name"] == manifest["name"]
    source = json.loads((COMPONENT / "strings.json").read_text())
    translated = json.loads((COMPONENT / "translations/en.json").read_text())
    assert source == translated
    assert set(source["options"]["step"]["init"]["menu_options"]) <= set(source["options"]["step"])
    assert (COMPONENT / "brand/icon.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
