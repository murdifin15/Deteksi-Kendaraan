import cv2
import time
import os
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StreamHandler")

class StreamHandler:
    def __init__(self, source, fallback_source=None):
        self.source = source
        self.fallback_source = fallback_source
        self.cap = None
        self.is_file = False
        self.latest_frame = None
        self.needs_reconnect = True
        self.running = True
        self.lock = threading.Lock()
        self.reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader_thread.start()

    def change_source(self, new_source, fallback=None):
        with self.lock:
            self.source = new_source
            if fallback:
                self.fallback_source = fallback
            self.needs_reconnect = True
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

    def _open_capture(self, src, is_file):
        """Opens a VideoCapture with appropriate flags for file vs live HLS stream."""
        if is_file:
            cap = cv2.VideoCapture(src)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return cap

        # For live HLS streams: inject FFmpeg low-latency flags via environment variable.
        # fflags=nobuffer  → skip FFmpeg input buffering
        # flags=low_delay  → real-time decode mode (no B-frame reorder wait)
        # max_delay=0      → don't pre-buffer extra HLS segments
        # stimeout=5000000 → 5s socket timeout (microseconds) — fail fast on dead streams
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "fflags;nobuffer|"
            "flags;low_delay|"
            "max_delay;0|"
            "stimeout;5000000"
        )
        cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Clear env var so it doesn't affect non-FFmpeg captures later
        os.environ.pop("OPENCV_FFMPEG_CAPTURE_OPTIONS", None)
        return cap

    def _connect(self):
        with self.lock:
            src = self.source
            fb = self.fallback_source
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

        logger.info(f"Connecting to stream source in background: {src}")
        is_file = os.path.exists(str(src))

        try:
            cap = self._open_capture(src, is_file)
        except Exception as e:
            logger.error(f"Error opening stream {src}: {e}")
            cap = None

        if (cap is None or not cap.isOpened()) and fb:
            logger.warning(f"Failed to open primary source {src}. Switching to fallback: {fb}")
            src = fb
            is_file = os.path.exists(str(src))
            try:
                cap = self._open_capture(src, is_file)
            except Exception:
                cap = None

        with self.lock:
            self.cap = cap
            self.is_file = is_file
            self.source = src
            self.needs_reconnect = False


    def _reader_loop(self):
        while self.running:
            if self.needs_reconnect or self.cap is None or not self.cap.isOpened():
                self._connect()
                if self.cap is None or not self.cap.isOpened():
                    time.sleep(1.0)
                    continue

            with self.lock:
                cap = self.cap
                is_file = self.is_file

            try:
                ret, frame = cap.read()
                if ret and frame is not None:
                    with self.lock:
                        self.latest_frame = frame
                else:
                    if is_file and cap is not None:
                        with self.lock:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    else:
                        logger.warning("Stream read frame failed, marking for reconnect...")
                        with self.lock:
                            self.needs_reconnect = True
                        time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Background reader exception: {e}")
                with self.lock:
                    self.needs_reconnect = True
                time.sleep(0.5)

            time.sleep(0.01 if self.is_file else 0.005)

    def read_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None

    def release(self):
        self.running = False
        with self.lock:
            if self.cap is not None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
