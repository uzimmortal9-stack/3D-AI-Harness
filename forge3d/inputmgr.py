"""Forge3D input management — action mapping over raw key events."""


class InputManager:
    def __init__(self):
        self.actions = {
            "forward": {"w", "up"},
            "back": {"s", "down"},
            "left": {"a", "left"},
            "right": {"d", "right"},
            "jump": {"space"},
            "run": {"left shift"},
            "interact": {"e"},
            "camera_orbit": {"mouse_right"},
            "camera_pan": {"mouse_middle"},
            "screenshot": {"f9"},
            "reload": {"f5"},
            "quit": {"escape"},
        }
        self.down = set()
        self._pressed = set()
        self._released = set()

    def bind(self, action, keys):
        self.actions[action] = set(keys)

    def key_down(self, key):
        key = key.lower()
        if key not in self.down:
            self._pressed.add(key)
        self.down.add(key)

    def key_up(self, key):
        key = key.lower()
        self.down.discard(key)
        self._released.add(key)

    def end_frame(self):
        self._pressed.clear()
        self._released.clear()

    def is_down(self, action):
        return bool(self.down & self.actions.get(action, set()))

    def was_pressed(self, action):
        return bool(self._pressed & self.actions.get(action, set()))

    def was_released(self, action):
        return bool(self._released & self.actions.get(action, set()))
