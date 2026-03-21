# ============================================================
# FILE: tests/test_joseph_widget.py
# PURPOSE: Tests for utils/joseph_widget.py
#          (Joseph's global sidebar widget — Layer 9)
# ============================================================
import sys, os, unittest
from unittest.mock import MagicMock, patch

# Ensure repo root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock streamlit before importing the module
_mock_st = MagicMock()
_mock_st.cache_data = lambda *a, **kw: (lambda f: f)
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)
sys.modules.setdefault("streamlit.components", MagicMock())
sys.modules.setdefault("streamlit.components.v1", MagicMock())

# Always use the actual mock from sys.modules (in case another test set it first)
_mock_st = sys.modules["streamlit"]


# ============================================================
# SECTION 1: Module imports & exports
# ============================================================

class TestModuleImports(unittest.TestCase):
    """Verify the module imports cleanly and exposes expected symbols."""

    def test_import_module(self):
        import utils.joseph_widget
        self.assertTrue(hasattr(utils.joseph_widget, "_inject_widget_css"))

    def test_inject_widget_css_callable(self):
        from utils.joseph_widget import _inject_widget_css
        self.assertTrue(callable(_inject_widget_css))

    def test_render_sidebar_widget_callable(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        self.assertTrue(callable(render_joseph_sidebar_widget))

    def test_inject_inline_commentary_callable(self):
        from utils.joseph_widget import inject_joseph_inline_commentary
        self.assertTrue(callable(inject_joseph_inline_commentary))

    def test_widget_css_constant_exists(self):
        from utils.joseph_widget import _WIDGET_CSS
        self.assertIsInstance(_WIDGET_CSS, str)

    def test_all_three_functions_importable(self):
        from utils.joseph_widget import (
            _inject_widget_css,
            render_joseph_sidebar_widget,
            inject_joseph_inline_commentary,
        )
        self.assertTrue(callable(_inject_widget_css))
        self.assertTrue(callable(render_joseph_sidebar_widget))
        self.assertTrue(callable(inject_joseph_inline_commentary))


# ============================================================
# SECTION 2: _WIDGET_CSS content validation
# ============================================================

class TestWidgetCSS(unittest.TestCase):
    """Verify the widget CSS string contains all required classes."""

    def setUp(self):
        from utils.joseph_widget import _WIDGET_CSS
        self.css = _WIDGET_CSS

    def test_contains_style_tag(self):
        self.assertIn("<style>", self.css)
        self.assertIn("</style>", self.css)

    def test_sidebar_container(self):
        self.assertIn("joseph-sidebar-container", self.css)
        self.assertIn("rgba(7,10,19,0.90)", self.css)
        self.assertIn("backdrop-filter", self.css)

    def test_sidebar_avatar(self):
        self.assertIn("joseph-sidebar-avatar", self.css)
        self.assertIn("56px", self.css)
        self.assertIn("#ff5e00", self.css)

    def test_sidebar_avatar_hover(self):
        self.assertIn("joseph-sidebar-avatar:hover", self.css)
        self.assertIn("scale(1.1)", self.css)

    def test_ambient_text(self):
        self.assertIn("joseph-ambient-text", self.css)
        self.assertIn("#ff9d4d", self.css)
        self.assertIn("font-style:italic", self.css)

    def test_pulse_dot(self):
        self.assertIn("joseph-pulse-dot", self.css)
        self.assertIn("josephPulse", self.css)
        self.assertIn("1.5s", self.css)

    def test_pulse_keyframes(self):
        self.assertIn("@keyframes josephPulse", self.css)
        self.assertIn("scale(0.8)", self.css)
        self.assertIn("scale(1.2)", self.css)

    def test_inline_card(self):
        self.assertIn("joseph-inline-card", self.css)
        self.assertIn("rgba(255,94,0,0.25)", self.css)

    def test_inline_avatar(self):
        self.assertIn("joseph-inline-avatar", self.css)
        self.assertIn("36px", self.css)

    def test_inline_label(self):
        self.assertIn("joseph-inline-label", self.css)
        self.assertIn("font-weight:700", self.css)

    def test_inline_text(self):
        self.assertIn("joseph-inline-text", self.css)
        self.assertIn("#c0d0e8", self.css)

    def test_verdict_smash(self):
        self.assertIn("joseph-widget-verdict-smash", self.css)
        self.assertIn("#ff4444", self.css)

    def test_verdict_lean(self):
        self.assertIn("joseph-widget-verdict-lean", self.css)
        self.assertIn("#00ff9d", self.css)

    def test_verdict_fade(self):
        self.assertIn("joseph-widget-verdict-fade", self.css)
        self.assertIn("#ffc800", self.css)

    def test_orange_accent_color(self):
        self.assertIn("#ff5e00", self.css)

    def test_border_radius_12(self):
        self.assertIn("border-radius:12px", self.css)

    def test_border_radius_10(self):
        self.assertIn("border-radius:10px", self.css)


# ============================================================
# SECTION 3: _inject_widget_css()
# ============================================================

class TestInjectWidgetCss(unittest.TestCase):
    """Test _inject_widget_css injects CSS via st.markdown."""

    def setUp(self):
        _mock_st.reset_mock()
        _mock_st.session_state = {}

    def test_injects_css(self):
        from utils.joseph_widget import _inject_widget_css
        _inject_widget_css()
        _mock_st.markdown.assert_called()
        call_args = _mock_st.markdown.call_args
        self.assertIn("<style>", call_args[0][0])

    def test_unsafe_allow_html(self):
        from utils.joseph_widget import _inject_widget_css
        _inject_widget_css()
        call_args = _mock_st.markdown.call_args
        self.assertTrue(call_args[1].get("unsafe_allow_html", False))

    def test_idempotent_injection(self):
        """Second call should not re-inject CSS."""
        from utils.joseph_widget import _inject_widget_css
        _mock_st.session_state = {}
        _inject_widget_css()
        first_count = _mock_st.markdown.call_count
        _inject_widget_css()
        second_count = _mock_st.markdown.call_count
        self.assertEqual(first_count, second_count)

    def test_session_flag_set(self):
        from utils.joseph_widget import _inject_widget_css
        _mock_st.session_state = {}
        _inject_widget_css()
        self.assertTrue(_mock_st.session_state.get("_joseph_widget_css_injected"))


# ============================================================
# SECTION 4: render_joseph_sidebar_widget()
# ============================================================

class TestRenderJosephSidebarWidget(unittest.TestCase):
    """Test the sidebar widget rendering function."""

    def setUp(self):
        _mock_st.reset_mock()
        _mock_st.session_state = {}

    def _get_sidebar_html(self):
        """Return the HTML string of the sidebar card from st.markdown calls."""
        for call in _mock_st.markdown.call_args_list:
            if call[0] and '<div class="joseph-sidebar-container">' in call[0][0]:
                return call[0][0]
        return ""

    def test_callable(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        self.assertTrue(callable(render_joseph_sidebar_widget))

    def test_does_not_raise(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        # Should not raise regardless of brain availability
        render_joseph_sidebar_widget()

    def test_calls_markdown(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        # At least one markdown call should contain the sidebar container
        self.assertTrue(len(self._get_sidebar_html()) > 0)

    def test_sidebar_html_contains_container(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertIn("joseph-sidebar-container", self._get_sidebar_html())

    def test_sidebar_html_contains_pulse_dot(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertIn("joseph-pulse-dot", self._get_sidebar_html())

    def test_sidebar_html_contains_ambient_text(self):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertIn("joseph-ambient-text", self._get_sidebar_html())

    @patch("utils.joseph_widget.get_joseph_avatar_b64", return_value="FAKE_B64")
    def test_avatar_image_rendered(self, mock_avatar):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        html = self._get_sidebar_html()
        self.assertIn("joseph-sidebar-avatar", html)
        self.assertIn("FAKE_B64", html)

    @patch("utils.joseph_widget.get_joseph_avatar_b64", return_value="")
    def test_fallback_emoji_when_no_avatar(self, mock_avatar):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertIn("🎙️", self._get_sidebar_html())

    @patch("utils.joseph_widget.joseph_ambient_line", return_value="TEST LINE")
    @patch("utils.joseph_widget.joseph_get_ambient_context", return_value=("idle", {}))
    def test_ambient_line_rendered(self, mock_ctx, mock_line):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertIn("TEST LINE", self._get_sidebar_html())

    @patch("utils.joseph_widget.joseph_ambient_line", return_value="")
    @patch("utils.joseph_widget.joseph_get_ambient_context", return_value=("idle", {}))
    def test_default_ambient_when_empty(self, mock_ctx, mock_line):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertIn("ALWAYS watching", self._get_sidebar_html())

    @patch("utils.joseph_widget.joseph_get_track_record",
           return_value={"total": 10, "wins": 7, "losses": 3,
                         "roi_estimate": 12.5})
    def test_track_record_shown(self, mock_record):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        html = self._get_sidebar_html()
        self.assertIn("7W-3L", html)
        self.assertIn("+12.5%", html)

    @patch("utils.joseph_widget.joseph_get_track_record",
           return_value={"total": 0, "wins": 0, "losses": 0,
                         "roi_estimate": 0.0})
    def test_no_track_record_when_zero(self, mock_record):
        from utils.joseph_widget import render_joseph_sidebar_widget
        render_joseph_sidebar_widget()
        self.assertNotIn("📊", self._get_sidebar_html())

    def test_html_escaping_ambient(self):
        """Ambient text must be HTML-escaped to prevent injection."""
        with patch("utils.joseph_widget.joseph_ambient_line",
                   return_value="<script>alert(1)</script>"):
            with patch("utils.joseph_widget.joseph_get_ambient_context",
                       return_value=("idle", {})):
                from utils.joseph_widget import render_joseph_sidebar_widget
                render_joseph_sidebar_widget()
                html = self._get_sidebar_html()
                self.assertNotIn("<script>", html)
                self.assertIn("&lt;script&gt;", html)


# ============================================================
# SECTION 5: inject_joseph_inline_commentary()
# ============================================================

class TestInjectJosephInlineCommentary(unittest.TestCase):
    """Test inline commentary injection."""

    def setUp(self):
        _mock_st.reset_mock()
        _mock_st.session_state = {}

    def test_callable(self):
        from utils.joseph_widget import inject_joseph_inline_commentary
        self.assertTrue(callable(inject_joseph_inline_commentary))

    def test_noop_on_empty_results(self):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([])
        _mock_st.markdown.assert_not_called()

    def test_noop_on_none_results(self):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary(None)
        # No inline card div should be rendered
        calls = [c for c in _mock_st.markdown.call_args_list
                 if c[0] and '<div class="joseph-inline-card">' in c[0][0]]
        self.assertEqual(len(calls), 0)

    @patch("utils.joseph_widget.joseph_commentary", return_value="HOT TAKE")
    def test_renders_inline_card(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "LeBron"}])
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(len(calls) > 0)

    @patch("utils.joseph_widget.joseph_commentary", return_value="SMASH IT")
    def test_inline_card_contains_label(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "Steph"}])
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("Joseph M. Smith" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="COMMENTARY")
    def test_inline_card_contains_commentary(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "Jokic"}])
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("COMMENTARY" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="SMASH")
    def test_verdict_smash_class(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary(
            [{"player": "LeBron", "verdict": "SMASH"}]
        )
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("joseph-widget-verdict-smash" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="LEAN")
    def test_verdict_lean_class(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary(
            [{"player": "Steph", "verdict": "LEAN"}]
        )
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("joseph-widget-verdict-lean" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="FADE")
    def test_verdict_fade_class(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary(
            [{"player": "Luka", "verdict": "FADE"}]
        )
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("joseph-widget-verdict-fade" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="NO VERDICT")
    def test_no_verdict_class_when_missing(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "Giannis"}])
        # Only check calls that render the actual inline card div (not CSS)
        calls = [c for c in _mock_st.markdown.call_args_list
                 if c[0] and '<div class="joseph-inline-card">' in c[0][0]]
        for c in calls:
            html = c[0][0]
            self.assertNotIn("joseph-widget-verdict-smash", html)
            self.assertNotIn("joseph-widget-verdict-lean", html)
            self.assertNotIn("joseph-widget-verdict-fade", html)

    @patch("utils.joseph_widget.joseph_commentary", return_value="")
    def test_no_render_when_empty_commentary(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "Test"}])
        # Only count calls that render the actual inline card div (not CSS)
        calls = [c for c in _mock_st.markdown.call_args_list
                 if c[0] and '<div class="joseph-inline-card">' in c[0][0]]
        self.assertEqual(len(calls), 0)

    @patch("utils.joseph_widget.joseph_commentary",
           return_value="<script>bad</script>")
    def test_html_escaping_commentary(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "Test"}])
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        for c in calls:
            self.assertNotIn("<script>bad</script>", str(c))

    @patch("utils.joseph_widget.joseph_commentary", return_value="TAKE")
    @patch("utils.joseph_widget.get_joseph_avatar_b64", return_value="B64IMG")
    def test_inline_avatar_rendered(self, mock_av, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "AD"}])
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("joseph-inline-avatar" in str(c) for c in calls))
        self.assertTrue(any("B64IMG" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="TAKE")
    @patch("utils.joseph_widget.get_joseph_avatar_b64", return_value="")
    def test_inline_emoji_fallback(self, mock_av, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "KD"}])
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("🎙️" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="TAKE")
    def test_default_context_type(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "Test"}])
        mock_comm.assert_called_with([{"player": "Test"}], "analysis_results")

    @patch("utils.joseph_widget.joseph_commentary", return_value="TAKE")
    def test_custom_context_type(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary([{"player": "T"}], "entry_built")
        mock_comm.assert_called_with([{"player": "T"}], "entry_built")

    @patch("utils.joseph_widget.joseph_commentary", return_value="STAY")
    def test_verdict_stay_away_uses_fade_class(self, mock_comm):
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary(
            [{"player": "X", "verdict": "STAY_AWAY"}]
        )
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("joseph-widget-verdict-fade" in str(c) for c in calls))

    @patch("utils.joseph_widget.joseph_commentary", return_value="TAKE")
    def test_joseph_verdict_key_fallback(self, mock_comm):
        """Should check joseph_verdict key when verdict is missing."""
        from utils.joseph_widget import inject_joseph_inline_commentary
        inject_joseph_inline_commentary(
            [{"player": "Z", "joseph_verdict": "SMASH"}]
        )
        calls = [c for c in _mock_st.markdown.call_args_list
                 if "joseph-inline-card" in str(c)]
        self.assertTrue(any("joseph-widget-verdict-smash" in str(c) for c in calls))


# ============================================================
# SECTION 6: Availability flags
# ============================================================

class TestAvailabilityFlags(unittest.TestCase):
    """Verify the module exposes availability flags."""

    def test_brain_available_flag(self):
        import utils.joseph_widget as w
        self.assertIsInstance(w._BRAIN_AVAILABLE, bool)

    def test_avatar_available_flag(self):
        import utils.joseph_widget as w
        self.assertIsInstance(w._AVATAR_AVAILABLE, bool)

    def test_bets_available_flag(self):
        import utils.joseph_widget as w
        self.assertIsInstance(w._BETS_AVAILABLE, bool)

    def test_auth_available_flag(self):
        import utils.joseph_widget as w
        self.assertIsInstance(w._AUTH_AVAILABLE, bool)


if __name__ == "__main__":
    unittest.main()
