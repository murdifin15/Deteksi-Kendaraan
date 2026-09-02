import cv2
import numpy as np
import os
import math

def generate_synthetic_traffic_video(output_path, duration_sec=15, fps=25, width=1280, height=720):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    total_frames = duration_sec * fps
    
    # Define simulated highway background
    def draw_road(img):
        # Dark asphalt road
        cv2.fillPoly(img, [np.array([[200, 720], [500, 200], [780, 200], [1080, 720]])], (40, 42, 48))
        # Side grass
        cv2.fillPoly(img, [np.array([[0, 720], [0, 0], [1280, 0], [1280, 720], [1080, 720], [780, 200], [500, 200], [200, 720]])], (25, 60, 30))
        # Lane divider lines (dashed)
        cv2.line(img, (640, 200), (640, 720), (220, 220, 220), 4)

    # Vehicles specification (start_y, speed, color, size, vehicle_type)
    vehicles = [
        # Downward lane
        {"id": 1, "x_center": 420, "y": 200, "speed": 6.5, "color": (220, 50, 50), "size": (60, 100), "type": "car"},
        {"id": 2, "x_center": 350, "y": 150, "speed": 8.0, "color": (50, 200, 220), "size": (25, 45), "type": "motorcycle"},
        {"id": 3, "x_center": 480, "y": 100, "speed": 4.5, "color": (180, 80, 240), "size": (90, 180), "type": "bus"},
        {"id": 4, "x_center": 390, "y": 50,  "speed": 5.5, "color": (50, 150, 240), "size": (80, 150), "type": "truck"},
        {"id": 5, "x_center": 450, "y": -80, "speed": 7.2, "color": (240, 240, 240), "size": (55, 95), "type": "car"},
        {"id": 6, "x_center": 320, "y": -150, "speed": 8.5, "color": (0, 220, 255), "size": (22, 40), "type": "motorcycle"},
        # Upward lane (moving from bottom to top)
        {"id": 7, "x_center": 860, "y": 720, "speed": -7.0, "color": (50, 220, 100), "size": (60, 100), "type": "car"},
        {"id": 8, "x_center": 930, "y": 780, "speed": -8.8, "color": (220, 220, 50), "size": (25, 45), "type": "motorcycle"},
        {"id": 9, "x_center": 800, "y": 850, "speed": -5.0, "color": (220, 100, 50), "size": (85, 160), "type": "truck"},
    ]

    for frame_idx in range(total_frames):
        frame = np.full((height, width, 3), (35, 38, 42), dtype=np.uint8)
        draw_road(frame)
        
        # Virtual ROI line
        cv2.line(frame, (200, 480), (1080, 480), (0, 242, 254), 2)
        cv2.putText(frame, "VIRTUAL ROI COUNTING LINE", (220, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 242, 254), 2)

        # Update and draw vehicles
        for v in vehicles:
            v["y"] += v["speed"]
            # Loop vehicles
            if v["speed"] > 0 and v["y"] > height + 100:
                v["y"] = -100
            elif v["speed"] < 0 and v["y"] < -150:
                v["y"] = height + 100
            
            # Perspective scaling factor based on Y position
            y_pos = max(0, min(height, v["y"]))
            scale = 0.5 + (y_pos / height) * 0.7
            
            w = int(v["size"][0] * scale)
            h = int(v["size"][1] * scale)

            # Perspective X position drifting
            if v["speed"] > 0:
                x = int(640 - (640 - v["x_center"]) * (0.3 + 0.7 * (y_pos / height)))
            else:
                x = int(640 + (v["x_center"] - 640) * (0.3 + 0.7 * (y_pos / height)))

            x1 = x - w // 2
            y1 = int(y_pos) - h // 2
            x2 = x1 + w
            y2 = y1 + h

            # Draw vehicle body (rounded rectangle)
            cv2.rectangle(frame, (x1, y1), (x2, y2), v["color"], -1)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)

            # Draw headlights/taillights
            light_color = (0, 255, 255) if v["speed"] > 0 else (0, 0, 255)
            cv2.circle(frame, (x1 + 6, y2 if v["speed"] > 0 else y1), 4, light_color, -1)
            cv2.circle(frame, (x2 - 6, y2 if v["speed"] > 0 else y1), 4, light_color, -1)

        out.write(frame)

    out.release()
    print(f"Generated sample synthetic traffic video at: {output_path}")

if __name__ == "__main__":
    generate_synthetic_traffic_video("backend/assets/sample_cctv.mp4")
