const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const PADDING = 40;

let trajectory = [];   // [step_id, t, x, y, vx, vy]
let playing = false;
let simTime = 0;       // поточний "час" анімації (в секундах симуляції)
let lastFrameTs = null;
let scaleX, scaleY, maxT;

let currentLoadedId = null;
let globalMaxX = null;
let globalMaxY = null;

async function populateSimSelect() {
  const res = await fetch('/simulations');
  if (!res.ok) return;
  const list = await res.json();

  const select = document.getElementById('simSelect');
  select.innerHTML = '';

  if (list.length === 0) {
    select.innerHTML = '<option value="">Немає симуляцій</option>';
    return;
  }

  list.forEach(sim => {
    const option = document.createElement('option');
    option.value = sim.id;
    option.textContent = `#${sim.id} — апогей ${sim.apogee.toFixed(1)}м, дальність ${sim.landing_x.toFixed(1)}м`;
    select.appendChild(option);
  });

  loadSimulation();
}

async function loadSimulation() {
  const id = document.getElementById('simSelect').value;
  if (!id) return;

  const fixedScale = document.getElementById('fixedScale').checked;
  if (fixedScale) {
    await fetchGlobalMax();
  }

  canvas.classList.add('fading');

  document.getElementById('info').textContent = 'Завантаження...';
  const res = await fetch(`/simulations/${id}`);
  if (!res.ok) {
    document.getElementById('info').textContent = 'Симуляцію не знайдено';
    canvas.classList.remove('fading');
    return;
  }
  const data = await res.json();
  trajectory = data.trajectory;
  maxT = trajectory[trajectory.length - 1][1];
  currentLoadedId = id;

  document.getElementById('info').textContent =
    `Апогей: ${data.apogee} м · Час польоту: ${data.flight_time.toFixed(2)} с · Дальність: ${data.landing_x.toFixed(2)} м`;

  computeScale();
  resetToStart();

  document.getElementById('restartBtn').disabled = false;
  document.getElementById('playBtn').disabled = false;

  setTimeout(() => canvas.classList.remove('fading'), 50);
}

async function fetchGlobalMax() {
  const res = await fetch('/simulations');
  if (!res.ok) return;
  const list = await res.json();
  if (list.length === 0) return;

  const maxApogee = Math.max(...list.map(s => s.apogee));
  const maxRange = Math.max(...list.map(s => s.landing_x));

  globalMaxY = niceCeil(maxApogee * 1.15);
  globalMaxX = niceCeil(maxRange);
}

function resetToStart() {
  simTime = 0;
  playing = false;
  lastFrameTs = null;
  document.getElementById('playBtn').textContent = '▶ Play';
  drawFrame();
}

function restart() {
  resetToStart();
}

function updateSpeedLabel() {
  const speed = parseFloat(document.getElementById('speed').value);
  document.getElementById('speedValue').textContent = `x${speed.toFixed(1)}`;
}

function updateTelemetry(point) {
  const [, t, x, y, vx, vy] = point;
  const speed = Math.sqrt(vx ** 2 + vy ** 2);

  const timeInput = document.getElementById('telTimeInput');
  if (document.activeElement !== timeInput) {
    timeInput.value = t.toFixed(2);
  }
  document.getElementById('telY').textContent = `${y.toFixed(2)} м`;
  document.getElementById('telX').textContent = `${x.toFixed(2)} м`;
  document.getElementById('telSpeed').textContent = `${speed.toFixed(2)} м/с`;
  document.getElementById('telVx').textContent = `${vx.toFixed(2)} м/с`;
  document.getElementById('telVy').textContent = `${vy.toFixed(2)} м/с`;
}

function computeScale() {
  const fixedScale = document.getElementById('fixedScale').checked;

  let maxX, maxY;
  if (fixedScale && globalMaxX && globalMaxY) {
    maxX = globalMaxX;
    maxY = globalMaxY;
  } else {
    maxX = Math.max(...trajectory.map(p => p[2]));
    maxY = Math.max(...trajectory.map(p => p[3])) * 1.15;
  }

  scaleX = (canvas.width - 2 * PADDING) / (maxX || 1);
  scaleY = (canvas.height - 2 * PADDING) / (maxY || 1);
}

function toScreen(x, y) {
  return {
    sx: PADDING + x * scaleX,
    sy: canvas.height - PADDING - y * scaleY
  };
}

function screenToWorld(sx, sy) {
  return {
    x: (sx - PADDING) / scaleX,
    y: (canvas.height - PADDING - sy) / scaleY
  };
}

function niceStep(maxValue) {
  const roughStep = maxValue / 5;
  const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep || 1)));
  const normalized = roughStep / magnitude;

  let niceNormalized;
  if (normalized < 1.5) niceNormalized = 1;
  else if (normalized < 3.5) niceNormalized = 2;
  else if (normalized < 7.5) niceNormalized = 5;
  else niceNormalized = 10;

  return niceNormalized * magnitude;
}

function niceCeil(value) {
  const step = niceStep(value);
  return Math.ceil(value / step) * step;
}

function interpolateAt(t) {
  if (t <= trajectory[0][1]) return trajectory[0];
  if (t >= maxT) return trajectory[trajectory.length - 1];

  for (let i = 0; i < trajectory.length - 1; i++) {
    const a = trajectory[i], b = trajectory[i + 1];
    if (t >= a[1] && t <= b[1]) {
      const k = (t - a[1]) / (b[1] - a[1] || 1);
      return [
        a[0], t,
        a[2] + k * (b[2] - a[2]),
        a[3] + k * (b[3] - a[3]),
        a[4] + k * (b[4] - a[4]),
        a[5] + k * (b[5] - a[5]),
      ];
    }
  }
  return trajectory[trajectory.length - 1];
}

function drawFrame() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const ground = toScreen(0, 0);
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, ground.sy);
  ctx.lineTo(canvas.width, ground.sy);
  ctx.stroke();

  const fixedScale = document.getElementById('fixedScale').checked;
  const maxY = (fixedScale && globalMaxY) ? globalMaxY / 1.15 : Math.max(...trajectory.map(p => p[3]));
  const maxX = (fixedScale && globalMaxX) ? globalMaxX : Math.max(...trajectory.map(p => p[2]));

  ctx.strokeStyle = 'rgba(148, 163, 184, 0.1)';
  ctx.fillStyle = '#64748b';
  ctx.font = '11px sans-serif';
  ctx.lineWidth = 1;

  const yStep = niceStep(maxY);
  const yLimit = fixedScale && globalMaxY ? globalMaxY : maxY * 1.15;
  for (let yVal = 0; yVal <= yLimit; yVal += yStep) {
    const { sy } = toScreen(0, yVal);
    ctx.beginPath();
    ctx.moveTo(PADDING, sy);
    ctx.lineTo(canvas.width - 10, sy);
    ctx.stroke();
    ctx.textAlign = 'right';
    ctx.fillText(`${yVal.toFixed(0)}м`, PADDING - 6, sy + 4);
  }

  const xStep = niceStep(maxX);
  const xLimit = fixedScale && globalMaxX ? globalMaxX : maxX;
  for (let xVal = 0; xVal <= xLimit; xVal += xStep) {
    const { sx } = toScreen(xVal, 0);
    ctx.beginPath();
    ctx.moveTo(sx, 10);
    ctx.lineTo(sx, canvas.height - PADDING);
    ctx.stroke();
    ctx.textAlign = 'center';
    ctx.fillText(`${xVal.toFixed(0)}м`, sx, canvas.height - PADDING + 16);
  }

  ctx.strokeStyle = 'rgba(96, 165, 250, 0.5)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  trajectory.forEach((p, i) => {
    if (p[1] > simTime) return;
    const { sx, sy } = toScreen(p[2], p[3]);
    if (i === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
  });
  ctx.stroke();

  ctx.strokeStyle = 'rgba(148, 163, 184, 0.15)';
  ctx.beginPath();
  trajectory.forEach((p, i) => {
    const { sx, sy } = toScreen(p[2], p[3]);
    if (i === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
  });
  ctx.stroke();

  const [, , x, y, vx, vy] = interpolateAt(simTime);
  const { sx, sy } = toScreen(x, Math.max(y, 0));
  const angle = Math.atan2(-vy, vx);

  ctx.save();
  ctx.translate(sx, sy);
  ctx.rotate(-angle);
  ctx.font = '24px serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('🚀', 0, 0);
  ctx.restore();

  updateTelemetry(interpolateAt(simTime));
}

function togglePlay() {
  playing = !playing;
  document.getElementById('playBtn').textContent = playing ? '⏸ Pause' : '▶ Play';
  if (playing) {
    lastFrameTs = null;
    requestAnimationFrame(animate);
  }
}

function animate(ts) {
  if (!playing) return;
  if (lastFrameTs === null) lastFrameTs = ts;
  const dt = (ts - lastFrameTs) / 1000;
  lastFrameTs = ts;

  const speed = parseFloat(document.getElementById('speed').value);
  simTime += dt * speed;

  if (simTime >= maxT) {
    simTime = maxT;
    playing = false;
    document.getElementById('playBtn').textContent = '▶ Play';
  }

  drawFrame();
  if (playing) requestAnimationFrame(animate);
}

let dragging = false;

function getRocketScreenPos() {
  const [, , x, y] = interpolateAt(simTime);
  return toScreen(x, Math.max(y, 0));
}

function distanceToRocket(mouseX, mouseY) {
  const { sx, sy } = getRocketScreenPos();
  return Math.hypot(mouseX - sx, mouseY - sy);
}

function findNearestTimeByX(worldX) {
  let closest = trajectory[0];
  let minDist = Infinity;
  for (const p of trajectory) {
    const dist = Math.abs(p[2] - worldX);
    if (dist < minDist) {
      minDist = dist;
      closest = p;
    }
  }
  return closest[1];
}

canvas.addEventListener('mousedown', (e) => {
  if (trajectory.length === 0) return;
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  if (distanceToRocket(mouseX, mouseY) < 20) {
    dragging = true;
    playing = false;
    document.getElementById('playBtn').textContent = '▶ Play';
    canvas.classList.add('dragging');
  }
});

canvas.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  const rect = canvas.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const world = screenToWorld(mouseX, 0);
  simTime = findNearestTimeByX(world.x);
  drawFrame();
});

window.addEventListener('mouseup', () => {
  dragging = false;
  canvas.classList.remove('dragging');
});

document.getElementById('telTimeInput').addEventListener('change', (e) => {
  if (trajectory.length === 0) return;
  let t = parseFloat(e.target.value);
  if (isNaN(t)) t = 0;
  t = Math.max(0, Math.min(t, maxT));

  playing = false;
  document.getElementById('playBtn').textContent = '▶ Play';
  simTime = t;
  drawFrame();
});

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  const messagesEl = document.getElementById('chatMessages');

  const placeholder = messagesEl.querySelector('.chat-placeholder');
  if (placeholder) placeholder.remove();

  appendChatMessage(question, 'user');
  input.value = '';

  const loadingEl = document.createElement('div');
  loadingEl.className = 'chat-message loading';
  loadingEl.textContent = 'Думаю...';
  messagesEl.appendChild(loadingEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  document.getElementById('chatSendBtn').disabled = true;

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });

    loadingEl.remove();

    if (!res.ok) {
      appendChatMessage('Помилка запиту до сервера.', 'assistant');
      return;
    }

    const data = await res.json();
    appendChatMessage(data.answer, 'assistant', data.confidence, data.relevant_simulation_ids);
  } catch (err) {
    loadingEl.remove();
    appendChatMessage('Не вдалося зв\'язатись із сервером.', 'assistant');
  } finally {
    document.getElementById('chatSendBtn').disabled = false;
  }
}

function appendChatMessage(text, role, confidence = null, simIds = null) {
  const messagesEl = document.getElementById('chatMessages');
  const msgEl = document.createElement('div');
  msgEl.className = `chat-message ${role}`;
  msgEl.textContent = text;

  if (role === 'assistant' && confidence) {
    const badge = document.createElement('span');
    badge.className = `confidence ${confidence}`;
    badge.textContent = confidence;
    msgEl.appendChild(document.createElement('br'));
    msgEl.appendChild(badge);
  }

  if (role === 'assistant' && simIds && simIds.length > 0) {
    const linksRow = document.createElement('div');
    linksRow.className = 'sim-links';
    simIds.forEach(id => {
      const btn = document.createElement('button');
      btn.className = 'sim-link';
      btn.textContent = `#${id}`;
      btn.onclick = () => {
        document.getElementById('simSelect').value = id;
        loadSimulation();
      };
      linksRow.appendChild(btn);
    });
    msgEl.appendChild(linksRow);
  }

  messagesEl.appendChild(msgEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function handleChatKeydown(event) {
  if (event.key === 'Enter') {
    sendChatMessage();
  }
}

populateSimSelect();
updateSpeedLabel();