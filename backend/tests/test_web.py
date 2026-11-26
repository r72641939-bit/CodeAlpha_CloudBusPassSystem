"""Security headers, search files and input rules - no database needed."""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app import web
from app.core.validation import clean_passenger_name

PAGE = (Path(web.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


def test_page_placeholders_are_filled():
    assert "__SITE_URL__" not in web.render_page(PAGE)


def test_policy_allows_scripts_only_by_hash():
    policy = web.content_security_policy(web.render_page(PAGE))
    script_rule = next(p for p in policy.split("; ") if p.startswith("script-src"))
    assert "sha256-" in script_rule
    assert "unsafe" not in script_rule


def test_sitemap_is_valid_and_robots_points_to_it():
    root = ET.fromstring(web.sitemap_xml().encode())
    assert root[0][0].text == web.SITE_URL + "/"
    assert web.SITE_URL + "/sitemap.xml" in web.robots_txt()


@pytest.mark.parametrize("bad", ["   ", "<b>Ali</b>", "Win at http://x.test", "www.x.test", "Ali\nBcc: a@b.c"])
def test_unsafe_names_are_rejected(bad):
    with pytest.raises(ValueError):
        clean_passenger_name(bad)


@pytest.mark.parametrize("good", ["Ram Kumar", "محمد علی", "O'Brien-Khan Jr."])
def test_real_names_are_accepted(good):
    assert clean_passenger_name(f"  {good} ") == good
