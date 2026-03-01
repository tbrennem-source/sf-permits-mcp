"""
tests/test_showcase_cards_redesign.py

Tests for the 4 visual-first showcase card redesigns (Sprint 94).
Verifies each component renders without error and contains required visual elements.
"""
import json
import os
import pytest
from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "web", "templates"
)


@pytest.fixture(scope="module")
def jinja_env():
    """Jinja2 environment pointed at web/templates."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=False,
    )
    return env


@pytest.fixture(scope="module")
def showcase_data():
    """Load showcase_data.json as a dict under the 'showcase' key expected by templates."""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "web", "static", "data", "showcase_data.json"
    )
    with open(data_path) as f:
        raw = json.load(f)

    # Templates access showcase.whatif, showcase.revision_risk, etc.
    return {
        "whatif": raw.get("whatif", {}),
        "revision_risk": raw.get("revision_risk", {}),
        "entity_network": raw.get("entity_network", {}),
        "cost_of_delay": raw.get("cost_of_delay", {}),
    }


def render_component(jinja_env, template_path, showcase_data):
    """Helper: render a component template with a showcase context."""
    tmpl = jinja_env.get_template(template_path)
    return tmpl.render(showcase=showcase_data)


# ─── What-If Card ──────────────────────────────────────────────────────────────

class TestShowcaseWhatif:
    def test_renders_without_error(self, jinja_env, showcase_data):
        """Component renders with no exceptions."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert html

    def test_has_intelligence_label(self, jinja_env, showcase_data):
        """Card displays 'Simulation Intelligence' label."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert "Simulation Intelligence" in html

    def test_has_two_comparison_columns(self, jinja_env, showcase_data):
        """Card has two comparison columns (col--a and col--b)."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert "whatif-col--a" in html
        assert "whatif-col--b" in html

    def test_has_big_numbers(self, jinja_env, showcase_data):
        """Card contains large timeline values — 2 weeks and 5 months."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert "2 weeks" in html
        assert "5 months" in html

    def test_has_sub_costs(self, jinja_env, showcase_data):
        """Card shows fee and review path for each scenario."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert "$1,200" in html
        assert "$6,487" in html
        assert "OTC" in html
        assert "In-house" in html

    def test_has_timeline_bars(self, jinja_env, showcase_data):
        """Card has bar elements for relative timeline visualization."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert "whatif-bar-fill--a" in html
        assert "whatif-bar-fill--b" in html

    def test_has_ghost_cta_with_correct_link(self, jinja_env, showcase_data):
        """Card has ghost CTA linking to what-if demo."""
        html = render_component(jinja_env, "components/showcase_whatif.html", showcase_data)
        assert "ghost-cta" in html
        assert "/tools/what-if?demo=kitchen-vs-full" in html
        assert "Compare your project" in html


# ─── Revision Risk Card ────────────────────────────────────────────────────────

class TestShowcaseRisk:
    def test_renders_without_error(self, jinja_env, showcase_data):
        """Component renders with no exceptions."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert html

    def test_has_intelligence_label(self, jinja_env, showcase_data):
        """Card displays 'Predictive Intelligence' label."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "Predictive Intelligence" in html

    def test_has_svg_gauge_element(self, jinja_env, showcase_data):
        """Card contains an SVG element for the circular gauge."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "<svg" in html
        assert "<circle" in html

    def test_gauge_shows_correct_percentage(self, jinja_env, showcase_data):
        """Card displays 24.6% prominently in the gauge."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "24.6%" in html

    def test_gauge_uses_amber_color(self, jinja_env, showcase_data):
        """Gauge arc uses amber token color (--dot-amber)."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "--dot-amber" in html

    def test_has_context_description(self, jinja_env, showcase_data):
        """Card shows context: 'Restaurant alterations in the Mission'."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "Restaurant alterations in the Mission" in html

    def test_has_triggers_link(self, jinja_env, showcase_data):
        """Card has '5 common triggers' as a ghost/link element."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "5 common triggers" in html

    def test_has_ghost_cta_with_correct_link(self, jinja_env, showcase_data):
        """Card has ghost CTA linking to revision-risk demo."""
        html = render_component(jinja_env, "components/showcase_risk.html", showcase_data)
        assert "ghost-cta" in html
        assert "/tools/revision-risk?demo=restaurant-mission" in html
        assert "Check your risk" in html


# ─── Entity Network Card ───────────────────────────────────────────────────────

class TestShowcaseEntity:
    def test_renders_without_error(self, jinja_env, showcase_data):
        """Component renders with no exceptions."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert html

    def test_has_intelligence_label(self, jinja_env, showcase_data):
        """Card displays 'Network Intelligence' label."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "Network Intelligence" in html

    def test_has_professional_cards(self, jinja_env, showcase_data):
        """Card contains text-first professional cards grid."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "entity-pros" in html
        assert "entity-pro" in html

    def test_has_professional_roles(self, jinja_env, showcase_data):
        """Card shows professional roles (Contractor, Engineer, Architect)."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "Contractor" in html
        assert "Engineer" in html
        assert "Architect" in html

    def test_has_professional_names(self, jinja_env, showcase_data):
        """Card shows entity names."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "Arb Inc" in html
        assert "Pribuss Engineering" in html
        assert "Gensler" in html

    def test_has_permit_counts(self, jinja_env, showcase_data):
        """Card shows permit counts for each professional."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "12,674" in html
        assert "7,309" in html
        assert "4,821" in html

    def test_has_summary_text(self, jinja_env, showcase_data):
        """Card has a summary paragraph about the professionals."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "entity-summary" in html
        assert "1 Market St" in html

    def test_has_ghost_cta_with_correct_link(self, jinja_env, showcase_data):
        """Card has ghost CTA linking to entity-network with address."""
        html = render_component(jinja_env, "components/showcase_entity.html", showcase_data)
        assert "ghost-cta" in html
        assert "/tools/entity-network?address=1+MARKET" in html
        assert "Find professionals" in html


# ─── Cost of Delay Card ────────────────────────────────────────────────────────

class TestShowcaseDelay:
    def test_renders_without_error(self, jinja_env, showcase_data):
        """Component renders with no exceptions."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert html

    def test_has_intelligence_label(self, jinja_env, showcase_data):
        """Card displays 'Financial Intelligence' label."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "Financial Intelligence" in html

    def test_has_dollar500_hero_number(self, jinja_env, showcase_data):
        """Card displays '$500' as the hero number."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "$500" in html

    def test_has_per_day_unit(self, jinja_env, showcase_data):
        """Card shows '/day' unit alongside the hero number."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "/day" in html

    def test_has_expected_total(self, jinja_env, showcase_data):
        """Card shows the expected total carrying cost."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "$41,375" in html

    def test_has_carrying_cost_basis(self, jinja_env, showcase_data):
        """Card shows the carrying cost basis ($15K/mo)."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "$15K/mo" in html

    def test_hero_number_uses_amber(self, jinja_env, showcase_data):
        """Hero number uses amber signal color."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "delay-hero-number" in html
        assert "signal-amber" in html

    def test_has_ghost_cta_with_correct_link(self, jinja_env, showcase_data):
        """Card has ghost CTA linking to cost-of-delay demo."""
        html = render_component(jinja_env, "components/showcase_delay.html", showcase_data)
        assert "ghost-cta" in html
        assert "/tools/cost-of-delay?demo=restaurant-15k" in html
        assert "Calculate your cost" in html
