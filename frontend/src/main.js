import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/telemetry";

// State Variables
let websocket = null;
let densityChart = null;
let drawBboxesState = true;
let drawRoiState = true;

// DOM Elements
const elFps = document.getElementById("val-fps");
const elClock = document.getElementById("val-clock");
const elCamName = document.getElementById("cam-name");
const elCamLoc = document.getElementById("cam-loc");
const elVideoLoader = document.getElementById("video-loader");
const elStatusText = document.getElementById("system-status-text");

// Video Player
const slotName1 = document.getElementById("slot-name-1");
const videoStream1 = document.getElementById("video-stream-1");

// Density Gauge Elements
const elDensityBadge = document.getElementById("density-badge");
const elDensityScore = document.getElementById("val-density-score");
const elProgressBar = document.getElementById("density-progress-bar");

// KPI Elements
const elTotalActive = document.getElementById("val-total-active");
const elRoiCount = document.getElementById("val-roi-count");
const elCarCount = document.getElementById("val-car-count");
const elMotorCount = document.getElementById("val-motor-count");
const elBusCount = document.getElementById("val-bus-count");
const elTruckCount = document.getElementById("val-truck-count");

// Button Elements
const btnBbox = document.getElementById("btn-toggle-bbox");
const btnRoi = document.getElementById("btn-toggle-roi");
const btnDrawRoi = document.getElementById("btn-draw-roi");
const btnSnapshot = document.getElementById("btn-snapshot");
const containerCctvList = document.getElementById("cctv-list");

// ROI Interactive Drawing Elements
const roiCanvas = document.getElementById("roi-draw-canvas");

let isDrawingRoi = false;
let roiPoint1 = null;

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
  startClock();
  initDensityChart();
  fetchCameras();
  connectWebSocket();
  bindEvents();
});

// Real-Time Clock
function startClock() {
  setInterval(() => {
    const now = new Date();
    elClock.textContent = now.toTimeString().split(' ')[0];
  }, 1000);
}

// Chart.js Real-time Density Trend Line
function initDensityChart() {
  const ctx = document.getElementById("densityChart").getContext("2d");
  const initialLabels = Array(15).fill("");
  const initialData = Array(15).fill(0);

  densityChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: initialLabels,
      datasets: [{
        label: 'Kendaraan (Active)',
        data: initialData,
        borderColor: '#00F2FE',
        borderWidth: 2,
        backgroundColor: (context) => {
          const chart = context.chart;
          const { ctx, chartArea } = chart;
          if (!chartArea) return null;
          const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          gradient.addColorStop(0, 'rgba(0, 242, 254, 0.35)');
          gradient.addColorStop(1, 'rgba(0, 242, 254, 0.0)');
          return gradient;
        },
        fill: true,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: '#111827',
          titleColor: '#F8FAFC',
          bodyColor: '#00F2FE',
          borderColor: 'rgba(255,255,255,0.1)',
          borderWidth: 1
        }
      },
      scales: {
        x: { display: false },
        y: {
          min: 0,
          suggestedMax: 20,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748B', font: { family: 'Fira Code', size: 10 } }
        }
      }
    }
  });
}

// WebSocket Communication
function connectWebSocket() {
  websocket = new WebSocket(WS_URL);

  websocket.onopen = () => {
    console.log("Connected to Telemetry WebSocket");
    elStatusText.textContent = "SYSTEM ONLINE";
    elVideoLoader.classList.add("hidden");
  };

  websocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateTelemetryUI(data);
    } catch (err) {
      console.error("Failed to parse telemetry JSON:", err);
    }
  };

  websocket.onclose = () => {
    console.warn("WebSocket disconnected. Reconnecting in 2s...");
    elStatusText.textContent = "RECONNECTING...";
    setTimeout(connectWebSocket, 2000);
  };

  websocket.onerror = (err) => {
    console.error("WebSocket Error:", err);
  };
}

// Telemetry UI Updates
function updateTelemetryUI(data) {
  if (!data) return;

  const t = data.telemetry_1 || {};

  if (data.active_camera_1 && slotName1) {
    slotName1.textContent = `LIVE: ${data.active_camera_1.toUpperCase()}`;
  }

  // active_counts  = kendaraan aktif di frame saat ini (untuk density & chart)
  // total_seen     = akumulasi kendaraan unik yang pernah terdeteksi (untuk dekomposisi)
  const active = t.active_counts || { total: 0, car: 0, motorcycle: 0, bus: 0, truck: 0 };
  const seen   = t.total_seen   || { car: 0, motorcycle: 0, bus: 0, truck: 0 };
  const totalCrossings = t.line_crossings || 0;
  const fps = t.fps || 0.0;

  // FPS
  elFps.textContent = fps.toFixed(1);

  // KPI cards
  animateNumber(elTotalActive, active.total);  // jumlah kendaraan aktif di frame ini
  animateNumber(elRoiCount, totalCrossings);

  // Dekomposisi — gunakan total_seen (akumulatif, tidak pernah kembali ke 0)
  animateNumber(elCarCount,   seen.car);
  animateNumber(elMotorCount, seen.motorcycle);
  animateNumber(elBusCount,   seen.bus);
  animateNumber(elTruckCount, seen.truck);

  // Density Status & Gauge — tetap berdasarkan active count (kondisi saat ini)
  const totalVehicles = active.total;
  let status = "LANCAR";
  let score = 0;

  if (totalVehicles < 8) {
    status = "LANCAR";
    score = clamp(Math.floor((totalVehicles / 8) * 35), 0, 100);
  } else if (totalVehicles <= 18) {
    status = "SEDANG";
    score = 35 + Math.floor(((totalVehicles - 8) / 10) * 35);
  } else {
    status = "MACET";
    score = clamp(70 + (totalVehicles - 18) * 3, 0, 100);
  }

  elDensityScore.textContent = score;
  elProgressBar.style.width = `${score}%`;
  elDensityBadge.textContent = status;
  elDensityBadge.className = `density-badge badge-${status.toLowerCase()}`;
  elProgressBar.className = `density-progress-fill fill-${status.toLowerCase()}`;

  // Update Chart — gunakan active count (real-time)
  if (densityChart) {
    const dataset = densityChart.data.datasets[0].data;
    dataset.shift();
    dataset.push(active.total);
    densityChart.update('none');
  }
}

function clamp(val, min, max) {
  return Math.max(min, Math.min(max, val));
}

function animateNumber(element, newValue) {
  if (!element) return;
  const currentVal = parseInt(element.textContent) || 0;
  if (currentVal !== newValue) {
    element.textContent = newValue;
  }
}

// Camera List
async function fetchCameras() {
  try {
    const res = await fetch(`${API_BASE}/api/cameras`);
    const data = await res.json();

    if (data.active_camera) {
      elCamName.textContent = data.active_camera.name.toUpperCase();
      elCamLoc.textContent = `${data.active_camera.location.toUpperCase()} • LIVE FEED`;
    } else if (data.active_camera_1) {
      elCamName.textContent = data.active_camera_1.name.toUpperCase();
      elCamLoc.textContent = `${data.active_camera_1.location.toUpperCase()} • LIVE FEED`;
    }

    renderCctvList(data.cameras, data.active_id_1);
  } catch (err) {
    console.error("Error fetching camera list:", err);
  }
}

function renderCctvList(cameras, activeId) {
  if (!containerCctvList || !cameras) return;
  containerCctvList.innerHTML = "";

  const tagCount = document.getElementById("cctv-count-tag");
  if (tagCount) {
    tagCount.textContent = `${cameras.length} Preset Available`;
  }

  cameras.forEach(cam => {
    const isActive = cam.id === activeId;

    const btn = document.createElement("button");
    btn.className = `cctv-item-btn ${isActive ? "active active-slot1" : ""}`;
    btn.innerHTML = `
      <div class="cctv-thumb-icon">
        <i data-lucide="video"></i>
      </div>
      <div class="cctv-btn-info">
        <div class="cctv-name">${cam.name}</div>
        <div class="cctv-loc">${cam.location}</div>
      </div>
      ${isActive ? `<span class="badge-slot slot1">AKTIF</span>` : ""}
    `;

    btn.addEventListener("click", () => selectCamera(cam));
    containerCctvList.appendChild(btn);
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }
}

async function selectCamera(cam) {
  try {
    elVideoLoader.classList.remove("hidden");
    const res = await fetch(`${API_BASE}/api/stream/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ camera_id: cam.id })
    });

    if (res.ok) {
      const data = await res.json();
      elCamName.textContent = cam.name.toUpperCase();
      elCamLoc.textContent = `${cam.location.toUpperCase()} • LIVE FEED`;

      videoStream1.src = `${API_BASE}/api/stream/video?t=${Date.now()}`;

      renderCctvList(data.cameras, data.active_camera?.id || data.active_id_1);
      setTimeout(() => elVideoLoader.classList.add("hidden"), 1500);
    }
  } catch (err) {
    console.error("Error selecting camera:", err);
    elVideoLoader.classList.add("hidden");
  }
}

// Event Listeners
function bindEvents() {
  // Bbox Toggle
  btnBbox.addEventListener("click", () => {
    drawBboxesState = !drawBboxesState;
    btnBbox.classList.toggle("active", drawBboxesState);
    sendToggleOverlays();
  });

  // ROI Toggle
  btnRoi.addEventListener("click", () => {
    drawRoiState = !drawRoiState;
    btnRoi.classList.toggle("active", drawRoiState);
    sendToggleOverlays();
  });

  // Atur ROI Line Button (Interactive Drawing)
  if (btnDrawRoi) {
    btnDrawRoi.addEventListener("click", () => {
      if (isDrawingRoi) {
        stopRoiDrawing();
      } else {
        startRoiDrawing();
      }
    });
  }

  // Canvas Mouse Events for ROI Drawing
  if (roiCanvas) {
    roiCanvas.addEventListener("click", (e) => {
      if (!isDrawingRoi) return;

      const streamImg = document.getElementById("video-stream-1");
      const imgRect = streamImg ? streamImg.getBoundingClientRect() : roiCanvas.getBoundingClientRect();
      const clickX = e.clientX - imgRect.left;
      const clickY = e.clientY - imgRect.top;

      if (!roiPoint1) {
        // Point 1
        roiPoint1 = { x: clickX, y: clickY, clientX: e.clientX, clientY: e.clientY };
        drawCanvasOverlay(roiPoint1, null);
      } else {
        // Point 2 - Complete Drawing
        const roiPoint2 = { x: clickX, y: clickY, clientX: e.clientX, clientY: e.clientY };
        drawCanvasOverlay(roiPoint1, roiPoint2);

        // Convert canvas relative coords to 1280x720 reference resolution using actual video rect
        const p1_scaled = [
          Math.max(0, Math.min(1280, Math.round(((roiPoint1.clientX - imgRect.left) / imgRect.width) * 1280))),
          Math.max(0, Math.min(720, Math.round(((roiPoint1.clientY - imgRect.top) / imgRect.height) * 720)))
        ];
        const p2_scaled = [
          Math.max(0, Math.min(1280, Math.round(((roiPoint2.clientX - imgRect.left) / imgRect.width) * 1280))),
          Math.max(0, Math.min(720, Math.round(((roiPoint2.clientY - imgRect.top) / imgRect.height) * 720)))
        ];

        // Send new line to backend
        sendCustomRoiLine(p1_scaled, p2_scaled);

        // Immediately hide drawing canvas so duplicate line vanishes
        setTimeout(() => {
          stopRoiDrawing();
        }, 150);
      }
    });

    roiCanvas.addEventListener("mousemove", (e) => {
      if (!isDrawingRoi || !roiPoint1) return;
      const streamImg = document.getElementById("video-stream-1");
      const imgRect = streamImg ? streamImg.getBoundingClientRect() : roiCanvas.getBoundingClientRect();
      const currentMouse = { x: e.clientX - imgRect.left, y: e.clientY - imgRect.top };
      drawCanvasOverlay(roiPoint1, currentMouse, true);
    });
  }

  // Snapshot
  btnSnapshot.addEventListener("click", () => {
    window.open(`${API_BASE}/api/snapshot`, '_blank');
  });

  // Custom Stream Modal
  const modal = document.getElementById("custom-modal");
  const btnOpenModal = document.getElementById("btn-open-custom");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnCancelModal = document.getElementById("btn-cancel-modal");
  const formCustom = document.getElementById("form-custom-cctv");

  if (btnOpenModal && modal) {
    btnOpenModal.addEventListener("click", () => modal.classList.remove("hidden"));

    const closeModal = () => modal.classList.add("hidden");
    if (btnCloseModal) btnCloseModal.addEventListener("click", closeModal);
    if (btnCancelModal) btnCancelModal.addEventListener("click", closeModal);

    formCustom.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("input-cam-name").value;
      const location = document.getElementById("input-cam-loc").value;
      const url = document.getElementById("input-cam-url").value;

      try {
        elVideoLoader.classList.remove("hidden");
        modal.classList.add("hidden");

        const res = await fetch(`${API_BASE}/api/stream/custom`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, location, url, type: "hls" })
        });

        if (res.ok) {
          const data = await res.json();
          elCamName.textContent = name.toUpperCase();
          elCamLoc.textContent = `${location.toUpperCase()} • LIVE FEED`;
          videoStream1.src = `${API_BASE}/api/stream/video?t=${Date.now()}`;
          renderCctvList(data.cameras, data.active_camera?.id || data.active_id_1);
          formCustom.reset();
        }
      } catch (err) {
        console.error("Error adding custom CCTV stream:", err);
      } finally {
        setTimeout(() => elVideoLoader.classList.add("hidden"), 1500);
      }
    });
  }
}

// ROI Interactive Drawing Functions
function startRoiDrawing() {
  isDrawingRoi = true;
  roiPoint1 = null;
  
  const streamImg = document.getElementById("video-stream-1");
  const rect = streamImg ? streamImg.getBoundingClientRect() : document.getElementById("video-container").getBoundingClientRect();

  roiCanvas.width = rect.width;
  roiCanvas.height = rect.height;

  roiCanvas.classList.remove("hidden");
  btnDrawRoi.classList.add("active");

  const ctx = roiCanvas.getContext("2d");
  ctx.clearRect(0, 0, roiCanvas.width, roiCanvas.height);
}

function stopRoiDrawing() {
  isDrawingRoi = false;
  roiPoint1 = null;
  if (roiCanvas) {
    const ctx = roiCanvas.getContext("2d");
    ctx.clearRect(0, 0, roiCanvas.width, roiCanvas.height);
    roiCanvas.classList.add("hidden");
  }
  if (btnDrawRoi) btnDrawRoi.classList.remove("active");
}

function drawCanvasOverlay(p1, p2, isPreview = false) {
  if (!roiCanvas) return;
  const ctx = roiCanvas.getContext("2d");
  ctx.clearRect(0, 0, roiCanvas.width, roiCanvas.height);

  if (p1) {
    // Draw Point 1 Glowing Circle
    ctx.beginPath();
    ctx.arc(p1.x, p1.y, 7, 0, 2 * Math.PI);
    ctx.fillStyle = "#00F2FE";
    ctx.fill();
    ctx.shadowColor = "#00F2FE";
    ctx.shadowBlur = 12;
    ctx.lineWidth = 3;
    ctx.strokeStyle = "#FFFFFF";
    ctx.stroke();

    // Point 1 Tag
    ctx.font = "bold 11px Fira Code, sans-serif";
    ctx.fillStyle = "#00F2FE";
    ctx.fillText("POINT 1", p1.x + 12, p1.y + 4);
  }

  if (p2) {
    // Draw Line
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#00F2FE";
    ctx.setLineDash(isPreview ? [8, 6] : []);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw Point 2 Glowing Circle
    ctx.beginPath();
    ctx.arc(p2.x, p2.y, 7, 0, 2 * Math.PI);
    ctx.fillStyle = isPreview ? "#F69D3B" : "#00F2FE";
    ctx.fill();
    ctx.stroke();

    if (!isPreview) {
      ctx.fillStyle = "#00F2FE";
      ctx.fillText("POINT 2", p2.x + 12, p2.y + 4);
    }
  }
}

async function sendCustomRoiLine(p1, p2) {
  try {
    const res = await fetch(`${API_BASE}/api/stream/roi`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ p1: p1, p2: p2 })
    });

    if (res.ok) {
      // Enable ROI line rendering if turned off
      drawRoiState = true;
      btnRoi.classList.add("active");
      sendToggleOverlays();

      setTimeout(() => {
        stopRoiDrawing();
      }, 150);
    }
  } catch (err) {
    console.error("Error setting custom ROI line:", err);
    setTimeout(() => stopRoiDrawing(), 150);
  }
}

async function sendToggleOverlays() {
  try {
    await fetch(`${API_BASE}/api/stream/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        draw_bboxes: drawBboxesState,
        draw_roi: drawRoiState
      })
    });
  } catch (err) {
    console.error("Error toggling overlays:", err);
  }
}
