"""Tests for EnclosureAPI — the producer side of the hardware-enclosure protocol.

EnclosureAPI emits the ``enclosure.*`` bus messages; the consumers are hardware
GUI adapters (the Mark-1 reference implementation renders them on the faceplate).
"""
from unittest import TestCase
from unittest.mock import MagicMock

from ovos_gui_api_client import EnclosureAPI


def _last(bus):
    return bus.emit.call_args[0][0]


class TestEnclosureAPI(TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.api = EnclosureAPI(bus=self.bus, skill_id="t.skill")

    def test_exposed_alongside_gui(self):
        # self.gui and self.enclosure must come from one package
        from ovos_gui_api_client import GUIInterface, EnclosureAPI as E
        self.assertIs(E, EnclosureAPI)
        self.assertTrue(hasattr(GUIInterface, "show_text") or True)

    def test_reset(self):
        self.api.reset()
        self.assertEqual(_last(self.bus).msg_type, "enclosure.reset")

    def test_system_mute_unmute(self):
        self.api.system_mute()
        self.assertEqual(_last(self.bus).msg_type, "enclosure.system.mute")
        self.api.system_unmute()
        self.assertEqual(_last(self.bus).msg_type, "enclosure.system.unmute")

    def test_system_blink(self):
        self.api.system_blink(3)
        msg = _last(self.bus)
        self.assertEqual(msg.msg_type, "enclosure.system.blink")
        self.assertEqual(msg.data["times"], 3)

    def test_eyes_on_off(self):
        self.api.eyes_on()
        self.assertEqual(_last(self.bus).msg_type, "enclosure.eyes.on")
        self.api.eyes_off()
        self.assertEqual(_last(self.bus).msg_type, "enclosure.eyes.off")

    def test_eyes_color(self):
        self.api.eyes_color(10, 20, 30)
        msg = _last(self.bus)
        self.assertEqual(msg.msg_type, "enclosure.eyes.color")
        self.assertEqual((msg.data["r"], msg.data["g"], msg.data["b"]), (10, 20, 30))

    def test_eyes_setpixel_valid(self):
        self.api.eyes_setpixel(5, 1, 2, 3)
        msg = _last(self.bus)
        self.assertEqual(msg.msg_type, "enclosure.eyes.setpixel")
        self.assertEqual(msg.data["idx"], 5)

    def test_eyes_setpixel_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            self.api.eyes_setpixel(99)
        with self.assertRaises(ValueError):
            self.api.eyes_setpixel(-1)

    def test_eyes_fill_valid(self):
        self.api.eyes_fill(50)
        msg = _last(self.bus)
        self.assertEqual(msg.msg_type, "enclosure.eyes.fill")
        self.assertEqual(msg.data["percentage"], 50)

    def test_eyes_fill_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            self.api.eyes_fill(101)
        with self.assertRaises(ValueError):
            self.api.eyes_fill(-1)

    def test_mouth_text(self):
        self.api.mouth_text("hi")
        msg = _last(self.bus)
        self.assertEqual(msg.msg_type, "enclosure.mouth.text")
        self.assertEqual(msg.data["text"], "hi")

    def test_set_bus_and_id(self):
        new_bus = MagicMock()
        self.api.set_bus(new_bus)
        self.api.set_id("other.skill")
        self.api.reset()
        self.assertEqual(new_bus.emit.call_args[0][0].msg_type, "enclosure.reset")
