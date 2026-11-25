import unittest
from rdc.mobile import touch_actions, ELEMENT_KEY


def resolved_waypoints(source, center):
    """Resolve W3C move origins into absolute points for semantic assertions."""
    elapsed = 0
    point = None
    waypoints = []
    for event in source["actions"]:
        elapsed += event.get("duration", 0)
        if event["type"] != "pointerMove":
            continue
        origin = event["origin"]
        offset = (event["x"], event["y"])
        if isinstance(origin, dict):
            point = (center[0] + offset[0], center[1] + offset[1])
        elif origin == "viewport":
            point = offset
        elif origin == "pointer":
            if point is None:
                raise ValueError("Pointer-relative move needs a previous position")
            point = (point[0] + offset[0], point[1] + offset[1])
        else:
            raise ValueError("Unsupported move origin")
        waypoints.append((elapsed, *point))
    return waypoints


class NativeWaypointTests(unittest.TestCase):
    def test_stationary_contact_interval_has_a_native_waypoint(self):
        paths = [
            dict(start_x=20, start_y=40, end_x=50, end_y=60, hold_ms=100),
            dict(start_x=90, start_y=40, end_x=120, end_y=60, hold_ms=600),
        ]
        batch = touch_actions(paths, {ELEMENT_KEY: "observed-surface"}, (70, 50), 100, 0)
        # Native coordinate waypoints must preserve the stationary interval.
        for source in batch:
            requested = paths[int(source["id"].rsplit("-", 1)[1]) - 1]
            self.assertEqual([
                (0, requested["start_x"], requested["start_y"]),
                (50, requested["start_x"], requested["start_y"]),
                (150, requested["end_x"], requested["end_y"]),
            ], resolved_waypoints(source, (70, 50)))

    def test_native_release_order_preserves_contact_identity(self):
        requested = [
            dict(start_x=20, start_y=40, end_x=50, end_y=60, hold_ms=100),
            dict(start_x=90, start_y=40, end_x=120, end_y=60, hold_ms=600),
        ]
        original = [dict(p) for p in requested]
        batch = touch_actions(requested, {ELEMENT_KEY: "observed-surface"}, (70, 50), 100, 0)
        now = 0
        release = {}
        for tick in range(max(len(s["actions"]) for s in batch)):
            events = [(s["id"], s["actions"][tick]) for s in batch if tick < len(s["actions"])]
            for key, event in events:
                if event["type"] == "pointerUp":
                    release[key] = now
            now += max((event.get("duration", 0) for _, event in events), default=0)
        self.assertEqual({"rdc-touch-1": 250, "rdc-touch-2": 750}, release)
        self.assertEqual([750, 250], [release[s["id"]] for s in batch])
        self.assertEqual(["rdc-touch-2", "rdc-touch-1"], [s["id"] for s in batch])
        for source in batch:
            path = requested[int(source["id"].rsplit("-", 1)[1]) - 1]
            self.assertEqual((path["end_x"], path["end_y"]), resolved_waypoints(source, (70, 50))[-1][1:])
        self.assertEqual(original, requested)

    def test_anchored_submoves_resolve_each_contact_once(self):
        paths = [
            dict(start_x=20, start_y=40, end_x=50, end_y=60),
            dict(start_x=90, start_y=40, end_x=120, end_y=60),
        ]
        original = [dict(p) for p in paths]
        anchor = {ELEMENT_KEY: "observed-surface"}
        batch = touch_actions(paths, anchor, (70, 50), 100, 300)
        self.assertEqual(["rdc-touch-1", "rdc-touch-2"], [s["id"] for s in batch])
        for source in batch:
            moves = [e for e in source["actions"] if e["type"] == "pointerMove"]
            self.assertEqual(1, sum(isinstance(e["origin"], dict) for e in moves))
            self.assertEqual([anchor, "pointer", "pointer"], [e["origin"] for e in moves])
            self.assertEqual((0, 0), (moves[1]["x"], moves[1]["y"]))
        self.assertEqual(original, paths)

    def test_pointer_relative_move_preserves_odd_center_displacement(self):
        path = dict(start_x=20, start_y=40, end_x=21, end_y=41)
        source = touch_actions([path], {ELEMENT_KEY: "odd-surface"}, (70.5, 50.5), 100, 0)[0]
        points = resolved_waypoints(source, (70.5, 50.5))
        self.assertEqual("rdc-touch", source["id"])
        self.assertEqual([0, 50, 150], [p[0] for p in points])
        self.assertEqual(points[0][1:], points[1][1:])
        self.assertEqual((1, 1), (points[-1][1] - points[0][1], points[-1][2] - points[0][2]))
        self.assertLessEqual(abs(points[0][1] - path["start_x"]), 0.5)
        self.assertLessEqual(abs(points[0][2] - path["start_y"]), 0.5)

    def test_viewport_submoves_preserve_legacy_actions(self):
        path = dict(start_x=20, start_y=40, end_x=50, end_y=60)
        source = touch_actions([path], "viewport", (0, 0), 100, None)[0]
        self.assertEqual([
            {"type": "pointerMove", "duration": 0, "origin": "viewport", "x": 20, "y": 40},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 50},
            {"type": "pointerMove", "duration": 100, "origin": "viewport", "x": 50, "y": 60},
            {"type": "pointerUp", "button": 0},
        ], source["actions"])
