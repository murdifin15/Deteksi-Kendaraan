import asyncio
import cv2
import json
import logging
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import CCTV_CAMERAS, ROI_LINE, SAMPLE_VIDEO_PATH
from app.stream_handler import StreamHandler
from app.detector import YOLODetector
from app.analytics import TrafficAnalytics
from app.optical_flow_tracker import OpticalFlowTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")

app = FastAPI(
    title="Deteksi Kendaraan - Smart CCTV Traffic Monitoring API",
    version="1.0.0"
)

# Enable CORS for Frontend Development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single-Camera Mode (CPU-optimized)
active_camera = CCTV_CAMERAS[0]
stream_handler = StreamHandler(active_camera["url"], fallback_source=SAMPLE_VIDEO_PATH)
detector = YOLODetector()
analytics = TrafficAnalytics()

# State Toggles
draw_bboxes_flag = True
draw_roi_flag = True
current_roi_line = ((200, 480), (1080, 480))


class StreamProcessorThread(threading.Thread):
    """
    CPU-optimized single-camera pipeline:
    - Fast streaming thread: reads raw frames at full source FPS, composites cached YOLO overlay, encodes JPEG.
    - Slow YOLO thread: runs inference every ~2s independently; never blocks the video stream.
    """
    def __init__(self, stream_handler, detector, analytics):
        super().__init__(daemon=True)
        self.stream_handler = stream_handler
        self.detector = detector
        self.analytics = analytics
        self.running = True
        self.latest_jpeg = None
        self.latest_annotated_frame = None
        self.latest_telemetry = {}
        self.lock = threading.Lock()
        self.stream_fps = 0.0
        self._stream_frame_count = 0
        self._stream_fps_time = time.time()

        # Cached YOLO detections updated by background inference thread
        self._cached_detections = []
        self._cached_telemetry = {}
        self._overlay_lock = threading.Lock()

        # Optical flow tracker — propagates bboxes between YOLO keyframes
        self._of_tracker = OpticalFlowTracker()
        self._of_lock = threading.Lock()

        # Launch separate slow YOLO inference thread
        self._yolo_thread = threading.Thread(target=self._yolo_inference_loop, daemon=True)
        self._yolo_thread.start()

    def _yolo_inference_loop(self):
        """
        Runs YOLO every 2 seconds on a 320px-wide downscaled frame.
        On CPU (~1200ms inference), this keeps video stream completely unblocked.
        """
        logger.info("YOLO Inference Thread started (CPU low-priority mode).")
        YOLO_INTERVAL = 2.0  # Run once every 2 seconds
        while self.running:
            t0 = time.time()
            frame = self.stream_handler.read_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            # Downscale to 320px wide for fastest CPU inference
            h, w = frame.shape[:2]
            target_infer_w = 320
            if w > target_infer_w:
                actual_infer_w = target_infer_w
                actual_infer_h = int(h * (target_infer_w / w))
                frame_small = cv2.resize(frame, (actual_infer_w, actual_infer_h), interpolation=cv2.INTER_LINEAR)
            else:
                # Source frame is already small enough — use as-is
                frame_small = frame
                actual_infer_w = w
                actual_infer_h = h

            try:
                _, detections = self.detector.detect_and_track(frame_small)

                # Scale bboxes to 1280x720 reference resolution for analytics crossing checks
                sx_1280 = 1280.0 / actual_infer_w
                sy_720 = 720.0 / actual_infer_h
                detections_1280 = []
                for det in detections:
                    d = dict(det)
                    d["x1"] = int(d["x1"] * sx_1280)
                    d["y1"] = int(d["y1"] * sy_720)
                    d["x2"] = int(d["x2"] * sx_1280)
                    d["y2"] = int(d["y2"] * sy_720)
                    detections_1280.append(d)

                # Analytics update with matching 1280x720 coordinates!
                telemetry = self.analytics.update(detections_1280, roi_line=current_roi_line)

                # Scale bboxes to streaming output resolution (max 854px wide)
                stream_w = min(w, 854)
                stream_h = int(h * (stream_w / w))
                sx_stream = stream_w / actual_infer_w
                sy_stream = stream_h / actual_infer_h
                stream_detections = []
                for det in detections:
                    d = dict(det)
                    d["x1"] = int(d["x1"] * sx_stream)
                    d["y1"] = int(d["y1"] * sy_stream)
                    d["x2"] = int(d["x2"] * sx_stream)
                    d["y2"] = int(d["y2"] * sy_stream)
                    stream_detections.append(d)

                with self._overlay_lock:
                    self._cached_detections = stream_detections
                    self._cached_telemetry = telemetry

                # Provide YOLO keyframe to optical flow tracker
                stream_frame = cv2.resize(frame, (stream_w, stream_h), interpolation=cv2.INTER_LINEAR)
                with self._of_lock:
                    self._of_tracker.update_keyframe(stream_frame, stream_detections)

                logger.info(f"YOLO: {len(detections)} detections | Crossings={telemetry.get('line_crossings', 0)}")
            except Exception as e:
                logger.warning(f"YOLO inference error: {e}")

            elapsed = time.time() - t0
            time.sleep(max(0.0, YOLO_INTERVAL - elapsed))

    def run(self):
        """
        Fast streaming thread: outputs frames at up to 20 FPS with cached YOLO overlay composited.
        """
        logger.info("Video Streaming Thread started.")
        TARGET_FPS = 20
        FRAME_INTERVAL = 1.0 / TARGET_FPS
        last_time = time.time()

        while self.running:
            frame = self.stream_handler.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            # Downscale for streaming output (max 854px wide)
            h, w = frame.shape[:2]
            if w > 854:
                out_h = int(h * (854 / w))
                frame = cv2.resize(frame, (854, out_h), interpolation=cv2.INTER_LINEAR)

            # Get smoothly-propagated bbox positions from optical flow tracker
            with self._of_lock:
                of_detections = self._of_tracker.propagate(frame)

            # Fall back to cached YOLO detections if optical flow has no tracks yet
            if of_detections:
                detections = of_detections
            else:
                with self._overlay_lock:
                    detections = list(self._cached_detections)

            sh, sw = frame.shape[:2]

            # Use the cached telemetry from the YOLO inference thread (do NOT call analytics.update
            # here — that would double-process every streaming frame with stale cached detections,
            # breaking FPS measurement and ROI crossing detection).
            with self._overlay_lock:
                telemetry = dict(self._cached_telemetry) if self._cached_telemetry else {}

            # Run per-frame ROI crossing check at streaming FPS (20fps) using
            # optical-flow-propagated positions. Scale from stream resolution -> 1280x720.
            if detections:
                scale_x = 1280.0 / sw
                scale_y = 720.0 / sh
                dets_ref = []
                for det in detections:
                    d = dict(det)
                    d["x1"] = int(d["x1"] * scale_x)
                    d["y1"] = int(d["y1"] * scale_y)
                    d["x2"] = int(d["x2"] * scale_x)
                    d["y2"] = int(d["y2"] * scale_y)
                    dets_ref.append(d)
                live_crossings = self.analytics.check_crossings(dets_ref, roi_line=current_roi_line)
                # Merge live crossing count into telemetry so the overlay label is always fresh
                telemetry["line_crossings"] = live_crossings

            sh, sw = frame.shape[:2]
            roi_scaled = (
                (int(current_roi_line[0][0] * (sw / 1280.0)), int(current_roi_line[0][1] * (sh / 720.0))),
                (int(current_roi_line[1][0] * (sw / 1280.0)), int(current_roi_line[1][1] * (sh / 720.0)))
            )

            final_frame = self.detector.draw_overlays(
                frame, detections,
                draw_bboxes=draw_bboxes_flag,
                draw_roi=draw_roi_flag,
                roi_line=roi_scaled,
                line_count=telemetry.get("line_crossings", 0)
            )

            # Encode JPEG
            ret, jpeg = cv2.imencode('.jpg', final_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if ret:
                with self.lock:
                    self.latest_jpeg = jpeg.tobytes()
                    self.latest_annotated_frame = final_frame.copy()
                    self.latest_telemetry = telemetry

            # Track streaming FPS
            self._stream_frame_count += 1
            now_t = time.time()
            if now_t - self._stream_fps_time >= 1.0:
                self.stream_fps = round(self._stream_frame_count / (now_t - self._stream_fps_time), 1)
                self._stream_frame_count = 0
                self._stream_fps_time = now_t

            # Rate-limit to TARGET_FPS
            elapsed = now_t - last_time
            time.sleep(max(0.0, FRAME_INTERVAL - elapsed))
            last_time = time.time()

    def get_jpeg(self):
        with self.lock:
            return self.latest_jpeg

    def get_telemetry(self):
        # Use analytics.get_telemetry_snapshot() so we always get the live crossing
        # count even if the cached YOLO telemetry is slightly stale.
        snapshot = self.analytics.get_telemetry_snapshot()
        with self.lock:
            cached = self.latest_telemetry
        if cached:
            # Merge: take cached counts/density from YOLO, live crossings + seen counts from analytics
            merged = dict(cached)
            merged["line_crossings"] = snapshot["line_crossings"]
            merged["total_counted"] = snapshot["total_counted"]
            merged["total_seen"] = snapshot["total_seen"]
            return merged
        return snapshot

    def get_annotated_frame(self):
        with self.lock:
            return self.latest_annotated_frame.copy() if self.latest_annotated_frame is not None else None


processor = StreamProcessorThread(stream_handler, detector, analytics)
processor.start()


class StreamSelectRequest(BaseModel):
    camera_id: str


class CustomStreamRequest(BaseModel):
    name: str
    location: str | None = "Custom Stream"
    url: str
    type: str | None = "hls"


class ToggleRequest(BaseModel):
    draw_bboxes: bool | None = None
    draw_roi: bool | None = None

class ROIRequest(BaseModel):
    p1: list[int]
    p2: list[int]

@app.post("/api/stream/roi")
def update_roi_line(req: ROIRequest):
    global current_roi_line
    current_roi_line = ((int(req.p1[0]), int(req.p1[1])), (int(req.p2[0]), int(req.p2[1])))
    analytics.reset_counters()
    logger.info(f"Dynamic ROI line set to: {current_roi_line}")
    return {
        "message": "ROI line updated",
        "roi_line": current_roi_line
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "active_camera": active_camera["name"],
        "active_camera_location": active_camera["location"],
        "model": "YOLOv11 Nano",
        "stream_fps": processor.stream_fps,
        # Legacy compat fields
        "fps_1": processor.stream_fps,
        "active_camera_1": active_camera["name"],
        "active_camera_2": active_camera["name"],
    }


@app.get("/api/cameras")
def get_cameras():
    return {
        "active_id_1": active_camera["id"],
        "active_id_2": active_camera["id"],
        "active_camera_1": active_camera,
        "active_camera_2": active_camera,
        "active_camera": active_camera,
        "cameras": CCTV_CAMERAS
    }


@app.post("/api/stream/select")
def select_camera(req: StreamSelectRequest):
    global active_camera
    found_cam = next((cam for cam in CCTV_CAMERAS if cam["id"] == req.camera_id), None)
    if not found_cam:
        raise HTTPException(status_code=404, detail="Camera ID not found")

    active_camera = found_cam
    fallback = found_cam.get("fallback_url", SAMPLE_VIDEO_PATH)
    stream_handler.change_source(found_cam["url"], fallback=fallback)
    analytics.reset_counters()
    # Reset optical flow tracker so stale tracks don't bleed into new stream
    with processor._of_lock:
        processor._of_tracker.reset()
    logger.info(f"Switched camera to: {active_camera['name']}")

    return {
        "message": f"Camera changed to {found_cam['name']}",
        "active_camera": active_camera,
        "active_camera_1": active_camera,
        "active_camera_2": active_camera,
        "cameras": CCTV_CAMERAS
    }


@app.post("/api/stream/custom")
def add_custom_camera(req: CustomStreamRequest):
    global active_camera
    new_id = f"cam-custom-{int(time.time())}"
    new_cam = {
        "id": new_id,
        "name": req.name,
        "location": req.location or "Custom Stream",
        "url": req.url,
        "type": req.type or "hls",
        "fallback_url": SAMPLE_VIDEO_PATH
    }
    CCTV_CAMERAS.append(new_cam)
    active_camera = new_cam
    stream_handler.change_source(new_cam["url"], fallback=SAMPLE_VIDEO_PATH)
    analytics.reset_counters()

    logger.info(f"Added & switched to custom stream: {new_cam['name']} ({new_cam['url']})")
    return {
        "message": f"Custom camera added: {new_cam['name']}",
        "active_camera": active_camera,
        "active_camera_1": active_camera,
        "active_camera_2": active_camera,
        "cameras": CCTV_CAMERAS
    }


@app.post("/api/stream/toggle")
def toggle_overlays(req: ToggleRequest):
    global draw_bboxes_flag, draw_roi_flag
    if req.draw_bboxes is not None:
        draw_bboxes_flag = req.draw_bboxes
    if req.draw_roi is not None:
        draw_roi_flag = req.draw_roi
    return {
        "draw_bboxes": draw_bboxes_flag,
        "draw_roi": draw_roi_flag
    }


def generate_mjpeg_stream():
    last_sent = None
    while True:
        jpeg_bytes = processor.get_jpeg()
        if jpeg_bytes is not None and jpeg_bytes != last_sent:
            last_sent = jpeg_bytes
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n')
        time.sleep(0.005)


@app.get("/api/stream/video")
def video_stream(slot: int = 1):
    # slot param kept for backward compat but ignored in single-camera mode
    return StreamingResponse(
        generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    logger.info("Client connected to WebSocket Telemetry Stream")
    try:
        while True:
            telemetry = processor.get_telemetry()
            # Inject the real video streaming FPS (from the processor) into telemetry
            # so the frontend header shows the actual stream output FPS.
            telemetry_with_fps = dict(telemetry)
            telemetry_with_fps["fps"] = processor.stream_fps
            payload = {
                "active_camera_1": active_camera["name"],
                "active_camera_2": active_camera["name"],
                "telemetry_1": telemetry_with_fps,
                "telemetry_2": telemetry_with_fps  # legacy compat
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket Telemetry Stream")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")


@app.get("/api/snapshot")
def get_snapshot(slot: int = 1):
    frame = processor.get_annotated_frame()
    if frame is None:
        raise HTTPException(status_code=503, detail="Frame not available yet")

    ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ret:
        raise HTTPException(status_code=500, detail="Failed to encode snapshot image")

    return Response(content=jpeg.tobytes(), media_type="image/jpeg", headers={
        "Content-Disposition": f"attachment; filename=cctv_snapshot_{int(time.time())}.jpg"
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
