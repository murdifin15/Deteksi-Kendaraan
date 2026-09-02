import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_VIDEO_PATH = os.path.join(BASE_DIR, "assets", "sample_cctv.mp4")

# Preset CCTV Cameras (Public Streams & Local Fallback - Area Jogja)
CCTV_CAMERAS = [
    {
        "id": "cam-01",
        "name": "CCTV Titik Nol Kilometer (Pojok BNI)",
        "location": "D.I. Yogyakarta",
        "url": "https://cctv.jogjaprov.go.id/cctv-proxy/cctv-public/ViewNolKilo.stream/playlist.m3u8",
        "type": "hls",
        "fallback_url": SAMPLE_VIDEO_PATH
    },
    {
        "id": "cam-02",
        "name": "CCTV Simpang Tugu Yogyakarta",
        "location": "D.I. Yogyakarta",
        "url": "https://cctv.jogjaprov.go.id/cctv-proxy/cctv-public/ViewTugu.stream/playlist.m3u8",
        "type": "hls",
        "fallback_url": SAMPLE_VIDEO_PATH
    },
    {
        "id": "cam-03",
        "name": "Simpang ATCS Malioboro (Demo Video Feed)",
        "location": "D.I. Yogyakarta",
        "url": SAMPLE_VIDEO_PATH,
        "type": "file"
    }
]

# YOLOv11 Detector Configuration
YOLO_MODEL_NAME = "yolo11n.pt"  # Will automatically download yolo11n.pt on first load
CONF_THRESHOLD = 0.30
TRACKER_TYPE = "bytetrack.yaml"

# Target Vehicle COCO Classes
VEHICLE_CLASSES = {
    2: {"name": "Mobil", "key": "car", "color": (246, 130, 59)},       # Royal Blue (BGR: 246, 130, 59)
    3: {"name": "Motor", "key": "motorcycle", "color": (212, 182, 6)},  # Cyan (BGR: 212, 182, 6)
    5: {"name": "Bus", "key": "bus", "color": (246, 92, 139)},          # Violet (BGR: 246, 92, 139)
    7: {"name": "Truk", "key": "truck", "color": (22, 115, 249)}       # Bright Orange (BGR: 22, 115, 249)
}

# Traffic Density Thresholds (Active Vehicles Count)
DENSITY_THRESHOLDS = {
    "LANCAR": 8,   # < 8 vehicles = LANCAR
    "SEDANG": 18   # 8 - 18 vehicles = SEDANG, > 18 = MACET
}

# Virtual ROI Line Coordinates (x1, y1, x2, y2)
ROI_LINE = ((200, 480), (1080, 480))
