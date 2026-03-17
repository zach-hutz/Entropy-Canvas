const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");

const presetSelect = document.getElementById("preset");
const themeSelect = document.getElementById("theme");
const forgeButton = document.getElementById("forgeButton");
const resetButton = document.getElementById("resetButton");
const copyButton = document.getElementById("copyButton");
const clearClipboardButton = document.getElementById("clearClipboardButton");
const secretBox = document.getElementById("secretBox");
const outputLabel = document.getElementById("outputLabel");
const strengthChip = document.getElementById("strengthChip");
const bitsValue = document.getElementById("bitsValue");
const hashPreview = document.getElementById("hashPreview");
const fingerprintPreview = document.getElementById("fingerprintPreview");
const eventCountEl = document.getElementById("eventCount");
const readinessLabel = document.getElementById("readinessLabel");
const entropyScoreEl = document.getElementById("entropyScore");
const meterFill = document.getElementById("meterFill");
const coverageValue = document.getElementById("coverageValue");
const turnValue = document.getElementById("turnValue");
const pauseValue = document.getElementById("pauseValue");
const clickValue = document.getElementById("clickValue");
const toast = document.getElementById("toast");

const particles = [];
const nodes = [];
const ripples = [];
const capturedEvents = [];
const visitedCells = new Set();

let width = window.innerWidth;
let height = window.innerHeight;
let lastCaptureTime = performance.now();
let lastPoint = null;
let lastVector = null;
let directionChanges = 0;
let pauses = 0;
let clicks = 0;
let outputSecret = "";
let pointerActive = false;
let currentTheme = "default";

const maxParticles = 240;
const thresholdScore = 68;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function rand(min, max) {
  return min + Math.random() * (max - min);
}

function resizeCanvas() {
  width = window.innerWidth;
  height = window.innerHeight;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function particleColorForTheme(theme) {
  if (theme === "forest") {
    return `hsla(${rand(82, 118)}, 76%, ${rand(60, 76)}%, ${rand(0.16, 0.42)})`;
  }
  if (theme === "prism") {
    return `hsla(${rand(185, 330)}, 92%, ${rand(64, 76)}%, ${rand(0.18, 0.5)})`;
  }
  if (theme === "ember") {
    return `hsla(${rand(14, 48)}, 96%, ${rand(56, 72)}%, ${rand(0.22, 0.56)})`;
  }
  return `hsla(${rand(188, 255)}, 95%, ${rand(70, 82)}%, ${rand(0.18, 0.46)})`;
}

function seedParticles() {
  particles.length = 0;
  nodes.length = 0;

  for (let index = 0; index < maxParticles; index += 1) {
    const risingBias =
      currentTheme === "ember"
        ? rand(-0.5, -0.1)
        : (Math.random() - 0.5) * 0.28;
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * (currentTheme === "forest" ? 0.18 : 0.32),
      vy: risingBias,
      radius: Math.random() * 2.4 + 0.7,
      life: Math.random(),
      angle: Math.random() * Math.PI * 2,
      spin: (Math.random() - 0.5) * 0.02,
      color: particleColorForTheme(currentTheme),
    });
  }
}

function applyTheme(theme) {
  currentTheme = theme;
  document.body.dataset.theme = theme;
  seedParticles();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(
    () => toast.classList.remove("visible"),
    1600,
  );
}

function createRipple(x, y, intensity = 1) {
  ripples.push({
    x,
    y,
    radius: currentTheme === "ember" ? 10 : 6,
    alpha: Math.min(0.36 * intensity, 0.72),
    speed: 1.2 + intensity * 2.8,
    theme: currentTheme,
  });
}

function nodeHueForTheme(theme) {
  if (theme === "forest") return 92 + Math.random() * 26;
  if (theme === "prism") return 185 + Math.random() * 135;
  if (theme === "ember") return 12 + Math.random() * 36;
  return 190 + Math.random() * 80;
}

function pushNode(x, y, power = 1) {
  nodes.push({
    x,
    y,
    power: Math.min(1.85, power),
    life: 1,
    hue: nodeHueForTheme(currentTheme),
    theme: currentTheme,
    sway: rand(-1.1, 1.1),
    branchSeed: rand(0.7, 1.25),
    birth: performance.now(),
  });

  if (nodes.length > 58) {
    nodes.shift();
  }
}

function captureEvent(type, x, y, pressure = 0) {
  const now = performance.now();
  const dt = Math.min(2000, Math.max(0, Math.round(now - lastCaptureTime)));
  lastCaptureTime = now;

  const event = {
    type,
    x: Math.max(0, Math.min(width, Math.round(x))),
    y: Math.max(0, Math.min(height, Math.round(y))),
    dt,
    pressure: Math.max(0, Math.min(1024, Math.round(pressure * 1024))),
  };

  capturedEvents.push(event);
  if (capturedEvents.length > 4096) {
    capturedEvents.shift();
  }

  const cellX = Math.floor((event.x / Math.max(width, 1)) * 18);
  const cellY = Math.floor((event.y / Math.max(height, 1)) * 12);
  visitedCells.add(`${cellX}:${cellY}`);

  if (dt > 120) {
    pauses += 1;
  }

  if (type === "down" || type === "click") {
    clicks += 1;
  }

  if (lastPoint) {
    const dx = event.x - lastPoint.x;
    const dy = event.y - lastPoint.y;
    const magnitude = Math.hypot(dx, dy);
    if (magnitude > 2) {
      const vector = { x: dx / magnitude, y: dy / magnitude };
      if (lastVector) {
        const dot = vector.x * lastVector.x + vector.y * lastVector.y;
        if (dot < 0.15) {
          directionChanges += 1;
        }
      }
      lastVector = vector;
    }
  }

  lastPoint = { x: event.x, y: event.y };
  updateReadiness();
}

function updateReadiness(serverSummary = null) {
  const coverage = serverSummary?.unique_cells ?? visitedCells.size;
  const turns = serverSummary?.direction_changes ?? directionChanges;
  const pauseCount = serverSummary?.pauses ?? pauses;
  const clickCount = serverSummary?.clicks ?? clicks;

  coverageValue.textContent = coverage;
  turnValue.textContent = turns;
  pauseValue.textContent = pauseCount;
  clickValue.textContent = clickCount;
  eventCountEl.textContent = capturedEvents.length;

  const score = Math.min(
    100,
    Math.round(
      (Math.min(coverage, 36) / 36) * 46 +
        (Math.min(turns, 36) / 36) * 24 +
        (Math.min(pauseCount, 22) / 22) * 15 +
        (Math.min(clickCount, 10) / 10) * 15,
    ),
  );

  entropyScoreEl.textContent = `${score}%`;
  meterFill.style.width = `${score}%`;

  let readiness = "Low";
  if (score >= thresholdScore) {
    readiness = "Ready";
  } else if (score >= 48) {
    readiness = "Rising";
  }
  readinessLabel.textContent = readiness;

  forgeButton.disabled = !(
    score >= thresholdScore && capturedEvents.length >= 60
  );
}

function resetSession() {
  capturedEvents.length = 0;
  visitedCells.clear();
  nodes.length = 0;
  ripples.length = 0;
  directionChanges = 0;
  pauses = 0;
  clicks = 0;
  outputSecret = "";
  lastPoint = null;
  lastVector = null;
  lastCaptureTime = performance.now();

  secretBox.textContent = "Move through the canvas to begin.";
  outputLabel.textContent = "No secret forged yet";
  strengthChip.textContent = "Awaiting entropy";
  strengthChip.style.color = "var(--success)";
  strengthChip.style.borderColor = "rgba(151, 240, 178, 0.2)";
  strengthChip.style.background = "rgba(151, 240, 178, 0.08)";
  bitsValue.textContent = "--";
  hashPreview.textContent = "--";
  fingerprintPreview.textContent = "--";
  fingerprintPreview.title = "";
  copyButton.disabled = true;
  clearClipboardButton.disabled = true;
  updateReadiness();
}

function drawBackgroundGlow() {
  if (currentTheme === "forest") {
    const canopy = ctx.createRadialGradient(
      width * 0.25,
      height * 0.18,
      0,
      width * 0.25,
      height * 0.18,
      width * 0.58,
    );
    canopy.addColorStop(0, "rgba(125, 214, 105, 0.08)");
    canopy.addColorStop(0.45, "rgba(56, 97, 43, 0.05)");
    canopy.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = canopy;
    ctx.fillRect(0, 0, width, height);

    const ground = ctx.createLinearGradient(0, height * 0.56, 0, height);
    ground.addColorStop(0, "rgba(0, 0, 0, 0)");
    ground.addColorStop(0.55, "rgba(38, 25, 10, 0.05)");
    ground.addColorStop(1, "rgba(56, 31, 12, 0.16)");
    ctx.fillStyle = ground;
    ctx.fillRect(0, 0, width, height);
    return;
  }

  if (currentTheme === "prism") {
    const gradient = ctx.createRadialGradient(
      width * 0.52,
      height * 0.5,
      0,
      width * 0.52,
      height * 0.5,
      Math.max(width, height) * 0.58,
    );
    gradient.addColorStop(0, "rgba(196, 96, 255, 0.14)");
    gradient.addColorStop(0.34, "rgba(48, 206, 255, 0.11)");
    gradient.addColorStop(0.68, "rgba(255, 152, 86, 0.07)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    for (let band = 0; band < 4; band += 1) {
      const y = height * 0.18 + band * height * 0.18;
      ctx.beginPath();
      for (let x = -80; x <= width + 80; x += 24) {
        const wave =
          Math.sin(x * 0.008 + performance.now() * 0.00045 + band * 0.75) *
          (18 + band * 5);
        const py = y + wave;
        if (x === -80) ctx.moveTo(x, py);
        else ctx.lineTo(x, py);
      }
      ctx.strokeStyle = `rgba(${band % 2 === 0 ? "104, 225, 255" : "226, 120, 255"}, ${0.05 + band * 0.015})`;
      ctx.lineWidth = 14 - band * 2;
      ctx.stroke();
    }
    return;
  }

  if (currentTheme === "ember") {
    const core = ctx.createRadialGradient(
      width * 0.5,
      height * 0.86,
      0,
      width * 0.5,
      height * 0.86,
      width * 0.72,
    );
    core.addColorStop(0, "rgba(255, 110, 58, 0.18)");
    core.addColorStop(0.25, "rgba(255, 167, 73, 0.14)");
    core.addColorStop(0.55, "rgba(110, 28, 12, 0.10)");
    core.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = core;
    ctx.fillRect(0, 0, width, height);

    for (let band = 0; band < 4; band += 1) {
      const y = height * (0.8 + band * 0.045);
      ctx.beginPath();
      ctx.moveTo(-60, y);
      for (let x = -60; x <= width + 60; x += 18) {
        const wave =
          Math.sin(x * 0.012 + performance.now() * 0.0015 + band) *
          (8 + band * 3);
        ctx.lineTo(x, y + wave);
      }
      ctx.lineTo(width + 60, height + 80);
      ctx.lineTo(-60, height + 80);
      ctx.closePath();
      ctx.fillStyle = `rgba(${band === 0 ? "255, 96, 42" : band === 1 ? "255, 139, 58" : band === 2 ? "149, 39, 18" : "58, 11, 8"}, ${0.12 + band * 0.05})`;
      ctx.fill();
    }
    return;
  }

  const gradient = ctx.createRadialGradient(
    width * 0.5,
    height * 0.55,
    0,
    width * 0.5,
    height * 0.55,
    Math.max(width, height) * 0.55,
  );
  gradient.addColorStop(0, "rgba(62, 103, 255, 0.12)");
  gradient.addColorStop(0.4, "rgba(0, 196, 255, 0.07)");
  gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);
}

function drawRipples() {
  for (const ripple of ripples) {
    ripple.radius += ripple.speed;
    ripple.alpha *= 0.972;

    ctx.beginPath();
    ctx.arc(ripple.x, ripple.y, ripple.radius, 0, Math.PI * 2);

    if (ripple.theme === "forest") {
      ctx.strokeStyle = `rgba(157, 234, 122, ${ripple.alpha})`;
      ctx.lineWidth = 1.4;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(ripple.x, ripple.y, ripple.radius * 0.68, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255, 206, 131, ${ripple.alpha * 0.38})`;
      ctx.lineWidth = 0.9;
      ctx.stroke();
    } else if (ripple.theme === "prism") {
      ctx.strokeStyle = `rgba(116, 233, 255, ${ripple.alpha})`;
      ctx.lineWidth = 2.2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(ripple.x, ripple.y, ripple.radius * 1.18, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(221, 122, 255, ${ripple.alpha * 0.45})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    } else if (ripple.theme === "ember") {
      ctx.strokeStyle = `rgba(255, 150, 70, ${ripple.alpha})`;
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(ripple.x, ripple.y, ripple.radius * 0.52, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255, 220, 120, ${ripple.alpha * 0.42})`;
      ctx.lineWidth = 1;
      ctx.stroke();
    } else {
      ctx.strokeStyle = `rgba(110, 219, 255, ${ripple.alpha})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
  }

  for (let index = ripples.length - 1; index >= 0; index -= 1) {
    if (ripples[index].alpha < 0.02) {
      ripples.splice(index, 1);
    }
  }
}

function updateParticles() {
  for (const particle of particles) {
    particle.x += particle.vx;
    particle.y += particle.vy;
    particle.angle += particle.spin;

    if (currentTheme === "ember") {
      if (particle.y < -20) {
        particle.y = height + rand(20, 120);
        particle.x = rand(-20, width + 20);
        particle.vy = rand(-0.9, -0.18);
      }
      if (particle.x < -30) particle.x = width + 30;
      if (particle.x > width + 30) particle.x = -30;
    } else {
      if (particle.x < -20) particle.x = width + 20;
      if (particle.x > width + 20) particle.x = -20;
      if (particle.y < -20) particle.y = height + 20;
      if (particle.y > height + 20) particle.y = -20;
    }

    for (const node of nodes) {
      const dx = node.x - particle.x;
      const dy = node.y - particle.y;
      const dist = Math.max(22, Math.hypot(dx, dy));
      let pull = 0.0035 * node.power;

      if (currentTheme === "forest") pull = 0.0024 * node.power;
      if (currentTheme === "prism") pull = 0.0043 * node.power;
      if (currentTheme === "ember") {
        pull = 0.0028 * node.power;
        particle.vy -= 0.0016 * node.power;
      }

      particle.vx += (dx / dist) * pull;
      particle.vy += (dy / dist) * pull;
    }

    const damp =
      currentTheme === "forest"
        ? 0.992
        : currentTheme === "ember"
          ? 0.989
          : 0.996;
    particle.vx *= damp;
    particle.vy *= damp;
  }
}

function drawDefaultScene() {
  for (const particle of particles) {
    ctx.beginPath();
    ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(207, 231, 255, 0.45)";
    ctx.fill();
  }

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    node.life *= 0.984;

    const nodeGlow = ctx.createRadialGradient(
      node.x,
      node.y,
      0,
      node.x,
      node.y,
      120 * node.power,
    );
    nodeGlow.addColorStop(
      0,
      `hsla(${node.hue}, 100%, 72%, ${0.22 * node.life})`,
    );
    nodeGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = nodeGlow;
    ctx.fillRect(node.x - 120, node.y - 120, 240, 240);

    for (let inner = index + 1; inner < nodes.length; inner += 1) {
      const other = nodes[inner];
      const dist = Math.hypot(node.x - other.x, node.y - other.y);
      if (dist < 160) {
        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.lineTo(other.x, other.y);
        ctx.strokeStyle = `rgba(139, 124, 255, ${(1 - dist / 160) * 0.18 * Math.min(node.life, other.life)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, 3.2 + node.power * 1.4, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${node.hue}, 100%, 70%, ${0.9 * node.life})`;
    ctx.fill();
  }
}

function drawForestScene() {
  const soil = ctx.createLinearGradient(0, height * 0.72, 0, height);
  soil.addColorStop(0, "rgba(0, 0, 0, 0)");
  soil.addColorStop(0.52, "rgba(38, 24, 12, 0.10)");
  soil.addColorStop(1, "rgba(60, 33, 12, 0.22)");
  ctx.fillStyle = soil;
  ctx.fillRect(0, 0, width, height);

  ctx.save();
  ctx.globalCompositeOperation = "lighter";
  for (const particle of particles) {
    const glow = ctx.createRadialGradient(
      particle.x,
      particle.y,
      0,
      particle.x,
      particle.y,
      16 + particle.radius * 3.6,
    );
    glow.addColorStop(0, particle.color);
    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(particle.x - 22, particle.y - 22, 44, 44);
  }
  ctx.restore();

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    node.life *= 0.982;

    const anchorX = node.x + Math.sin(node.birth * 0.0013 + node.sway) * 28;
    const anchorY = height + 30;
    const bendY = height - (34 + node.power * 22);
    const midX =
      (anchorX + node.x) * 0.5 +
      Math.sin(performance.now() * 0.0012 + node.sway) * 22;

    ctx.beginPath();
    ctx.moveTo(anchorX, anchorY);
    ctx.bezierCurveTo(
      anchorX + node.sway * 16,
      bendY,
      midX,
      node.y + 26,
      node.x,
      node.y,
    );
    ctx.strokeStyle = `rgba(94, 63, 34, ${0.3 * node.life})`;
    ctx.lineWidth = 1.4 + node.power * 2.3;
    ctx.stroke();

    for (let branch = 0; branch < 3; branch += 1) {
      const side = branch % 2 === 0 ? -1 : 1;
      const startY = anchorY - (36 + branch * 24 + node.power * 10);
      const startX = anchorX + side * (5 + branch * 4);
      const endX = startX + side * (18 + node.power * 12 + branch * 8);
      const endY = startY - (14 + branch * 10);

      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.quadraticCurveTo(
        startX + side * (9 + branch * 3),
        startY - 10,
        endX,
        endY,
      );
      ctx.strokeStyle = `rgba(121, 84, 44, ${0.16 * node.life})`;
      ctx.lineWidth = 0.8 + node.power * 0.7;
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(endX + side * 9, endY - 5);
      ctx.strokeStyle = `rgba(142, 103, 61, ${0.11 * node.life})`;
      ctx.lineWidth = 0.6;
      ctx.stroke();
    }

    for (let inner = index + 1; inner < nodes.length; inner += 1) {
      const other = nodes[inner];
      const dist = Math.hypot(node.x - other.x, node.y - other.y);
      if (dist < 130) {
        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.quadraticCurveTo(
          (node.x + other.x) * 0.5,
          (node.y + other.y) * 0.5 + 22,
          other.x,
          other.y,
        );
        ctx.strokeStyle = `rgba(157, 234, 122, ${(1 - dist / 130) * 0.14 * Math.min(node.life, other.life)})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    const glow = ctx.createRadialGradient(
      node.x,
      node.y,
      0,
      node.x,
      node.y,
      78 * node.power,
    );
    glow.addColorStop(0, `rgba(180, 248, 154, ${0.18 * node.life})`);
    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(node.x - 78, node.y - 78, 156, 156);

    ctx.beginPath();
    ctx.arc(node.x, node.y, 3 + node.power * 1.6, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(228, 255, 211, ${0.85 * node.life})`;
    ctx.fill();
  }
}

function drawPrismScene() {
  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  for (const particle of particles) {
    const shardLength = 6 + particle.radius * 4.6;
    const dx = Math.cos(particle.angle) * shardLength;
    const dy = Math.sin(particle.angle) * shardLength;

    ctx.beginPath();
    ctx.moveTo(particle.x - dx, particle.y - dy);
    ctx.lineTo(particle.x + dx, particle.y + dy);
    ctx.strokeStyle = particle.color;
    ctx.lineWidth = 1.2 + particle.radius * 0.35;
    ctx.stroke();
  }

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    node.life *= 0.985;

    const glow = ctx.createRadialGradient(
      node.x,
      node.y,
      0,
      node.x,
      node.y,
      120 * node.power,
    );
    glow.addColorStop(0, `hsla(${node.hue}, 100%, 74%, ${0.2 * node.life})`);
    glow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = glow;
    ctx.fillRect(node.x - 120, node.y - 120, 240, 240);

    for (let inner = index + 1; inner < nodes.length; inner += 1) {
      const other = nodes[inner];
      const dist = Math.hypot(node.x - other.x, node.y - other.y);
      if (dist < 170) {
        const mx = (node.x + other.x) * 0.5;
        const my = (node.y + other.y) * 0.5;
        const lift = 18 + (1 - dist / 170) * 42;

        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.lineTo(mx, my - lift);
        ctx.lineTo(other.x, other.y);
        ctx.closePath();
        ctx.fillStyle = `hsla(${(node.hue + other.hue) * 0.5}, 96%, 68%, ${0.035 * Math.min(node.life, other.life)})`;
        ctx.fill();

        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.lineTo(other.x, other.y);
        ctx.strokeStyle = `rgba(116, 233, 255, ${(1 - dist / 170) * 0.22 * Math.min(node.life, other.life)})`;
        ctx.lineWidth = 1.1;
        ctx.stroke();
      }
    }

    const size = 5 + node.power * 2.8;
    ctx.beginPath();
    ctx.moveTo(node.x, node.y - size);
    ctx.lineTo(node.x + size * 0.92, node.y);
    ctx.lineTo(node.x, node.y + size);
    ctx.lineTo(node.x - size * 0.92, node.y);
    ctx.closePath();
    ctx.fillStyle = `hsla(${node.hue}, 100%, 72%, ${0.82 * node.life})`;
    ctx.fill();
  }

  ctx.restore();
}

function drawEmberScene() {
  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  for (const particle of particles) {
    const emberGlow = ctx.createRadialGradient(
      particle.x,
      particle.y,
      0,
      particle.x,
      particle.y,
      12 + particle.radius * 5,
    );
    emberGlow.addColorStop(0, particle.color);
    emberGlow.addColorStop(0.45, "rgba(255, 190, 100, 0.12)");
    emberGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = emberGlow;
    ctx.fillRect(particle.x - 20, particle.y - 20, 40, 40);

    ctx.beginPath();
    ctx.moveTo(particle.x, particle.y + particle.radius * 1.5);
    ctx.lineTo(
      particle.x + Math.cos(particle.angle) * (2 + particle.radius * 5),
      particle.y - (6 + particle.radius * 4),
    );
    ctx.strokeStyle = particle.color;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    node.life *= 0.984;

    const heat = ctx.createRadialGradient(
      node.x,
      node.y,
      0,
      node.x,
      node.y,
      95 * node.power,
    );
    heat.addColorStop(0, `rgba(255, 124, 64, ${0.22 * node.life})`);
    heat.addColorStop(0.55, `rgba(255, 198, 102, ${0.1 * node.life})`);
    heat.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = heat;
    ctx.fillRect(node.x - 95, node.y - 95, 190, 190);

    for (let inner = index + 1; inner < nodes.length; inner += 1) {
      const other = nodes[inner];
      const dist = Math.hypot(node.x - other.x, node.y - other.y);
      if (dist < 145) {
        const mx = (node.x + other.x) * 0.5;
        const my = (node.y + other.y) * 0.5;
        const arcLift = 12 + (1 - dist / 145) * 22;

        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.quadraticCurveTo(mx, my - arcLift, other.x, other.y);
        ctx.strokeStyle = `rgba(255, 132, 68, ${(1 - dist / 145) * 0.3 * Math.min(node.life, other.life)})`;
        ctx.lineWidth = 1.4;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(node.x, node.y);
        ctx.quadraticCurveTo(mx, my + arcLift * 0.45, other.x, other.y);
        ctx.strokeStyle = `rgba(255, 220, 114, ${(1 - dist / 145) * 0.12 * Math.min(node.life, other.life)})`;
        ctx.lineWidth = 0.9;
        ctx.stroke();
      }
    }

    const size = 4 + node.power * 2.2;
    ctx.beginPath();
    ctx.moveTo(node.x, node.y - size);
    ctx.lineTo(node.x + size * 0.65, node.y - size * 0.15);
    ctx.lineTo(node.x + size * 0.25, node.y + size);
    ctx.lineTo(node.x - size * 0.25, node.y + size);
    ctx.lineTo(node.x - size * 0.65, node.y - size * 0.15);
    ctx.closePath();
    ctx.fillStyle = `rgba(255, 205, 118, ${0.82 * node.life})`;
    ctx.fill();
  }

  ctx.restore();
}

function pruneNodes() {
  for (let index = nodes.length - 1; index >= 0; index -= 1) {
    if (nodes[index].life < 0.03) {
      nodes.splice(index, 1);
    }
  }
}

function animate() {
  ctx.clearRect(0, 0, width, height);
  drawBackgroundGlow();
  drawRipples();
  updateParticles();

  if (currentTheme === "forest") {
    drawForestScene();
  } else if (currentTheme === "prism") {
    drawPrismScene();
  } else if (currentTheme === "ember") {
    drawEmberScene();
  } else {
    drawDefaultScene();
  }

  pruneNodes();
  requestAnimationFrame(animate);
}

async function forgeSecret() {
  forgeButton.disabled = true;
  forgeButton.textContent = "Forging...";

  try {
    const response = await fetch("/api/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        events: capturedEvents,
        width,
        height,
        preset: presetSelect.value,
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Generation failed.");
    }

    outputSecret = payload.secret;
    secretBox.textContent = payload.secret;
    outputLabel.textContent = `${payload.presetLabel} forged`;
    strengthChip.textContent = `${payload.strengthLabel}`;
    bitsValue.textContent = `${payload.approxBits} bits`;
    hashPreview.textContent = payload.interactionHashPreview;
    fingerprintPreview.textContent = payload.fingerprint;
    fingerprintPreview.title = payload.fingerprint;
    copyButton.disabled = false;
    clearClipboardButton.disabled = false;
    updateReadiness(payload.featureSummary);
    createRipple(width * 0.5, height * 0.5, 1.8);
    showToast("Secret forged locally.");
  } catch (error) {
    showToast(error.message);
  } finally {
    forgeButton.textContent = "Forge secret";
    updateReadiness();
  }
}

async function copySecret() {
  if (!outputSecret) return;
  try {
    await navigator.clipboard.writeText(outputSecret);
    showToast("Copied to clipboard.");
  } catch (error) {
    showToast("Clipboard access failed.");
  }
}

async function clearClipboard() {
  try {
    await navigator.clipboard.writeText("");
    showToast("Clipboard cleared.");
  } catch (error) {
    showToast("Clipboard clear failed.");
  }
}

function handlePointerMove(event) {
  const point = event.touches ? event.touches[0] : event;
  const x = point.clientX;
  const y = point.clientY;
  const pressure =
    event.pressure || point.force || (pointerActive ? 0.65 : 0.35);

  pushNode(x, y, pointerActive ? 1.35 : 0.9);
  if (Math.random() > 0.6) {
    createRipple(x, y, pointerActive ? 1.2 : 0.7);
  }

  captureEvent(pointerActive ? "drag" : "move", x, y, pressure);
}

window.addEventListener("resize", () => {
  resizeCanvas();
  seedParticles();
});

window.addEventListener("pointermove", handlePointerMove, { passive: true });
window.addEventListener("pointerdown", (event) => {
  pointerActive = true;
  pushNode(event.clientX, event.clientY, 1.7);
  createRipple(event.clientX, event.clientY, 1.4);
  captureEvent("down", event.clientX, event.clientY, event.pressure || 0.8);
});
window.addEventListener("pointerup", (event) => {
  pointerActive = false;
  captureEvent("up", event.clientX, event.clientY, event.pressure || 0.2);
});
window.addEventListener("click", (event) => {
  pushNode(event.clientX, event.clientY, 1.25);
  createRipple(event.clientX, event.clientY, 1.3);
  captureEvent("click", event.clientX, event.clientY, 0.7);
});
window.addEventListener("touchmove", handlePointerMove, { passive: true });
window.addEventListener(
  "wheel",
  (event) => {
    const x = width * 0.5;
    const y = height * 0.5;
    pushNode(x, y, 0.9);
    captureEvent("wheel", x, y, clamp(Math.abs(event.deltaY) / 250, 0, 1));
  },
  { passive: true },
);

themeSelect.addEventListener("change", (event) => {
  applyTheme(event.target.value);
  showToast(
    `${themeSelect.options[themeSelect.selectedIndex].text} theme selected.`,
  );
});

forgeButton.addEventListener("click", forgeSecret);
resetButton.addEventListener("click", () => {
  resetSession();
  showToast("Session reset.");
});
copyButton.addEventListener("click", copySecret);
clearClipboardButton.addEventListener("click", clearClipboard);

resizeCanvas();
applyTheme(themeSelect.value || "default");
resetSession();
animate();
