"""Unit tests for ovos_gui_api_client.GUIInterface and PageTemplates."""
import time
import unittest
from unittest.mock import MagicMock

from ovos_gui_api_client import (
    GUIInterface,
    PageTemplates,
    FillMode,
    ListItem,
    GridItem,
    SelectItem,
)
from ovos_gui_api_client import _GUIDict
from ovos_bus_client.message import Message


class FakeBus:
    """A minimal message-bus stand-in that records every emitted Message."""

    def __init__(self):
        self.emitted = []
        self.handlers = {}

    def emit(self, message):
        self.emitted.append(message)

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def remove(self, event, handler):
        if event in self.handlers and handler in self.handlers[event]:
            self.handlers[event].remove(handler)

    # --- helpers for assertions -------------------------------------
    def messages(self, msg_type):
        return [m for m in self.emitted if m.msg_type == msg_type]

    def last(self, msg_type):
        msgs = self.messages(msg_type)
        return msgs[-1] if msgs else None

    def reset(self):
        self.emitted = []


def make_gui(skill_id="test.skill"):
    bus = FakeBus()
    gui = GUIInterface(skill_id, bus=bus, config={})
    return gui, bus


# ---------------------------------------------------------------------------
# PageTemplates registry
# ---------------------------------------------------------------------------

class TestPageTemplates(unittest.TestCase):

    EXPECTED = {
        "IDLE": "SYSTEM_idle",
        "LOADING": "SYSTEM_loading",
        "STATUS": "SYSTEM_status",
        "ERROR": "SYSTEM_error",
        "TEXT": "SYSTEM_text",
        "IMAGE": "SYSTEM_image",
        "ANIMATED_IMAGE": "SYSTEM_animated_image",
        "LIST": "SYSTEM_list",
        "GRID": "SYSTEM_grid",
        "TABLE": "SYSTEM_table",
        "HTML": "SYSTEM_html",
        "URL": "SYSTEM_url",
        "MEDIA_PLAYER": "SYSTEM_media_player",
        "CLOCK": "SYSTEM_clock",
        "TIMER": "SYSTEM_timer",
        "WEATHER": "SYSTEM_weather",
        "MAP": "SYSTEM_map",
        "CONFIRM": "SYSTEM_confirm",
        "SELECT": "SYSTEM_select",
        "FACE": "SYSTEM_face",
    }

    def test_all_members_present(self):
        names = {m.name for m in PageTemplates}
        self.assertEqual(names, set(self.EXPECTED.keys()))

    def test_member_values(self):
        for name, value in self.EXPECTED.items():
            self.assertEqual(getattr(PageTemplates, name).value, value)

    def test_all_values_are_system_prefixed(self):
        for member in PageTemplates:
            self.assertTrue(member.value.startswith("SYSTEM_"))

    def test_count(self):
        self.assertEqual(len(list(PageTemplates)), 20)

    def test_is_str_enum(self):
        self.assertEqual(PageTemplates.TEXT, "SYSTEM_text")


# ---------------------------------------------------------------------------
# Helper: drive a show_* method and inspect emissions
# ---------------------------------------------------------------------------

class ShowMixin:

    def page_show(self, bus):
        msg = bus.last("gui.page.show")
        self.assertIsNotNone(msg, "expected a gui.page.show emission")
        return msg

    def assert_page(self, bus, template):
        msg = self.page_show(bus)
        self.assertEqual(msg.data["page_names"], [template])
        # page name carried is the SYSTEM_* enum value
        self.assertEqual(msg.data["page_names"][0].value, template.value)
        self.assertEqual(msg.data["__from"], "test.skill")
        self.assertIn("__idle", msg.data)
        self.assertIn("__animations", msg.data)

    def value_set_data(self, bus):
        msg = bus.last("gui.value.set")
        self.assertIsNotNone(msg, "expected a gui.value.set emission")
        return msg.data


# ---------------------------------------------------------------------------
# show_* methods: session-data writes + gui.page.show emission
# ---------------------------------------------------------------------------

class TestShowMethods(unittest.TestCase, ShowMixin):

    def test_show_text(self):
        gui, bus = make_gui()
        gui.show_text("hello", title="Greeting")
        self.assertEqual(gui["text"], "hello")
        self.assertEqual(gui["title"], "Greeting")
        self.assert_page(bus, PageTemplates.TEXT)
        data = self.value_set_data(bus)
        self.assertEqual(data["text"], "hello")
        self.assertEqual(data["title"], "Greeting")

    def test_show_loading(self):
        gui, bus = make_gui()
        gui.show_loading("please wait")
        self.assertEqual(gui["label"], "please wait")
        self.assert_page(bus, PageTemplates.LOADING)

    def test_show_status(self):
        gui, bus = make_gui()
        gui.show_status("done", success=True)
        self.assertEqual(gui["success"], True)
        self.assertEqual(gui["label"], "done")
        self.assert_page(bus, PageTemplates.STATUS)

    def test_show_error(self):
        gui, bus = make_gui()
        gui.show_error("boom", detail="stacktrace")
        self.assertEqual(gui["label"], "boom")
        self.assertEqual(gui["detail"], "stacktrace")
        self.assert_page(bus, PageTemplates.ERROR)

    def test_show_face_awake(self):
        gui, bus = make_gui()
        gui.show_face(awake=True)
        self.assertEqual(gui["sleeping"], False)
        self.assert_page(bus, PageTemplates.FACE)

    def test_show_face_sleeping(self):
        gui, bus = make_gui()
        gui.show_face(awake=False)
        self.assertEqual(gui["sleeping"], True)
        self.assert_page(bus, PageTemplates.FACE)

    def test_show_image_remote(self):
        gui, bus = make_gui()
        gui.show_image("https://example.com/x.png", caption="cap",
                       title="t", fill=FillMode.CROP, background_color="#000")
        self.assertEqual(gui["image"], "https://example.com/x.png")
        self.assertEqual(gui["caption"], "cap")
        self.assertEqual(gui["title"], "t")
        self.assertEqual(gui["fill"], "crop")
        self.assertEqual(gui["background_color"], "#000")
        self.assert_page(bus, PageTemplates.IMAGE)

    def test_show_image_missing_local_is_noop(self):
        gui, bus = make_gui()
        gui.show_image("/nonexistent/path/to/image.png")
        # no page should be shown for a missing local file
        self.assertIsNone(bus.last("gui.page.show"))

    def test_show_image_animated_flag(self):
        gui, bus = make_gui()
        gui.show_image("https://example.com/x.gif", animated=True)
        self.assert_page(bus, PageTemplates.ANIMATED_IMAGE)

    def test_show_animated_image(self):
        gui, bus = make_gui()
        gui.show_animated_image("https://example.com/x.gif")
        self.assert_page(bus, PageTemplates.ANIMATED_IMAGE)

    def test_show_html(self):
        gui, bus = make_gui()
        gui.show_html("<b>hi</b>", resource_url="https://example.com")
        self.assertEqual(gui["html"], "<b>hi</b>")
        self.assertEqual(gui["resource_url"], "https://example.com")
        self.assert_page(bus, PageTemplates.HTML)

    def test_show_url(self):
        gui, bus = make_gui()
        gui.show_url("https://example.com")
        self.assertEqual(gui["url"], "https://example.com")
        self.assert_page(bus, PageTemplates.URL)

    def test_show_weather(self):
        gui, bus = make_gui()
        gui.show_weather(20, 10, 25, "Sunny", icon="ic", location="Berlin")
        self.assertEqual(gui["current_temp"], 20)
        self.assertEqual(gui["min_temp"], 10)
        self.assertEqual(gui["max_temp"], 25)
        self.assertEqual(gui["condition"], "Sunny")
        self.assertEqual(gui["icon"], "ic")
        self.assertEqual(gui["location"], "Berlin")
        self.assert_page(bus, PageTemplates.WEATHER)

    def test_show_list_with_dataclass(self):
        gui, bus = make_gui()
        gui.show_list([ListItem("a", subtitle="sub", image="img"),
                       {"title": "b"}], title="My list")
        self.assertEqual(gui["title"], "My list")
        self.assertEqual(gui["items"],
                         [{"title": "a", "subtitle": "sub", "image": "img"},
                          {"title": "b"}])
        self.assert_page(bus, PageTemplates.LIST)

    def test_show_grid(self):
        gui, bus = make_gui()
        gui.show_grid([GridItem("img1", title="t1"), {"image": "img2"}],
                      title="Albums")
        self.assertEqual(gui["items"],
                         [{"image": "img1", "title": "t1"},
                          {"image": "img2"}])
        self.assert_page(bus, PageTemplates.GRID)

    def test_show_table(self):
        gui, bus = make_gui()
        gui.show_table(["A", "B"], [[1, 2], [3, 4]], title="T")
        self.assertEqual(gui["columns"], ["A", "B"])
        self.assertEqual(gui["rows"], [[1, 2], [3, 4]])
        self.assert_page(bus, PageTemplates.TABLE)

    def test_show_table_row_mismatch_raises(self):
        gui, _ = make_gui()
        with self.assertRaises(ValueError):
            gui.show_table(["A", "B"], [[1]])

    def test_show_media_player(self):
        gui, bus = make_gui()
        gui.show_media_player(
            now_playing={"title": "Song", "artist": "Artist", "album": "Album",
                         "image": "art", "uri": "u", "position": 1,
                         "duration": 200},
            playlist=[{"uri": "u"}, {"uri": "u2"}],
            state="playing",
        )
        self.assertEqual(gui["ocp_title"], "Song")
        self.assertEqual(gui["ocp_artist"], "Artist")
        self.assertEqual(gui["ocp_album"], "Album")
        self.assertEqual(gui["ocp_image"], "art")
        self.assertEqual(gui["ocp_position"], 1)
        self.assertEqual(gui["ocp_duration"], 200)
        self.assertEqual(gui["ocp_playback_state"], "playing")
        self.assertEqual(gui["ocp_playlist_position"], 0)
        self.assert_page(bus, PageTemplates.MEDIA_PLAYER)

    def test_show_clock(self):
        gui, bus = make_gui()
        gui.show_clock()
        self.assert_page(bus, PageTemplates.CLOCK)

    def test_show_timer(self):
        gui, bus = make_gui()
        end = time.time() + 60
        gui.show_timer(end, label="Pasta", count_up=False)
        self.assertEqual(gui["end_time"], end)
        self.assertEqual(gui["label"], "Pasta")
        self.assertEqual(gui["count_up"], False)
        self.assert_page(bus, PageTemplates.TIMER)

    def test_show_map(self):
        gui, bus = make_gui()
        gui.show_map(52.5, 13.4, zoom=10, label="Berlin")
        self.assertEqual(gui["latitude"], 52.5)
        self.assertEqual(gui["longitude"], 13.4)
        self.assertEqual(gui["zoom"], 10)
        self.assertEqual(gui["label"], "Berlin")
        self.assert_page(bus, PageTemplates.MAP)

    def test_show_confirm(self):
        gui, bus = make_gui()
        gui.show_confirm("Are you sure?")
        self.assertEqual(gui["question"], "Are you sure?")
        self.assert_page(bus, PageTemplates.CONFIRM)

    def test_show_select(self):
        gui, bus = make_gui()
        gui.show_select([SelectItem("One", 1), {"label": "Two", "value": 2}],
                        prompt="Pick")
        self.assertEqual(gui["prompt"], "Pick")
        self.assertEqual(gui["items"],
                         [{"label": "One", "value": 1},
                          {"label": "Two", "value": 2}])
        self.assert_page(bus, PageTemplates.SELECT)

    def test_every_template_has_a_show_path(self):
        """Every non-IDLE template is reachable through a show_* call."""
        cases = [
            (PageTemplates.LOADING, lambda g: g.show_loading()),
            (PageTemplates.STATUS, lambda g: g.show_status("x", True)),
            (PageTemplates.ERROR, lambda g: g.show_error("x")),
            (PageTemplates.TEXT, lambda g: g.show_text("x")),
            (PageTemplates.IMAGE, lambda g: g.show_image("https://e/x.png")),
            (PageTemplates.ANIMATED_IMAGE,
             lambda g: g.show_animated_image("https://e/x.gif")),
            (PageTemplates.LIST, lambda g: g.show_list([{"title": "x"}])),
            (PageTemplates.GRID, lambda g: g.show_grid([{"image": "x"}])),
            (PageTemplates.TABLE, lambda g: g.show_table(["A"], [[1]])),
            (PageTemplates.HTML, lambda g: g.show_html("<b/>")),
            (PageTemplates.URL, lambda g: g.show_url("https://e")),
            (PageTemplates.MEDIA_PLAYER,
             lambda g: g.show_media_player(now_playing={"title": "s"})),
            (PageTemplates.CLOCK, lambda g: g.show_clock()),
            (PageTemplates.TIMER, lambda g: g.show_timer(time.time())),
            (PageTemplates.WEATHER,
             lambda g: g.show_weather(1, 0, 2, "x")),
            (PageTemplates.MAP, lambda g: g.show_map(0.0, 0.0)),
            (PageTemplates.CONFIRM, lambda g: g.show_confirm("q")),
            (PageTemplates.SELECT,
             lambda g: g.show_select([{"label": "a", "value": 1}])),
            (PageTemplates.FACE, lambda g: g.show_face()),
        ]
        seen = set()
        for template, call in cases:
            gui, bus = make_gui()
            call(gui)
            msg = bus.last("gui.page.show")
            self.assertIsNotNone(msg, f"{template} produced no page.show")
            self.assertEqual(msg.data["page_names"], [template])
            seen.add(template)
        # IDLE is reserved for the service, not a public show_* path
        self.assertEqual(seen, set(PageTemplates) - {PageTemplates.IDLE})


# ---------------------------------------------------------------------------
# Session-data sync: gui.value.set
# ---------------------------------------------------------------------------

class TestSessionData(unittest.TestCase, ShowMixin):

    def test_setitem_no_active_page_does_not_emit(self):
        gui, bus = make_gui()
        gui["temperature"] = 22
        self.assertEqual(gui["temperature"], 22)
        # no page active -> no sync emitted yet
        self.assertEqual(bus.messages("gui.value.set"), [])

    def test_setitem_with_active_page_emits_value_set(self):
        gui, bus = make_gui()
        gui.show_text("hi")  # activates a page
        bus.reset()
        gui["temperature"] = 22
        data = self.value_set_data(bus)
        self.assertEqual(data["temperature"], 22)
        self.assertEqual(data["__from"], "test.skill")

    def test_setitem_unchanged_value_is_noop(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        bus.reset()
        gui["text"] = "hi"  # same value already set by show_text
        self.assertEqual(bus.messages("gui.value.set"), [])

    def test_get_default(self):
        gui, _ = make_gui()
        self.assertIsNone(gui.get("missing"))
        self.assertEqual(gui.get("missing", "fallback"), "fallback")
        gui["k"] = "v"
        self.assertEqual(gui.get("k"), "v")

    def test_contains_len_keys(self):
        gui, _ = make_gui()
        gui["a"] = 1
        gui["b"] = 2
        self.assertIn("a", gui)
        self.assertNotIn("z", gui)
        self.assertEqual(len(gui), 2)
        self.assertEqual(set(gui.keys()), {"a", "b"})

    def test_update_batches_single_sync(self):
        gui, bus = make_gui()
        gui.show_text("hi")  # active page
        bus.reset()
        gui.update({"a": 1, "b": 2, "c": 3})
        sets = bus.messages("gui.value.set")
        self.assertEqual(len(sets), 1)
        data = sets[0].data
        self.assertEqual(data["a"], 1)
        self.assertEqual(data["b"], 2)
        self.assertEqual(data["c"], 3)

    def test_update_no_page_does_not_emit(self):
        gui, bus = make_gui()
        gui.update({"a": 1, "b": 2})
        self.assertEqual(bus.messages("gui.value.set"), [])
        self.assertEqual(gui["a"], 1)

    def test_update_no_changes_no_emit(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        gui.update({"x": 1})
        bus.reset()
        gui.update({"x": 1})  # unchanged
        self.assertEqual(bus.messages("gui.value.set"), [])


# ---------------------------------------------------------------------------
# _GUIDict nested mutation propagation
# ---------------------------------------------------------------------------

class TestGUIDict(unittest.TestCase, ShowMixin):

    def test_dict_value_becomes_guidict(self):
        gui, _ = make_gui()
        gui["info"] = {"city": "Berlin", "temp": 12}
        self.assertIsInstance(gui["info"], _GUIDict)

    def test_nested_setitem_triggers_sync(self):
        gui, bus = make_gui()
        gui.show_text("hi")  # active page so syncs are emitted
        gui["info"] = {"city": "Berlin", "temp": 12}
        bus.reset()
        gui["info"]["temp"] = 13
        data = self.value_set_data(bus)
        self.assertEqual(data["info"]["temp"], 13)

    def test_nested_unchanged_value_no_sync(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        gui["info"] = {"temp": 12}
        bus.reset()
        gui["info"]["temp"] = 12  # unchanged
        self.assertEqual(bus.messages("gui.value.set"), [])

    def test_guidict_update_single_sync(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        gui["info"] = {"a": 1}
        bus.reset()
        gui["info"].update({"a": 2, "b": 3})
        sets = bus.messages("gui.value.set")
        self.assertEqual(len(sets), 1)
        self.assertEqual(gui["info"]["a"], 2)
        self.assertEqual(gui["info"]["b"], 3)


# ---------------------------------------------------------------------------
# Reserved keys / message envelope
# ---------------------------------------------------------------------------

class TestReservedKeys(unittest.TestCase, ShowMixin):

    def test_value_set_carries_from_meta_key(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        data = self.value_set_data(bus)
        self.assertEqual(data["__from"], "test.skill")

    def test_page_show_carries_reserved_keys(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        msg = bus.last("gui.page.show")
        for key in ("__from", "__idle", "__animations"):
            self.assertIn(key, msg.data)

    def test_session_data_excludes_reserved_keys(self):
        """Reserved meta keys are envelope-only; user session data is clean."""
        gui, bus = make_gui()
        gui.show_text("hi")
        for key in ("__from", "__idle", "__animations"):
            self.assertNotIn(key, gui._session_data)

    def test_override_idle_propagates(self):
        gui, bus = make_gui()
        gui.show_text("hi", override_idle=30)
        msg = bus.last("gui.page.show")
        self.assertEqual(msg.data["__idle"], 30)


# ---------------------------------------------------------------------------
# Inbound set + callback
# ---------------------------------------------------------------------------

class TestInbound(unittest.TestCase, ShowMixin):

    def test_on_gui_set_updates_session_data(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        bus.reset()
        gui._on_gui_set(Message(f"{gui.skill_id}.set", {"answer": 42}))
        self.assertEqual(gui["answer"], 42)
        # echoes back a sync
        self.assertIsNotNone(bus.last("gui.value.set"))

    def test_on_gui_changed_callback_fires(self):
        gui, bus = make_gui()
        cb = MagicMock()
        gui.set_on_gui_changed(cb)
        gui._on_gui_set(Message(f"{gui.skill_id}.set", {"x": 1}))
        cb.assert_called_once()

    def test_default_handler_registered(self):
        gui, bus = make_gui()
        self.assertIn(f"{gui.skill_id}.set", bus.handlers)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle(unittest.TestCase):

    def test_clear_resets_state_and_emits(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        gui.clear()
        self.assertEqual(len(gui), 0)
        self.assertEqual(gui.pages, [])
        self.assertIsNone(gui.page)
        self.assertIsNotNone(bus.last("gui.clear.namespace"))

    def test_release_emits_screen_close(self):
        gui, bus = make_gui()
        gui.show_text("hi")
        gui.release()
        self.assertIsNotNone(bus.last("ovos.gui.screen.close"))

    def test_shutdown_removes_handlers(self):
        gui, bus = make_gui()
        gui.shutdown()
        self.assertEqual(gui._events, [])
        self.assertEqual(bus.handlers.get(f"{gui.skill_id}.set", []), [])

    def test_gui_disabled_suppresses_emissions(self):
        bus = FakeBus()
        gui = GUIInterface("test.skill", bus=bus, config={"disable_gui": True})
        gui.show_text("hi")
        self.assertEqual(bus.messages("gui.page.show"), [])
        self.assertEqual(bus.messages("gui.value.set"), [])

    def test_page_property_tracks_active(self):
        gui, _ = make_gui()
        self.assertIsNone(gui.page)
        gui.show_text("hi")
        self.assertEqual(gui.page, PageTemplates.TEXT)


# ---------------------------------------------------------------------------
# send_event / remove pages
# ---------------------------------------------------------------------------

class TestEventsAndPages(unittest.TestCase):

    def test_send_event(self):
        gui, bus = make_gui()
        gui.send_event("my_event", {"k": "v"})
        msg = bus.last("gui.event.send")
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data["event_name"], "my_event")
        self.assertEqual(msg.data["params"], {"k": "v"})
        self.assertEqual(msg.data["__from"], "test.skill")

    def test_remove_pages(self):
        gui, bus = make_gui()
        gui._remove_pages([PageTemplates.TEXT])
        msg = bus.last("gui.page.delete")
        self.assertIsNotNone(msg)
        self.assertEqual(msg.data["page_names"], [PageTemplates.TEXT])

    def test_remove_all_pages(self):
        gui, bus = make_gui()
        gui._remove_all_pages()
        msg = bus.last("gui.page.delete.all")
        self.assertIsNotNone(msg)

    def test_register_handler_prefixes_namespace(self):
        gui, bus = make_gui()
        handler = MagicMock()
        gui.register_handler("confirm.response", handler)
        self.assertIn("test.skill.confirm.response", bus.handlers)


if __name__ == "__main__":
    unittest.main()
