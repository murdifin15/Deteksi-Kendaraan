# Style Guide & UI/UX Design System
## Futuristic Dark Glassmorphism - Traffic Monitoring Dashboard

---

## 1. Aesthetic Vision & Concept

**Theme Concept:** **Futuristic Dark Glassmorphism & High-Density Analytics**  
UI dirancang untuk memberikan kesan *Command Center* modern khas Smart City. Menggabungkan efek kaca buram (*frosted glass*), aksen neon yang menyala pada latar belakang obsidian gelap, dan visualisasi data berkepadatan tinggi yang mudah dibaca secara *real-time*.

- **Style ID (UI/UX Pro Max):** `glassmorphism` + `data-dense-dashboard`
- **Preferred Mode:** Dark Mode Only (Optimized for low-light command center environments)
- **Visual Depth:** Multi-layered translucent surfaces with backdrop blur (12-16px).

---

## 2. Color System & Palettes

Palette warna disusun secara ilmiah untuk membedakan kategori kendaraan, status kepadatan jalan, serta menjaga kontras teks (WCAG AAA/AA 4.5:1+).

### 2.1 Base & Surface Colors (Obsidian Glass)

```css
:root {
  /* Canvas Background */
  --bg-canvas: #0B0F17;           /* Deep Space Obsidian Black */
  --bg-canvas-gradient: radial-gradient(circle at 50% 0%, #1A233A 0%, #0B0F17 75%);

  /* Surface & Glass Panels */
  --glass-bg: rgba(17, 24, 39, 0.65);
  --glass-bg-hover: rgba(30, 41, 59, 0.75);
  --glass-border: rgba(255, 255, 255, 0.08);
  --glass-border-glow: rgba(0, 242, 254, 0.25);
  --backdrop-blur: blur(16px);

  /* Text & Content */
  --text-primary: #F8FAFC;        /* Crisp White */
  --text-secondary: #94A3B8;      /* Slate Muted */
  --text-dimmed: #64748B;         /* Dark Slate */
}
```

### 2.2 Brand & Neon Accent Colors

```css
:root {
  --accent-cyan: #00F2FE;         /* AI / Detection Primary Accent */
  --accent-blue: #3B82F6;         /* Primary Action Button */
  --accent-purple: #7F00FF;       /* AI Tracking Glow */
  --accent-glow: 0 0 15px rgba(0, 242, 254, 0.4);
}
```

### 2.3 Traffic Status Indicators (Kepadatan Lalu Lintas)

| Status | Color Name | Hex Code | Glow Effect | Meaning |
| :--- | :--- | :--- | :--- | :--- |
| **LANCAR** | Emerald Green | `#10B981` | `0 0 12px rgba(16, 185, 129, 0.4)` | Lalu lintas lancar (Volume kendaraan rendah) |
| **SEDANG** | Amber Orange | `#F59E0B` | `0 0 12px rgba(245, 158, 11, 0.4)` | Lalu lintas sedang (Volume kendaraan moderat) |
| **MACET** | Crimson Red | `#EF4444` | `0 0 12px rgba(239, 68, 68, 0.4)` | Lalu lintas padat/macet (Volume tinggi) |

### 2.4 Vehicle Class Badges & Bounding Box Colors

| Vehicle Class | Label | Color Code | Badge Preview |
| :--- | :--- | :--- | :--- |
| **Car** | Mobil | `#3B82F6` (Royal Blue) | ![Car Badge](https://via.placeholder.com/15/3B82F6/3B82F6) Blue |
| **Motorcycle** | Sepeda Motor | `#06B6D4` (Electric Cyan) | ![Motorcycle Badge](https://via.placeholder.com/15/06B6D4/06B6D4) Cyan |
| **Bus** | Bus | `#8B5CF6` (Vivid Purple) | ![Bus Badge](https://via.placeholder.com/15/8B5CF6/8B5CF6) Purple |
| **Truck** | Truk | `#F97316` (Bright Orange) | ![Truck Badge](https://via.placeholder.com/15/F97316/F97316) Orange |

---

## 3. Typography System

**Font Pairing (UI/UX Pro Max Recommendation):** `Space Grotesk` (Headings) + `DM Sans` (Body UI) + `Fira Code` (Telemetry Numbers).

```html
<!-- Google Fonts Import -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,400&family=Fira+Code:wght@400;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
```

### Font Scales & Usage

| Element | Font Family | Size | Weight | Line Height | Case / Style |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **App Header Title** | `Space Grotesk` | `24px` | `700` | `1.2` | Normal |
| **Card Header** | `Space Grotesk` | `16px` | `600` | `1.3` | Uppercase (`letter-spacing: 0.05em`) |
| **KPI Big Number** | `Fira Code` | `32px - 36px` | `700` | `1.0` | Monospace (Data Density) |
| **Body Label** | `DM Sans` | `14px` | `500` | `1.5` | Normal |
| **Small Telemetry/Badge** | `Fira Code` | `12px` | `600` | `1.4` | Monospace |

---

## 4. Component Design System & Bento Layout

### 4.1 Grid Layout Architecture (12-Column Grid)

```
+-----------------------------------------------------------------------------------------+
| HEADER BAR: Logo | CCTV Selector | System Time | Network Ping | Live FPS Badge         |
+-------------------------------------------------------------+---------------------------+
| MAIN FEED CONTAINER (8 Cols)                                | SIDEBAR STATS (4 Cols)    |
| +---------------------------------------------------------+ | +-----------------------+ |
| | LIVE VIDEO CANVAS (YOLOv11 Bounding Boxes & ROI Line)   | | | TRAFFIC STATUS BADGE  | |
| |                                                         | | | (LANCAR/SEDANG/MACET) | |
| |                                                         | | +-----------------------+ |
| |                                                         | | | KPI STAT CARDS        | |
| | [LIVE REC] [CAMERA: JL. SUDIRMAN ATCS] [SNAPSHOT BTN]   | | | Total | Motor | Mobil | |
| +---------------------------------------------------------+ | | Bus   | Truk  | ROI   | |
| | QUICK CONTROLS: Toggle Bbox | Toggle ROI | Reset Counter| | +-----------------------+ |
| +---------------------------------------------------------+ | | LIVE DENSITY CHART    | |
|                                                             | | (Chart.js Telemetry)  | |
|                                                             | +-----------------------+ |
+-------------------------------------------------------------+---------------------------+
| BOTTOM BAR: Multi-CCTV Thumbnail Carousel | Event Log Stream                            |
+-----------------------------------------------------------------------------------------+
```

### 4.2 Glass Card CSS Component Template

```css
.glass-card {
  background: var(--glass-bg);
  backdrop-filter: var(--backdrop-blur);
  -webkit-backdrop-filter: var(--backdrop-blur);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 20px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
}

.glass-card:hover {
  background: var(--glass-bg-hover);
  border-color: var(--glass-border-glow);
  transform: translateY(-2px);
  box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.15);
}
```

### 4.3 Live Status Indicator (Pulse Micro-Animation)

```css
.live-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 999px;
  color: #EF4444;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  font-weight: 700;
}

.live-dot {
  width: 8px;
  height: 8px;
  background-color: #EF4444;
  border-radius: 50%;
  box-shadow: 0 0 8px #EF4444;
  animation: pulse-glow 1.5s infinite ease-in-out;
}

@keyframes pulse-glow {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.3); }
}
```

---

## 5. Micro-Interactions & UX Best Practices

1. **Zero Cumulative Layout Shift (CLS):** Video Player memiliki *aspect ratio* tetap `16:9` agar kontainer tidak terdistorsi saat video dimuat.
2. **Instant Visual Feedback:** Tombol aksi (misal: *Take Snapshot*, *Toggle Line*) memberikan respon visual dalam 50ms (efek ripple / glow highlight).
3. **High Contrast Bounding Box:** Bounding Box YOLOv11 digambar dengan garis tebal 2px + *semi-transparent fill background* (opacity 15%) agar objek tetap terlihat jelas tanpa menutupi latar belakang.
4. **Number Ticker Animation:** Saat jumlah statistik kendaraan bertambah, angka berpindah secara halus menggunakan animasi *count-up*.
