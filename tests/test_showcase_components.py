"""
tests/test_showcase_components.py

Tests for the 6 intelligence showcase Jinja2 partial templates.
Uses Jinja2 environment directly — no Flask server needed.
"""
import json
import os
import pytest
from jinja2 import Environment, FileSystemLoader, Undefined


# ---------------------------------------------------------------------------
# Jinja2 environment setup
# ---------------------------------------------------------------------------
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'templates')
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'web', 'static', 'data', 'showcase_data.json')


def make_env():
    """Create a Jinja2 Environment with the tojson filter and urlencode filter."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    env.filters['tojson'] = json.dumps
    env.filters['urlencode'] = lambda s: s.replace(' ', '+') if isinstance(s, str) else str(s)
    # Add truncate filter that Jinja2 provides by default — it already exists.
    return env


def load_showcase_data():
    """Load the showcase_data.json fixture."""
    with open(DATA_FILE) as f:
        return json.load(f)


@pytest.fixture(scope='module')
def env():
    return make_env()


@pytest.fixture(scope='module')
def showcase():
    return load_showcase_data()


@pytest.fixture(scope='module')
def context(showcase):
    # Also need loop variable available at module scope for entity template
    return {'showcase': showcase}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def render(env, template_path, context):
    """Render a component template with the given context."""
    tmpl = env.get_template(template_path)
    return tmpl.render(**context)


# ---------------------------------------------------------------------------
# Component 1: showcase_gantt.html
# ---------------------------------------------------------------------------
class TestShowcaseGantt:
    TEMPLATE = 'components/showcase_gantt.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_contains_permit_number(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '202509155257' in html

    def test_contains_station_names(self, env, context):
        html = render(env, self.TEMPLATE, context)
        for station in ['PERMIT-CTR', 'CP-ZOC', 'BLDG', 'CPB']:
            assert station in html, f"Missing station: {station}"

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/station-predictor?permit=202509155257' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-track="showcase-click"' in html
        assert 'data-showcase="gantt"' in html

    def test_you_are_here_on_current_station(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'you are here' in html


# ---------------------------------------------------------------------------
# Component 2: showcase_stuck.html
# ---------------------------------------------------------------------------
class TestShowcaseStuck:
    TEMPLATE = 'components/showcase_stuck.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_contains_permit_number(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '202412237330' in html

    def test_contains_severity_badge(self, env, context):
        # Redesigned: shows "CRITICAL" badge + "4 agencies blocked" headline.
        # "4 SIMULTANEOUS BLOCKS" text was replaced by the visual pipeline design.
        html = render(env, self.TEMPLATE, context)
        assert 'CRITICAL' in html
        assert 'agencies blocked' in html

    def test_pipeline_station_blocks(self, env, context):
        # Redesigned: shows visual pipeline — reviewer names are not displayed.
        # Station abbreviations replace reviewer text in the new layout.
        html = render(env, self.TEMPLATE, context)
        for station in ['BLDG', 'MECH', 'SFFD', 'CP-ZOC']:
            assert station in html, f"Pipeline station '{station}' missing"

    def test_contains_first_playbook_step(self, env, context):
        # Redesigned: only shows Step 1 of the playbook as the intervention hint.
        # Full multi-step playbook is available at the linked tool page.
        html = render(env, self.TEMPLATE, context)
        assert 'Step 1:' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/stuck-permit?permit=202412237330' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="stuck"' in html


# ---------------------------------------------------------------------------
# Component 3: showcase_whatif.html
# ---------------------------------------------------------------------------
class TestShowcaseWhatif:
    TEMPLATE = 'components/showcase_whatif.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_contains_simulation_intelligence_label(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'Simulation Intelligence' in html

    def test_contains_visual_timeline_numbers(self, env, context):
        # Visual-first design: big timeline numbers, not construction cost columns
        html = render(env, self.TEMPLATE, context)
        assert '2 weeks' in html
        assert '5 months' in html
        assert '$1,200' in html
        assert '$6,487' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/what-if?demo=kitchen-vs-full' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="whatif"' in html

    def test_has_visual_comparison_columns(self, env, context):
        # Visual-first: two tinted columns, not a data table
        html = render(env, self.TEMPLATE, context)
        assert 'whatif-col--a' in html
        assert 'whatif-col--b' in html


# ---------------------------------------------------------------------------
# Component 4: showcase_risk.html
# ---------------------------------------------------------------------------
class TestShowcaseRisk:
    TEMPLATE = 'components/showcase_risk.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_contains_risk_percentage(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '24.6%' in html or '24.6' in html

    def test_has_predictive_intelligence_label(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'Predictive Intelligence' in html

    def test_has_svg_arc_gauge(self, env, context):
        # Visual-first: circular SVG gauge replaces linear gauge bar
        html = render(env, self.TEMPLATE, context)
        assert '<svg' in html
        assert '<circle' in html

    def test_contains_risk_percentage_in_gauge(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '24.6%' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/revision-risk?demo=restaurant-mission' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="risk"' in html

    def test_has_context_description(self, env, context):
        # Visual-first: simple context label, not a full data table
        html = render(env, self.TEMPLATE, context)
        assert 'Restaurant alterations in the Mission' in html


# ---------------------------------------------------------------------------
# Component 5: showcase_entity.html
# ---------------------------------------------------------------------------
class TestShowcaseEntity:
    TEMPLATE = 'components/showcase_entity.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_contains_address(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '1 Market St' in html

    def test_contains_professional_names(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'Arb Inc' in html
        assert 'Gensler' in html
        assert 'Pribuss Engineering' in html

    def test_contains_permit_counts(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '12,674' in html
        assert '7,309' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/entity-network' in html
        assert '1+MARKET' in html or '1 Market St' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="entity"' in html

    def test_has_professional_cards_grid(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'entity-pros' in html
        assert 'entity-pro' in html


# ---------------------------------------------------------------------------
# Component 6: showcase_delay.html
# ---------------------------------------------------------------------------
class TestShowcaseDelay:
    TEMPLATE = 'components/showcase_delay.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_has_financial_intelligence_label(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'Financial Intelligence' in html

    def test_has_hero_daily_cost_number(self, env, context):
        # Visual-first: $500/day hero number is the primary element
        html = render(env, self.TEMPLATE, context)
        assert '$500' in html
        assert '/day' in html

    def test_has_expected_total(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$41,375' in html

    def test_has_carrying_cost_basis(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$15K/mo' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/cost-of-delay?demo=restaurant-15k' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="delay"' in html

    def test_hero_number_present_in_card(self, env, context):
        # The big number IS the intelligence — must be immediately visible
        html = render(env, self.TEMPLATE, context)
        assert 'delay-hero-number' in html
