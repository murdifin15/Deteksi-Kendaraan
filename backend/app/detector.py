import cv2
import math
import numpy as np
import logging
from ultralytics import YOLO
from app.config import YOLO_MODEL_NAME, CONF_THRESHOLD, VEHICLE_CLASSES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YOLODetector")


def _draw_rotated_text(img, text, p1, p2, font_scale=0.38, color=(254, 242, 0), thickness=1):
    """
    Renders text rotated parallel along line p1-p2 with smaller font size.
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 10:
        cv2.putText(img, text, (p1[0] + 5, p1[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)
        return

    # Calculate angle of the line
    angle = math.degrees(math.atan2(dy, dx))
    if angle > 90:
        angle -= 180
    elif angle < -90:
        angle += 180

    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

    pad = 6
    w_box = tw + pad * 2
    h_box = th + pad * 2 + baseline
    text_canvas = np.zeros((h_box, w_box, 4), dtype=np.uint8)

    # Render text in canvas
    cv2.putText(text_canvas, text, (pad, pad + th), font, font_scale, (*color, 255), thickness, cv2.LINE_AA)

    # Rotate text_canvas
    center = (w_box // 2, h_box // 2)
    M = cv2.getRotationMatrix2D(center, -angle, 1.0)  # OpenCV y grows downward

    cos = abs(M[0, 0])
    sin = abs(M[0, 1])
    nW = int((h_box * sin) + (w_box * cos))
    nH = int((h_box * cos) + (w_box * sin))
    M[0, 2] += (nW / 2) - center[0]
    M[1, 2] += (nH / 2) - center[1]

    rotated = cv2.warpAffine(text_canvas, M, (nW, nH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))

    mid_x = (p1[0] + p2[0]) / 2.0
    mid_y = (p1[1] + p2[1]) / 2.0

    nx = -dy / length
    ny = dx / length
    if ny > 0:
        nx = -nx
        ny = -ny

    offset = 10
    pos_x = int(mid_x + nx * offset - nW / 2)
    pos_y = int(mid_y + ny * offset - nH / 2)

    h_img, w_img = img.shape[:2]
    x1 = max(0, pos_x)
    y1 = max(0, pos_y)
    x2 = min(w_img, pos_x + nW)
    y2 = min(h_img, pos_y + nH)

    if x2 <= x1 or y2 <= y1:
        cv2.putText(img, text, (p1[0] + 5, p1[1] - 5), font, font_scale, color, thickness, cv2.LINE_AA)
        return

    crop_rot = rotated[(y1 - pos_y):(y2 - pos_y), (x1 - pos_x):(x2 - pos_x)]
    alpha = crop_rot[:, :, 3] / 255.0

    for c in range(3):
        img[y1:y2, x1:x2, c] = (alpha * crop_rot[:, :, c] + (1.0 - alpha) * img[y1:y2, x1:x2, c]).astype(np.uint8)


class YOLODetector:
    def __init__(self, model_name=YOLO_MODEL_NAME):
        logger.info(f"Initializing YOLOv11 model: {model_name}...")
        self.model = YOLO(model_name)
        # Target COCO classes: 2 (car), 3 (motorcycle), 5 (bus), 7 (truck)
        self.target_classes = list(VEHICLE_CLASSES.keys())
        logger.info(f"YOLOv11 model initialized successfully with target classes: {self.target_classes}")

    def detect_and_track(self, frame):
        """
        Runs YOLOv11 detection and persistent tracking on a single frame.
        Returns:
            processed_frame: frame with visual overlays
            detections: list of dicts containing bbox, class, confidence, track_id
        """
        if frame is None:
            return None, []

        results = self.model.track(
            frame,
            persist=True,
            classes=self.target_classes,
            conf=CONF_THRESHOLD,
            tracker="bytetrack.yaml",
            imgsz=640,
            verbose=False
        )

        detections = []
        annotated_frame = frame.copy()

        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes

            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    
                    # Track ID (if available from ByteTrack)
                    track_id = int(box.id[0].item()) if box.id is not None else None
                    
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    x1, y1, x2, y2 = xyxy

                    vehicle_info = VEHICLE_CLASSES.get(cls_id, {"name": "Kendaraan", "key": "car", "color": (255, 255, 255)})
                    
                    det_data = {
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2),
                        "class_id": cls_id,
                        "class_name": vehicle_info["name"],
                        "class_key": vehicle_info["key"],
                        "confidence": round(conf, 2),
                        "track_id": track_id
                    }
                    detections.append(det_data)

        return annotated_frame, detections

    def draw_overlays(self, frame, detections, draw_bboxes=True, draw_roi=True, roi_line=None, line_count=0):
        """
        Draws glowing bounding boxes, labels, and ROI lines onto the frame.
        """
        out_frame = frame.copy()

        # Draw ROI Counting Line
        if draw_roi and roi_line:
            p1, p2 = roi_line
            # Cyan line
            cv2.line(out_frame, p1, p2, (254, 242, 0), 2)
            # Text tag rotated to follow line orientation with smaller crisp font
            _draw_rotated_text(out_frame, f"ROI CROSSING LINE | TOTAL PASSED: {line_count}", p1, p2, font_scale=0.38, color=(254, 242, 0), thickness=1)

        # Draw Bounding Boxes with batch alpha blend overlay
        if draw_bboxes and detections:
            overlay = out_frame.copy()
            for det in detections:
                x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
                cls_id = det["class_id"]
                vehicle_info = VEHICLE_CLASSES.get(cls_id, {"name": "Kendaraan", "key": "car", "color": (255, 255, 255)})
                cv2.rectangle(overlay, (x1, y1), (x2, y2), vehicle_info["color"], -1)
            
            cv2.addWeighted(overlay, 0.15, out_frame, 0.85, 0, out_frame)

            for det in detections:
                x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
                cls_id = det["class_id"]
                track_id = det["track_id"]
                conf = det["confidence"]
                
                vehicle_info = VEHICLE_CLASSES.get(cls_id, {"name": "Kendaraan", "key": "car", "color": (255, 255, 255)})
                color = vehicle_info["color"]

                # Crisp 2px Bounding Box
                cv2.rectangle(out_frame, (x1, y1), (x2, y2), color, 2)

                # Label text: e.g. "Mobil #12 85%"
                label_str = f"{vehicle_info['name']}"
                if track_id is not None:
                    label_str += f" #{track_id}"
                label_str += f" {int(conf * 100)}%"

                # Label background tag calculation
                (w, h), _ = cv2.getTextSize(label_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                tag_h = h + 10
                if y1 - tag_h >= 0:
                    tag_y1 = y1 - tag_h
                    tag_y2 = y1
                    text_y = tag_y1 + h + 3
                else:
                    tag_y1 = y1
                    tag_y2 = y1 + tag_h
                    text_y = tag_y1 + h + 3

                cv2.rectangle(out_frame, (x1, tag_y1), (x1 + w + 12, tag_y2), color, -1)
                cv2.putText(out_frame, label_str, (x1 + 6, text_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

        return out_frame
