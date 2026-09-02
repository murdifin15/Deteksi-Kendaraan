import time
import math
import threading
from app.config import DENSITY_THRESHOLDS, ROI_LINE, VEHICLE_CLASSES


def _ccw(A, B, C):
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def _line_intersects(p1, p2, q1, q2):
    """Checks if line segment p1-p2 intersects line segment q1-q2."""
    return (_ccw(p1, q1, q2) != _ccw(p2, q1, q2)) and (_ccw(p1, p2, q1) != _ccw(p1, p2, q2))


class TrafficAnalytics:
    def __init__(self):
        self.fps = 0.0
        self.frame_count = 0
        self.last_time = time.time()

        # Thread-safety lock — crossing state is accessed from both
        # the YOLO inference thread (~every 2s) and the streaming thread (20fps).
        self._lock = threading.Lock()

        # Persistent Line Crossing Tracking
        # prev_positions: {track_id: {"cx", "cy", "y1", "y2", "class_key", "last_seen"}}
        self.crossed_ids = set()
        self.prev_positions = {}
        self.total_line_crossings = 0
        self._next_spatial_id = 1

        # Cached active counts (set by YOLO thread, read by streaming thread via snapshot)
        self._active_counts = {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "total": 0}
        self._density_status = "LANCAR"
        self._density_score = 0

        # Vehicle Counter: cumulative unique vehicles SEEN this session (never resets to 0).
        # Incremented when a track_id appears for the first time, regardless of ROI crossing.
        self.seen_ids = set()
        self.total_seen_by_class = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0
        }

        # Vehicle Counter: cumulative vehicles that CROSSED the ROI line
        self.total_counted_by_class = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0
        }

    # ------------------------------------------------------------------
    # Internal helpers (must be called with self._lock held)
    # ------------------------------------------------------------------

    def _resolve_track_id(self, det, now):
        """Return a stable string track_id for a detection dict."""
        raw_track_id = det.get("track_id")
        class_key = det["class_key"]
        cx = (det["x1"] + det["x2"]) // 2
        cy = (det["y1"] + det["y2"]) // 2

        if raw_track_id is not None:
            return f"id_{raw_track_id}"

        # Spatial centroid matching fallback
        best_dist = 95.0
        best_id = None
        for existing_id, pos_info in self.prev_positions.items():
            if pos_info["class_key"] == class_key and (now - pos_info["last_seen"] < 1.2):
                dist = math.hypot(cx - pos_info["cx"], cy - pos_info["cy"])
                if dist < best_dist:
                    best_dist = dist
                    best_id = existing_id

        if best_id is not None:
            return best_id

        track_id = f"spatial_{self._next_spatial_id}_{class_key}"
        self._next_spatial_id += 1
        return track_id

    def _do_crossing_check(self, det, track_id, roi_q1, roi_q2, now):
        """
        Checks if the trajectory from prev_positions -> current bbox crosses the ROI line.
        Increments total_line_crossings if a new crossing is detected.
        Must be called with self._lock held.
        """
        cx = (det["x1"] + det["x2"]) // 2
        cy = (det["y1"] + det["y2"]) // 2
        y1 = det["y1"]
        y2 = det["y2"]
        class_key = det["class_key"]

        # ---- Cumulative seen counter: count each unique vehicle once ----
        if track_id not in self.seen_ids:
            self.seen_ids.add(track_id)
            if class_key in self.total_seen_by_class:
                self.total_seen_by_class[class_key] += 1

        # ---- ROI line-crossing check ----
        if track_id in self.prev_positions:
            prev = self.prev_positions[track_id]
            crossed_center = _line_intersects(
                (prev["cx"], prev["cy"]), (cx, cy), roi_q1, roi_q2
            )
            crossed_bottom = _line_intersects(
                (prev["cx"], prev["y2"]), (cx, y2), roi_q1, roi_q2
            )
            crossed_top = _line_intersects(
                (prev["cx"], prev["y1"]), (cx, y1), roi_q1, roi_q2
            )

            if (crossed_center or crossed_bottom or crossed_top) and (track_id not in self.crossed_ids):
                self.crossed_ids.add(track_id)
                self.total_line_crossings += 1
                if class_key in self.total_counted_by_class:
                    self.total_counted_by_class[class_key] += 1

        # Update position state for next frame
        self.prev_positions[track_id] = {
            "cx": cx, "cy": cy, "y1": y1, "y2": y2,
            "class_key": class_key, "last_seen": now
        }

    def _purge_stale(self, now, ttl=3.0):
        """Remove position entries older than ttl seconds. Call with lock held."""
        stale = [tid for tid, info in self.prev_positions.items()
                 if now - info["last_seen"] > ttl]
        for tid in stale:
            del self.prev_positions[tid]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, detections, roi_line=ROI_LINE):
        """
        Called by the YOLO inference thread (~every 2 seconds).
        Updates active vehicle counts, density status, and runs the ROI
        crossing check for the YOLO keyframe positions.
        Returns a full telemetry dict.
        """
        now = time.time()
        self.frame_count += 1
        roi_q1, roi_q2 = roi_line[0], roi_line[1]

        active_counts = {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "total": 0}

        with self._lock:
            for det in detections:
                class_key = det["class_key"]
                if class_key in active_counts:
                    active_counts[class_key] += 1
                    active_counts["total"] += 1

                track_id = self._resolve_track_id(det, now)
                self._do_crossing_check(det, track_id, roi_q1, roi_q2, now)

            self._purge_stale(now)
            self._active_counts = active_counts

            # Calculate Density Status
            total_active = active_counts["total"]
            if total_active < DENSITY_THRESHOLDS["LANCAR"]:
                self._density_status = "LANCAR"
                self._density_score = min(100, int(
                    (total_active / DENSITY_THRESHOLDS["LANCAR"]) * 35))
            elif total_active <= DENSITY_THRESHOLDS["SEDANG"]:
                self._density_status = "SEDANG"
                self._density_score = 35 + int(
                    ((total_active - DENSITY_THRESHOLDS["LANCAR"]) /
                     (DENSITY_THRESHOLDS["SEDANG"] - DENSITY_THRESHOLDS["LANCAR"])) * 35)
            else:
                self._density_status = "MACET"
                self._density_score = min(100, 70 + int(
                    (total_active - DENSITY_THRESHOLDS["SEDANG"]) * 3))

            return {
                "active_counts": dict(active_counts),
                "density_status": self._density_status,
                "density_score": self._density_score,
                "line_crossings": self.total_line_crossings,
                "total_counted": dict(self.total_counted_by_class),
                "total_seen": dict(self.total_seen_by_class),
                "fps": self.fps,
                "timestamp": time.strftime("%H:%M:%S")
            }

    def check_crossings(self, detections_1280, roi_line=ROI_LINE):
        """
        Called by the streaming thread at ~20 FPS with optical-flow-propagated
        bbox positions already scaled to 1280x720 reference space.

        Only updates ROI crossing counters — does NOT touch active_counts or
        density status, so it is fully safe to call concurrently with update().

        Returns the current total_line_crossings value after the check.
        """
        now = time.time()
        roi_q1, roi_q2 = roi_line[0], roi_line[1]

        with self._lock:
            for det in detections_1280:
                track_id = self._resolve_track_id(det, now)
                self._do_crossing_check(det, track_id, roi_q1, roi_q2, now)

            self._purge_stale(now, ttl=3.0)
            return self.total_line_crossings

    def get_telemetry_snapshot(self):
        """
        Returns a telemetry dict using the most recent cached counts plus
        the live crossing counter. Safe to call from any thread.
        """
        with self._lock:
            return {
                "active_counts": dict(self._active_counts),
                "density_status": self._density_status,
                "density_score": self._density_score,
                "line_crossings": self.total_line_crossings,
                "total_counted": dict(self.total_counted_by_class),
                "total_seen": dict(self.total_seen_by_class),
                "fps": self.fps,
                "timestamp": time.strftime("%H:%M:%S")
            }

    def reset_counters(self):
        with self._lock:
            self.crossed_ids.clear()
            self.seen_ids.clear()
            self.prev_positions.clear()
            self.total_line_crossings = 0
            for k in self.total_counted_by_class:
                self.total_counted_by_class[k] = 0
            for k in self.total_seen_by_class:
                self.total_seen_by_class[k] = 0

