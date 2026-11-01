from profile_craft.models import Certification, Experience, Profile
from profile_craft.pdf import generate_ats_pdf


def test_pdf_is_generated():
    pdf = generate_ats_pdf(Profile(full_name="Ana", email="ana@example.com"))
    assert pdf.startswith(b"%PDF")


def test_special_characters_do_not_break_pdf():
    p = Profile(
        full_name="R&D <Lead>",
        summary="SQL & Python; a < b",
        experience=[Experience(company="AT&T", role="Data & Analytics", start_year=2020)],
        certifications=[Certification(name="C++ & Rust")],
    )
    assert generate_ats_pdf(p).startswith(b"%PDF")
