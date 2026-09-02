"""
Optical Flow Bbox Tracker
=========================
Runs between YOLO keyframes to keep bounding boxes smoothly following objects.

How it works:
1. YOLO gives new detections every ~2s (keyframe)
2. On each video frame, Lucas-Kanade Sparse Optical Flow propagates
   the center + corner points of each bbox forward in time.
3. The bbox is translated by the median motion vector of its tracked points.
4. Bboxes that lose their tracked points (occlusion / left frame) are dropped.

This gives smooth, real-time bbox tracking at full video FPS
without needing to run YOLO on every frame.
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger("OpticalFlowTracker")

# LK optical flow parameters (optimized for small/fast vehicles)
LK_PARAMS = dict(
    winSize=(15, 15),
    maxLevel=2,
    criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
)

# How many grid points to sample inside each bbox for tracking
POINTS_PER_BOX = 9  # 3x3 grid


def _sample_points_in_box(x1, y1, x2, y2, n=POINTS_PER_BOX):
    """Sample a grid of points inside a bounding box for optical flow tracking."""
    side = int(np.sqrt(n))
    xs = np.linspace(x1 + 4, x2 - 4, side)
    ys = np.linspace(y1 + 4, y2 - 4, side)
    pts = []
    for y in ys:
        for x in xs:
            pts.append([x, y])
    return np.array(pts, dtype=np.float32).reshape(-1, 1, 2)


class OpticalFlowTracker:
    """
    Lightweight inter-frame bbox tracker using Lucas-Kanade optical flow.
    Call update_keyframe() when YOLO provides fresh detections.
    Call propagate() every streaming frame to get smoothly-updated bboxes.
    """

    def __init__(self):
        self._prev_gray = None          # Previous grayscale frame
        self._tracked = []              # List of active track states
        # Each track state: {det: dict, points: np.ndarray, w: int, h: int}

    def update_keyframe(self, frame_bgr, detections):
        """
        Called when YOLO provides a new set of detections.
        Initialises tracking points for each detected bbox.

        Args:
            frame_bgr: Current BGR frame (streaming resolution)
            detections:  List of det dicts from YOLO (already scaled to stream res)
        """
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        self._prev_gray = gray
        self._tracked = []

        for det in detections:
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
            w = max(1, x2 - x1)
            h = max(1, y2 - y1)

            pts = _sample_points_in_box(x1, y1, x2, y2)
            self._tracked.append({
                "det": dict(det),   # snapshot of YOLO detection data
                "points": pts,
                "w": w,
                "h": h,
            })

    def propagate(self, frame_bgr):
        """
        Propagates all tracked bboxes to the current frame using optical flow.
        Returns an updated list of detection dicts with shifted bbox coords.

        Args:
            frame_bgr: Current BGR streaming frame

        Returns:
            List of updated detection dicts (same format as YOLO detections)
        """
        if self._prev_gray is None or not self._tracked:
            return []

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        fh, fw = gray.shape[:2]

        next_tracked = []
        updated_dets = []

        for track in self._tracked:
            pts = track["points"]
            if pts is None or len(pts) == 0:
                continue

            # Run Lucas-Kanade optical flow
            next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, gray, pts, None, **LK_PARAMS
            )

            if next_pts is None or status is None:
                continue

            # Keep only good points (status == 1)
            good_mask = status.ravel() == 1
            good_next = next_pts[good_mask]
            good_prev = pts[good_mask]

            # Need at least 1 good point to keep the track
            if len(good_next) < 1:
                continue

            # Calculate median motion vector
            motion = good_next.reshape(-1, 2) - good_prev.reshape(-1, 2)
            dx = float(np.median(motion[:, 0]))
            dy = float(np.median(motion[:, 1]))

            # Translate bbox
            det = dict(track["det"])
            w = track["w"]
            h = track["h"]

            new_x1 = int(det["x1"] + dx)
            new_y1 = int(det["y1"] + dy)
            new_x2 = new_x1 + w
            new_y2 = new_y1 + h

            # Clamp to frame boundaries
            new_x1 = max(0, min(new_x1, fw - 1))
            new_y1 = max(0, min(new_y1, fh - 1))
            new_x2 = max(0, min(new_x2, fw - 1))
            new_y2 = max(0, min(new_y2, fh - 1))

            # Drop degenerate boxes
            if new_x2 - new_x1 < 5 or new_y2 - new_y1 < 5:
                continue

            det["x1"] = new_x1
            det["y1"] = new_y1
            det["x2"] = new_x2
            det["y2"] = new_y2

            updated_dets.append(det)

            # Update track state for next frame
            next_tracked.append({
                "det": det,
                "points": good_next.reshape(-1, 1, 2),
                "w": new_x2 - new_x1,
                "h": new_y2 - new_y1,
            })

        self._prev_gray = gray
        self._tracked = next_tracked
        return updated_dets

    def reset(self):
        """Reset tracker state (e.g. when camera source changes)."""
        self._prev_gray = None
        self._tracked = []
