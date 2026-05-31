from unittest.mock import MagicMock, patch

from scrapers.detail_extractor import _installation_steps


def test_installation_steps_from_description_and_reviews():
    driver = MagicMock()
    with patch("scrapers.detail_extractor._description") as desc, \
         patch("scrapers.detail_extractor._installation_meta") as meta:
        desc.return_value = (
            "This bin attaches to the door. Installation is tool-free—simply align and snap into place."
        )
        meta.return_value = {"installation_complexity": None, "installation_time": None}

        el = MagicMock()
        el.text = "Pop the old bin out and snap the new one in."
        driver.find_element.return_value = el
        driver.find_elements.return_value = [el]

        steps = _installation_steps(driver)
    assert any("snap" in s.lower() for s in steps)
    assert any("pop" in s.lower() for s in steps)
