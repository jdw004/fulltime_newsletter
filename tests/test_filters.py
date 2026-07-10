"""Filter behaviour against the real config/filters.yaml."""

from src import config
from src.filters import passes
from src.models import Job


def _job(title, locations=None, **kw):
    return Job(
        company=kw.pop("company", "Acme"),
        title=title,
        url=kw.pop("url", f"https://example.com/{abs(hash(title)) % 10000}"),
        locations=locations or [],
        **kw,
    )


F = config.filters()


def test_swe_fulltime_us_kept():
    j = _job("Software Engineer", ["New York, NY"])
    assert passes(j, F)
    assert j.category == "swe"
    assert j.season is None


def test_quant_fulltime_classified_as_quant():
    j = _job("Quantitative Trader", ["Chicago, IL"])
    assert passes(j, F)
    assert j.category == "quant"


def test_technology_analyst_rejected():
    j = _job("Technology Analyst", ["Boston, MA"])
    assert not passes(j, F)


def test_associate_rejected():
    j = _job("Registered Client Service Associate", ["Boston, MA"])
    assert not passes(j, F)


def test_senior_role_rejected():
    j = _job("Senior Software Engineer", ["San Francisco, CA"])
    assert not passes(j, F)


def test_sr_role_rejected():
    j = _job("Sr. Software Engineer", ["San Francisco, CA"])
    assert not passes(j, F)


def test_internship_rejected():
    j = _job("Software Engineer Intern", ["Seattle, WA"])
    assert not passes(j, F)


def test_non_us_location_rejected():
    j = _job("Software Engineer Intern", ["London, UK"])
    assert not passes(j, F)


def test_canada_rejected():
    j = _job("Software Developer Intern", ["Toronto, Canada"])
    assert not passes(j, F)


def test_unknown_location_kept():
    j = _job("Software Engineer")
    assert passes(j, F)  # keep_when_location_unknown: true


def test_multi_location_with_us_option_kept():
    j = _job("Software Engineer", ["London, UK", "New York, NY"])
    assert passes(j, F)


def test_non_category_fulltime_rejected():
    j = _job("Marketing Coordinator", ["New York, NY"])
    assert not passes(j, F)


def test_research_scientist_rejected():
    j = _job("Research Scientist", ["Austin, TX"])
    assert not passes(j, F)


def test_remote_kept():
    j = _job("Software Engineer", ["Remote"])
    assert passes(j, F)
