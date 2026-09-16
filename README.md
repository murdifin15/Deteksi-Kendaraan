# Sistem Deteksi Kendaraan dan Analisis Lalu Lintas Real-Time (YOLO11 & FastAPI)

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![YOLO11](https://img.shields.io/badge/YOLO-v11-00FFFF.svg)](https://docs.ultralytics.com/)
[![Vite](https://img.shields.io/badge/Vite-5.0-646CFF.svg)](https://vitejs.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Sistem Transportasi Cerdas (Intelligent Transportation System / ITS) berbasis **YOLO11**, **ByteTrack**, **FastAPI**, dan **Dashboard Web Interaktif**. Aplikasi ini memproses aliran video CCTV publik (protokol RTSP/HLS atau berkas video MP4 lokal) secara langsung (real-time) untuk klasifikasi kendaraan, pelacakan pergerakan, estimasi tingkat kepadatan lalu lintas, penghitungan kendaraan berbasis garis batas ROI (line-crossing), serta streaming telemetri melalui WebSocket.

---

## Fitur Utama

- **Deteksi dan Pelacakan Objek (YOLO11 & ByteTrack)**: Deteksi langsung dan pelacakan presisi (ByteTrack) untuk 4 kategori kendaraan utama:
  - Mobil (Car)
  - Sepeda Motor (Motorcycle)
  - Bus
  - Truk (Truck)
- **Analisis Lalu Lintas Real-Time**:
  - **Penghitungan Kendaraan Aktif**: Rincian jumlah kendaraan per kelas yang berada di dalam frame secara langsung.
  - **Klasifikasi Kepadatan Lalu Lintas**: Menghitung tingkat kepadatan lalu lintas (LANCAR < 8, SEDANG 8-18, MACET > 18).
  - **Penghitungan Garis Batas Virtual (ROI Line Crossing)**: Melacak dan menghitung akumulasi kendaraan yang melintasi garis pemantauan yang ditentukan.
- **Streaming Multicast Terpisah (Decoupled)**: Thread inferensi latar belakang berjalan pada ~30 FPS; mendukung banyak klien dashboard secara bersamaan tanpa redundansi komputasi model AI.
- **Dashboard Web Interaktif**:
  - Tampilan antarmuka pusat kendali berbasis *Dark Glassmorphism*.
  - Pemutar video stream MJPEG dengan opsi sakelar tampilan bounding box dan garis batas ROI.
  - Grafik tren volume lalu lintas real-time menggunakan Chart.js.
  - Menu pemilih sumber kamera CCTV (preset switcher).
  - Fitur unduh tangkapan layar (snapshot) beranotasi kualitas tinggi.

---

## Arsitektur Sistem

`mermaid
flowchart TD
    subgraph Sumber_Video["1. Sumber Umpan Video"]
        RTSP["Aliran RTSP Publik"]
        HLS["Aliran HLS (.m3u8) Publik"]
        Local["Berkas Sampel MP4 Lokal"]
    end

    subgraph Backend_Engine["2. Backend FastAPI & Mesin AI"]
        Decoder["Dekoder Aliran OpenCV"]
        YOLO["Mesin Ultralytics YOLO11"]
        Tracker["Pelacak Objek ByteTrack"]
        Analytics["Modul Analisis (Kepadatan & ROI)"]
    end

    subgraph Transmisi["3. Lapisan Transmisi Real-Time"]
        MJPEG["Streamer Video MJPEG (/api/stream/video)"]
        WS["Server Telemetri WebSocket (/ws/telemetry)"]
    end

    subgraph Frontend_UI["4. Dashboard Antarmuka Web"]
        Player["Kanvas Pemutar Video"]
        KPIs["Kartu Telemetri & Status Kepadatan"]
        Chart["Grafik Tren Real-Time Chart.js"]
        Controls["Pengalih Kamera & Sakelar Overlay"]
    end

    Sumber_Video --> Decoder
    Decoder --> YOLO
    YOLO --> Tracker
    Tracker --> Analytics
    Analytics --> MJPEG
    Analytics --> WS
    MJPEG --> Player
    WS --> KPIs
    WS --> Chart
    Controls --> Decoder
`

---

## Prasyarat Sistem

- **Python 3.10+**
- **Node.js 18+** & **npm**
- **FFmpeg** (Disarankan untuk pemutaran aliran HLS pada OpenCV)

---

## Panduan Instalasi dan Penggunaan

### 1. Konfigurasi Backend (FastAPI & YOLO11)

1. Masuk ke direktori backend:
   `ash
   cd backend
   `

2. Buat dan aktifkan virtual environment (opsional tetapi disarankan):
   `ash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   `

3. Pasang paket dependensi yang diperlukan:
   `ash
   pip install -r requirements.txt
   `

4. Jalankan server FastAPI:
   `ash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   `

   - Dokumentasi Interaktif Swagger UI: http://localhost:8000/docs
   - Aliran Video MJPEG: http://localhost:8000/api/stream/video
   - Endpoint WebSocket Telemetri: ws://localhost:8000/ws/telemetry

---

### 2. Konfigurasi Frontend (Dashboard Web)

1. Buka terminal baru dan masuk ke direktori frontend:
   `ash
   cd frontend
   `

2. Pasang paket npm:
   `ash
   npm install
   `

3. Jalankan server pengembang Vite:
   `ash
   npm run dev
   `

4. Buka peramban (browser) dan akses alamat:
   `	ext
   http://localhost:3000
   `

---

## Daftar Endpoint API

| Metode | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| GET | /api/health | Status server backend, kamera aktif, versi model, dan FPS langsung |
| GET | /api/cameras | Daftar preset sumber aliran kamera CCTV yang tersedia |
| POST | /api/stream/select | Mengubah sumber kamera aktif ({ "camera_id": "cam-01" }) |
| POST | /api/stream/toggle | Mengaktifkan/menonaktifkan overlay bounding box dan garis ROI |
| GET | /api/stream/video | Aliran video real-time berformat MJPEG |
| WS | /ws/telemetry | Endpoint WebSocket penyiaran data telemetri JSON (frekuensi 5Hz) |
| GET | /api/snapshot | Mengunduh berkas tangkapan layar JPEG dari frame terkini |

---

## Struktur Direktori Repositori

`	ext
Deteksi-Kendaraan/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── analytics.py        # Logika penghitungan kendaraan, status kepadatan, dan ROI
│   │   ├── config.py           # Konfigurasi preset, pemetaan kelas kendaraan, dan koordinat ROI
│   │   ├── detector.py         # Integrasi model YOLO11 dan ByteTrack
│   │   ├── main.py             # Endpoint REST API FastAPI dan server WebSocket
│   │   └── stream_handler.py   # Pengambilan video stream OpenCV dan rekoneksi otomatis
│   ├── assets/
│   │   └── sample_cctv.mp4     # Sampel video lokal untuk pengujian luring (offline)
│   ├── requirements.txt        # Dependensi pustaka Python backend
│   └── yolo11n.pt              # Bobot model Ultralytics YOLO11 Nano
├── frontend/
│   ├── index.html              # Tata letak antarmuka dashboard
│   ├── package.json            # Konfigurasi dependensi JavaScript
│   └── src/
│       ├── main.js             # Koneksi WebSocket, integrasi Chart.js, dan pengendali UI
│       └── styles/
│           └── index.css       # Gaya tampilan Dark Glassmorphism dan animasi
├── LICENSE                     # Lisensi MIT (Murdifin)
├── PRD.md                      # Dokumen Persyaratan Produk (PRD)
├── StyleGuide.md               # Panduan gaya desain antarmuka (UI/UX)
├── Tasks.md                    # Daftar tugas dan peta jalan pengembangan
└── README.md                   # Dokumentasi proyek
`

---

## Lisensi

Proyek ini dilisensikan di bawah [MIT License](LICENSE) - Hak Cipta (c) 2026 **Murdifin**.