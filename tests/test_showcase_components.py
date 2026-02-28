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

    def test_contains_scenario_labels(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'KITCHEN ONLY' in html
        assert 'KITCHEN + BATH + WALL' in html

    def test_contains_key_values(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$45,000' in html
        assert '$185,000' in html
        assert '$1,200' in html
        assert '$6,487' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/what-if?demo=kitchen-vs-full' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="whatif"' in html

    def test_strategy_callout_present(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'splitting into two permits' in html.lower() or 'splitting' in html.lower()


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

    def test_contains_severity_badge(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'HIGH' in html

    def test_contains_sample_size(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '21,596' in html

    def test_contains_top_triggers(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'grease interceptor' in html.lower()
        assert 'ventilation' in html.lower()

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/revision-risk?demo=restaurant-mission' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="risk"' in html

    def test_budget_recommendation_present(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$321,250' in html


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

    def test_contains_permit_count(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '63' in html

    def test_contains_node_labels(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'Hathaway Dinwiddie' in html
        assert 'Gensler' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/entity-network' in html
        assert '1+Market+St' in html or '1 Market St' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="entity"' in html

    def test_svg_present(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '<svg' in html


# ---------------------------------------------------------------------------
# Component 6: showcase_delay.html
# ---------------------------------------------------------------------------
class TestShowcaseDelay:
    TEMPLATE = 'components/showcase_delay.html'

    def test_renders_without_error(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert html

    def test_contains_monthly_cost(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$15,000' in html

    def test_contains_delay_scenarios(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'Best case' in html
        assert 'Typical' in html
        assert 'Conservative' in html
        assert 'Worst case' in html

    def test_contains_cost_values(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$17,500' in html
        assert '$35,000' in html
        assert '$56,500' in html
        assert '$87,000' in html

    def test_expected_cost_highlighted(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '$41,375' in html

    def test_warning_badge_present(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'SFFD-HQ' in html
        assert '86%' in html

    def test_ghost_cta_link(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert '/tools/cost-of-delay?demo=restaurant-15k' in html

    def test_data_track_attributes(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'data-track="showcase-view"' in html
        assert 'data-showcase="delay"' in html

    def test_recommendation_present(self, env, context):
        html = render(env, self.TEMPLATE, context)
        assert 'p75' in html
