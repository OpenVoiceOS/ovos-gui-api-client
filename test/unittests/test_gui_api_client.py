"""Unit tests for ovos_gui_api_client"""

import pytest
from unittest.mock import MagicMock, patch

from ovos_gui_api_client import (
    GUIInterface,
    PageTemplates,
    FillMode,
    ListItem,
    GridItem,
    SelectItem,
)


class FakeBus:
    """Fake message bus for testing."""

    def __init__(self):
        self.emitted_messages = []
        self.handlers = {}

    def emit(self, message):
        self.emitted_messages.append(message)

    def on(self, event, handler):
        self.handlers[event] = handler

    def remove(self, event, handler):
        self.handlers.pop(event, None)


@pytest.fixture
def fake_bus():
    return FakeBus()


@pytest.fixture
def gui_interface(fake_bus):
    return GUIInterface("test.skill", bus=fake_bus)


class TestListItem:
    def test_as_dict_full(self):
        item = ListItem(title="Title", subtitle="Subtitle", image="image.jpg")
        result = item.as_dict()
        assert result == {
            "title": "Title",
            "subtitle": "Subtitle",
            "image": "image.jpg",
        }

    def test_as_dict_partial(self):
        item = ListItem(title="Title")
        result = item.as_dict()
        assert result == {"title": "Title"}

    def test_as_dict_excludes_none(self):
        item = ListItem(title="Title", subtitle=None, image=None)
        result = item.as_dict()
        assert result == {"title": "Title"}


class TestGridItem:
    def test_as_dict_full(self):
        item = GridItem(image="image.jpg", title="Title")
        result = item.as_dict()
        assert result == {"image": "image.jpg", "title": "Title"}

    def test_as_dict_partial(self):
        item = GridItem(image="image.jpg")
        result = item.as_dict()
        assert result == {"image": "image.jpg"}

    def test_as_dict_excludes_none(self):
        item = GridItem(image="image.jpg", title=None)
        result = item.as_dict()
        assert result == {"image": "image.jpg"}


class TestSelectItem:
    def test_as_dict(self):
        item = SelectItem(label="Option 1", value="option1")
        result = item.as_dict()
        assert result == {"label": "Option 1", "value": "option1"}


class TestFillMode:
    def test_values(self):
        assert FillMode.FIT.value == "fit"
        assert FillMode.CROP.value == "crop"
        assert FillMode.STRETCH.value == "stretch"


class TestPageTemplates:
    def test_values(self):
        assert PageTemplates.TEXT.value == "SYSTEM_text"
        assert PageTemplates.IMAGE.value == "SYSTEM_image"
        assert PageTemplates.LIST.value == "SYSTEM_list"

    def test_enum_members(self):
        assert "SYSTEM_idle" in PageTemplates.IDLE.value
        assert "SYSTEM_weather" in PageTemplates.WEATHER.value


class TestGUIInterfaceInit:
    def test_init_with_bus(self, fake_bus):
        gui = GUIInterface("test.skill", bus=fake_bus)
        assert gui.skill_id == "test.skill"
        assert gui.bus is fake_bus

    def test_init_without_bus(self):
        gui = GUIInterface("test.skill")
        assert gui.skill_id == "test.skill"
        assert gui.bus is None

    def test_default_config(self):
        with patch("ovos_gui_api_client.Configuration") as mock_config:
            mock_config.return_value.get.return_value = {}
            gui = GUIInterface("test.skill")
            assert gui.config == {}

    def test_custom_config(self):
        gui = GUIInterface("test.skill", config={"custom": "value"})
        assert gui.config == {"custom": "value"}


class TestGUIDictAccess:
    def test_set_item(self, gui_interface):
        gui_interface["key1"] = "value1"
        assert gui_interface["key1"] == "value1"

    def test_get_item(self, gui_interface):
        gui_interface["key1"] = "value1"
        assert gui_interface.get("key1") == "value1"

    def test_get_item_default(self, gui_interface):
        assert gui_interface.get("nonexistent", "default") == "default"

    def test_contains(self, gui_interface):
        gui_interface["key1"] = "value1"
        assert "key1" in gui_interface
        assert "key2" not in gui_interface

    def test_len(self, gui_interface):
        gui_interface["key1"] = "value1"
        gui_interface["key2"] = "value2"
        assert len(gui_interface) == 2

    def test_keys_values_items(self, gui_interface):
        gui_interface["key1"] = "value1"
        gui_interface["key2"] = "value2"
        assert list(gui_interface.keys()) == ["key1", "key2"]
        assert list(gui_interface.values()) == ["value1", "value2"]
        assert list(gui_interface.items()) == [("key1", "value1"), ("key2", "value2")]


class TestGUIDictUpdate:
    def test_update(self, gui_interface):
        gui_interface.update({"key1": "value1", "key2": "value2"})
        assert gui_interface["key1"] == "value1"
        assert gui_interface["key2"] == "value2"

    def test_update_existing_key(self, gui_interface):
        gui_interface["key1"] = "value1"
        gui_interface.update({"key1": "new_value"})
        assert gui_interface["key1"] == "new_value"


class TestShowText:
    def test_show_text_no_bus(self):
        gui = GUIInterface("test.skill")
        with pytest.raises(RuntimeError, match="Bus not set"):
            gui.show_text("Hello")

    def test_show_text_emits_message(self, gui_interface, fake_bus):
        gui_interface.show_text("Hello", title="Greeting")
        assert len(fake_bus.emitted_messages) == 2

    def test_show_text_sets_session_data(self, gui_interface):
        gui_interface.show_text("Hello", title="Greeting")
        assert gui_interface["text"] == "Hello"
        assert gui_interface["title"] == "Greeting"


class TestShowImage:
    def test_show_image_url(self, gui_interface):
        gui_interface.show_image("https://example.com/image.png")
        assert gui_interface["image"] == "https://example.com/image.png"

    def test_show_image_fill_mode(self, gui_interface):
        gui_interface.show_image("https://example.com/image.png", fill=FillMode.CROP)
        assert gui_interface["fill"] == "crop"

    def test_show_image_caption_title(self, gui_interface):
        gui_interface.show_image(
            "https://example.com/image.png", caption="A caption", title="Image Title"
        )
        assert gui_interface["caption"] == "A caption"
        assert gui_interface["title"] == "Image Title"


class TestShowList:
    def test_show_list_with_list_items(self, gui_interface):
        items = [
            ListItem(title="Item 1", subtitle="Sub 1", image="img1.jpg"),
            ListItem(title="Item 2", subtitle="Sub 2", image="img2.jpg"),
        ]
        gui_interface.show_list(items, title="My List")
        assert gui_interface["title"] == "My List"
        assert len(gui_interface["items"]) == 2

    def test_show_list_with_dicts(self, gui_interface):
        items = [{"title": "Item 1"}, {"title": "Item 2"}]
        gui_interface.show_list(items)
        assert len(gui_interface["items"]) == 2


class TestShowGrid:
    def test_show_grid_with_grid_items(self, gui_interface):
        items = [
            GridItem(image="img1.jpg", title="Tile 1"),
            GridItem(image="img2.jpg", title="Tile 2"),
        ]
        gui_interface.show_grid(items, title="My Grid")
        assert gui_interface["title"] == "My Grid"
        assert len(gui_interface["items"]) == 2


class TestShowWeather:
    def test_show_weather(self, gui_interface):
        gui_interface.show_weather(
            current_temp=22,
            min_temp=18,
            max_temp=25,
            condition="Sunny",
            icon="sunny.png",
            location="Berlin",
        )
        assert gui_interface["current_temp"] == 22
        assert gui_interface["min_temp"] == 18
        assert gui_interface["max_temp"] == 25
        assert gui_interface["condition"] == "Sunny"
        assert gui_interface["icon"] == "sunny.png"
        assert gui_interface["location"] == "Berlin"


class TestShowTable:
    def test_show_table_valid(self, gui_interface):
        columns = ["Name", "Age"]
        rows = [["Alice", "30"], ["Bob", "25"]]
        gui_interface.show_table(columns, rows)
        assert gui_interface["columns"] == columns
        assert gui_interface["rows"] == rows

    def test_show_table_invalid_row_length(self, gui_interface):
        columns = ["Name", "Age"]
        rows = [["Alice", "30", "extra"]]
        with pytest.raises(ValueError, match="Row 0 has 3 value"):
            gui_interface.show_table(columns, rows)


class TestShowAudioPlayer:
    def test_show_audio_player(self, gui_interface):
        gui_interface.show_audio_player(
            title="Song Title",
            artist="Artist Name",
            album="Album Name",
            image="cover.jpg",
            position=30.0,
            duration=180.0,
            playing=True,
        )
        assert gui_interface["title"] == "Song Title"
        assert gui_interface["artist"] == "Artist Name"
        assert gui_interface["album"] == "Album Name"
        assert gui_interface["position"] == 30.0
        assert gui_interface["duration"] == 180.0
        assert gui_interface["playing"] is True


class TestShowVideoPlayer:
    def test_show_video_player(self, gui_interface):
        gui_interface.show_video_player(
            uri="https://example.com/video.mp4", title="Video Title", playing=True
        )
        assert gui_interface["uri"] == "https://example.com/video.mp4"
        assert gui_interface["title"] == "Video Title"
        assert gui_interface["playing"] is True


class TestShowMediaPlayer:
    def test_show_media_player_minimal(self, gui_interface):
        gui_interface.show_media_player()
        assert gui_interface["ocp_title"] == ""
        assert gui_interface["ocp_playback_state"] == "playing"

    def test_show_media_player_full(self, gui_interface):
        now_playing = {
            "title": "Song",
            "artist": "Artist",
            "album": "Album",
            "image": "cover.jpg",
            "uri": "spotify:track:123",
            "position": 30000,
            "duration": 180000,
        }
        playlist = [
            {
                "title": "Song 1",
                "artist": "A1",
                "image": "i1.jpg",
                "uri": "s:1",
                "duration": 120000,
            },
            {
                "title": "Song 2",
                "artist": "A2",
                "image": "i2.jpg",
                "uri": "s:2",
                "duration": 150000,
            },
        ]
        search_results = [
            {
                "title": "Result 1",
                "artist": "R1",
                "image": "r1.jpg",
                "uri": "r:1",
                "skill_id": "search.skill",
                "match_confidence": 0.9,
            }
        ]
        gui_interface.show_media_player(
            now_playing=now_playing,
            playlist=playlist,
            search_results=search_results,
            state="playing",
        )
        assert gui_interface["ocp_title"] == "Song"
        assert gui_interface["ocp_artist"] == "Artist"
        assert gui_interface["ocp_playlist"] == playlist
        assert gui_interface["ocp_search_results"] == search_results
        assert gui_interface["ocp_playback_state"] == "playing"


class TestShowTimer:
    def test_show_timer(self, gui_interface):
        import time

        end = time.time() + 300
        gui_interface.show_timer(end_time=end, label="Timer", count_up=False)
        assert gui_interface["end_time"] == end
        assert gui_interface["label"] == "Timer"
        assert gui_interface["count_up"] is False


class TestShowClock:
    def test_show_clock(self, gui_interface):
        gui_interface.show_clock()
        assert gui_interface.page == PageTemplates.CLOCK


class TestShowFace:
    def test_show_face_awake(self, gui_interface):
        gui_interface.show_face(awake=True)
        assert gui_interface["sleeping"] is False

    def test_show_face_sleeping(self, gui_interface):
        gui_interface.show_face(awake=False)
        assert gui_interface["sleeping"] is True


class TestShowMap:
    def test_show_map(self, gui_interface):
        gui_interface.show_map(
            latitude=52.52, longitude=13.405, zoom=12, label="Berlin"
        )
        assert gui_interface["latitude"] == 52.52
        assert gui_interface["longitude"] == 13.405
        assert gui_interface["zoom"] == 12
        assert gui_interface["label"] == "Berlin"


class TestGUIAvailability:
    def test_gui_disabled_default(self, gui_interface):
        with patch("ovos_gui_api_client.Configuration") as mock_config:
            mock_config.return_value.get.return_value = {}
            gui = GUIInterface("test.skill", bus=FakeBus())
            assert gui.gui_disabled is False

    def test_gui_disabled_true(self):
        with patch("ovos_gui_api_client.Configuration") as mock_config:
            mock_config.return_value.get.return_value = {"disable_gui": True}
            gui = GUIInterface("test.skill", config={"disable_gui": True})
            assert gui.gui_disabled is True


class TestLifecycle:
    def test_clear(self, gui_interface, fake_bus):
        gui_interface["key1"] = "value1"
        gui_interface._pages = [PageTemplates.TEXT]
        gui_interface.current_page_idx = 0
        gui_interface.clear()
        assert len(gui_interface._session_data) == 0
        assert len(gui_interface._pages) == 0

    def test_release(self, gui_interface, fake_bus):
        gui_interface.release()
        assert len(fake_bus.emitted_messages) >= 1

    def test_shutdown(self, gui_interface, fake_bus):
        gui_interface.shutdown()
        assert len(fake_bus.handlers) == 0


class TestPageProperty:
    def test_page_no_pages(self, gui_interface):
        assert gui_interface.page is None

    def test_page_with_pages(self, gui_interface):
        gui_interface._pages = [PageTemplates.TEXT, PageTemplates.IMAGE]
        gui_interface.current_page_idx = 0
        assert gui_interface.page == PageTemplates.TEXT

    def test_pages_property(self, gui_interface):
        gui_interface._pages = [PageTemplates.TEXT, PageTemplates.IMAGE]
        assert gui_interface.pages == [PageTemplates.TEXT, PageTemplates.IMAGE]


class TestOCPTemplates:
    def test_show_ocp_now_playing(self, gui_interface):
        gui_interface.show_ocp_now_playing(
            title="Track",
            artist="Artist",
            image="cover.jpg",
            uri="spotify:track:123",
            media_type="audio",
            position=30000,
            duration=180000,
            playing=True,
        )
        assert gui_interface["title"] == "Track"
        assert gui_interface["media_type"] == "audio"
        assert gui_interface["playing"] is True

    def test_show_ocp_search(self, gui_interface):
        results = [{"title": "Result 1", "uri": "r:1"}]
        gui_interface.show_ocp_search(results=results, search_term="test")
        assert gui_interface["results"] == results
        assert gui_interface["search_term"] == "test"

    def test_show_ocp_playlist(self, gui_interface):
        tracks = [
            {"title": "Track 1", "uri": "t:1"},
            {"title": "Track 2", "uri": "t:2"},
        ]
        gui_interface.show_ocp_playlist(tracks=tracks, current_index=1)
        assert gui_interface["tracks"] == tracks
        assert gui_interface["current_index"] == 1
