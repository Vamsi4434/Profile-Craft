import pytest
from pydantic import ValidationError

from profile_craft.models import Education, Experience, Profile


def test_legacy_duration_is_split_into_years():
    x = Experience(company="Acme", role="DE", duration="2022 - 2024")
    assert (x.start_year, x.end_year) == (2022, 2024)


def test_present_role_has_no_end_year():
    x = Experience(company="Acme", role="DE", duration="2025 - Present")
    assert x.start_year == 2025 and x.end_year is None
    assert x.duration == "2025 - Present"


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError):
        Experience(company="Acme", role="DE", start_year=2024, end_year=2020)


@pytest.mark.parametrize("raw, expected", [("2025", 2025), ("Class of 2023", 2023), ("", None), (2019, 2019)])
def test_graduation_year_parsing(raw, expected):
    assert Education(school="S", degree="D", graduation_year=raw).graduation_year == expected


def test_legacy_year_field_maps_to_graduation_year():
    assert Education.model_validate({"school": "S", "degree": "D", "year": "2025"}).graduation_year == 2025


def test_invalid_email_is_rejected():
    with pytest.raises(ValidationError):
        Profile(email="nope")


def test_email_is_lowercased():
    assert Profile(email="A@B.COM").email == "a@b.com"


def test_bad_phone_is_rejected():
    with pytest.raises(ValidationError):
        Profile(phone="123")


def test_legacy_name_field_maps_to_full_name():
    assert Profile.model_validate({"name": "Jo"}).full_name == "Jo"


def test_completeness():
    assert Profile().completeness() == 0
    assert Profile(full_name="A", email="a@b.co").completeness() == pytest.approx(2 / 8)
