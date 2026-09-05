const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const PADDING = 40;

let trajectory = [];   // [step_id, t, x, y, vx, vy]
let playing = false;
let simTime = 0;       // поточний "час" анімації (в секундах симуляції)
let lastFrameTs = null;
let scaleX, scaleY, maxT;

let currentLoadedId = null;
let currentSimData = null;
let editingSimulationId = null;
let globalMaxX = null;
let globalMaxY = null;

let agentSessionId = crypto.randomUUID ? crypto.randomUUID() : `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;

async function populateSimSelect(preferredId = null) {
  const res = await fetch('/simulations');
  if (!res.ok) return;
  const list = await res.json();

  const select = document.getElementById('simSelect');
  select.innerHTML = '';

  if (list.length === 0) {
    select.innerHTML = '<option value="">Немає симуляцій</option>';
    document.getElementById('restartBtn').disabled = true;
    document.getElementById('playBtn').disabled = true;
    document.getElementById('deleteBtn').disabled = true;
    document.getElementById('editBtn').disabled = true;
    currentSimData = null;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  list.forEach(sim => {
    const option = document.createElement('option');
    option.value = sim.id;
    option.textContent = `#${sim.id} — апогей ${sim.apogee.toFixed(1)}м, дальність ${sim.landing_x.toFixed(1)}м`;
    select.appendChild(option);
  });

  if (preferredId !== null && list.some(s => s.id === preferredId)) {
    select.value = preferredId;
  }

  await loadSimulation();
}

async function loadSimulation() {
  const id = document.getElementById('simSelect').value;
  if (!id) return;

  dispersionMode = false;
  document.getElementById('deleteBtn').disabled = false;

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
  currentSimData = data;

  document.getElementById('info').textContent =
    `Апогей: ${data.apogee} м · Час польоту: ${data.flight_time.toFixed(2)} с · Дальність: ${data.landing_x.toFixed(2)} м`;

  computeScale();
  resetToStart();

  document.getElementById('restartBtn').disabled = false;
  document.getElementById('playBtn').disabled = false;
  document.getElementById('deleteBtn').disabled = false;
  document.getElementById('editBtn').disabled = false;

  setTimeout(() => canvas.classList.remove('fading'), 50);
}

async function deleteSimulation() {
  const id = document.getElementById('simSelect').value;
  if (!id) return;

  const confirmed = confirm(`Видалити симуляцію #${id}? Цю дію не можна скасувати.`);
  if (!confirmed) return;

  const res = await fetch(`/simulations/${id}`, { method: 'DELETE' });

  if (!res.ok) {
    document.getElementById('info').textContent = 'Не вдалося видалити симуляцію';
    return;
  }

  document.getElementById('restartBtn').disabled = true;
  document.getElementById('playBtn').disabled = true;
  document.getElementById('deleteBtn').disabled = true;
  document.getElementById('editBtn').disabled = true;
  currentSimData = null;
  trajectory = [];

  await populateSimSelect();
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
  if (compareMode) {
    drawCompareFrame();
  } else {
    drawFrame();
  }
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

  const limit = compareMode ? compareMaxT : maxT;
  if (simTime >= limit) {
    simTime = limit;
    playing = false;
    document.getElementById('playBtn').textContent = '▶ Play';
  }

  if (compareMode) {
    drawCompareFrame();
  } else {
    drawFrame();
  }
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
  if (compareMode || trajectory.length === 0) return;
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

let chatMode = 'ask';

function setChatMode(mode) {
  chatMode = mode;
  document.getElementById('modeAskBtn').classList.toggle('active', mode === 'ask');
  document.getElementById('modeAgentBtn').classList.toggle('active', mode === 'agent');

  const input = document.getElementById('chatInput');
  input.placeholder = mode === 'ask'
    ? 'Запитай про існуючі симуляції...'
    : 'Наприклад: запусти симуляцію масою 2кг, кут 45, швидкість 50 м/с';
}

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  const messagesEl = document.getElementById('chatMessages');
  const placeholder = messagesEl.querySelector('.chat-placeholder');
  if (placeholder) placeholder.remove();

  appendChatMessage(question, 'user');
  input.value = '';
  document.getElementById('chatSendBtn').disabled = true;

  try {
    if (chatMode === 'agent') {
      await streamAgentReply(question);
    } else {
      await askQuestion(question);
    }
  } finally {
    document.getElementById('chatSendBtn').disabled = false;
  }
}

async function askQuestion(question) {
  const messagesEl = document.getElementById('chatMessages');
  const loadingEl = document.createElement('div');
  loadingEl.className = 'chat-message loading';
  loadingEl.textContent = 'Думаю...';
  messagesEl.appendChild(loadingEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;

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
  }
}

function toolCallLabel(name, input) {
  switch (name) {
    case 'run_new_simulation':
      return `Запускаю нову симуляцію (маса ${input.mass}кг, кут ${input.angle_deg}°, v0 ${input.v0}м/с)`;
    case 'show_existing_simulation':
      return `Відкриваю симуляцію #${input.simulation_id}`;
    case 'compare_simulations':
      return `Порівнюю симуляції: ${(input.simulation_ids || []).map(id => '#' + id).join(', ')}`;
    case 'list_all_simulations':
      return 'Переглядаю список усіх симуляцій';
    case 'search_past_simulations':
      return `Шукаю по запиту: "${input.query}"`;
    default:
      return `Викликаю ${name}`;
  }
}

async function streamAgentReply(question) {
  const messagesEl = document.getElementById('chatMessages');
  let currentBubble = null;
  let gotAnyContent = false;
  let doneData = null;

  function appendTrace(label) {
    currentBubble = null;
    const traceEl = document.createElement('div');
    traceEl.className = 'chat-trace';
    traceEl.textContent = `🔧 ${label}`;
    messagesEl.appendChild(traceEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function appendTextDelta(text) {
    if (!currentBubble) {
      currentBubble = document.createElement('div');
      currentBubble.className = 'chat-message assistant';
      messagesEl.appendChild(currentBubble);
    }
    currentBubble.textContent += text;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  try {
    const res = await fetch('/agent/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: question, session_id: agentSessionId }),
    });

    if (!res.ok || !res.body) {
      appendChatMessage('Помилка запиту до сервера.', 'assistant');
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let newlineIdx;
      while ((newlineIdx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, newlineIdx).trim();
        buffer = buffer.slice(newlineIdx + 1);
        if (!line) continue;

        const evt = JSON.parse(line);
        if (evt.type === 'text_delta') {
          gotAnyContent = true;
          appendTextDelta(evt.text);
        } else if (evt.type === 'tool_call') {
          gotAnyContent = true;
          appendTrace(toolCallLabel(evt.name, evt.input));
        } else if (evt.type === 'done') {
          doneData = evt;
        }
      }
    }

    if (!gotAnyContent) {
      appendChatMessage('Агент не відповів.', 'assistant');
    }

    if (doneData) {
      if (doneData.compare_simulation_ids && doneData.compare_simulation_ids.length >= 2) {
        selectedCompareIds = new Set(doneData.compare_simulation_ids);
        await applyCompare();
        if (!playing) togglePlay();
      } else {
        await populateSimSelect(doneData.simulation_id);
        if (doneData.simulation_id && !playing) {
          togglePlay();
        }
      }
    }
  } catch (err) {
    appendChatMessage('Не вдалося зв\'язатись із сервером.', 'assistant');
  }
}

function resetAgentChat() {
  agentSessionId = crypto.randomUUID ? crypto.randomUUID() : `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const messagesEl = document.getElementById('chatMessages');
  messagesEl.innerHTML = '<div class="chat-placeholder" id="chatPlaceholder">Запитай про дані або попроси запустити нову симуляцію</div>';
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

const COMPARE_COLORS = ['#3b82f6', '#f472b6', '#facc15', '#34d399', '#f97316', '#a78bfa'];

let compareMode = false;
let compareSims = []; // [{id, trajectory, maxT, apogee, flight_time, landing_x, color}]
let compareMaxT = 0;
let selectedCompareIds = new Set();

function resetCreateFormDefaults() {
  document.getElementById('createMass').value = 0.5;
  document.getElementById('createV0').value = 40;
  document.getElementById('createAngle').value = 45;
  document.getElementById('createDrag').value = 0.47;
  document.getElementById('createArea').value = 0.03;
  document.getElementById('createMethod').value = 'euler';

  document.getElementById('toggleEngine').checked = false;
  toggleEngineFields();
  document.getElementById('toggleParachute').checked = false;
  toggleParachuteFields();
  document.getElementById('toggleDispersion').checked = false;
  toggleDispersionFields();
}

function toggleCreateMode() {
  const panel = document.getElementById('createPanel');
  const isOpen = panel.classList.contains('open');

  document.getElementById('comparePanel').classList.remove('open');

  if (isOpen) {
    panel.classList.remove('open');
    return;
  }

  editingSimulationId = null;
  resetCreateFormDefaults();
  document.getElementById('createHeaderTitle').textContent = 'Параметри нової симуляції:';
  document.getElementById('createSubmitBtn').textContent = '▶ Запустити';
  document.getElementById('dispersionToggleLabel').classList.remove('hidden');
  document.getElementById('createError').textContent = '';
  document.getElementById('createNote').textContent = '';
  panel.classList.add('open');
}

function exitCreateMode() {
  document.getElementById('createPanel').classList.remove('open');
  editingSimulationId = null;
}

function openEditMode() {
  if (!currentSimData) return;

  editingSimulationId = currentSimData.id;

  document.getElementById('comparePanel').classList.remove('open');
  document.getElementById('createError').textContent = '';
  document.getElementById('createNote').textContent = '';

  document.getElementById('createMass').value = currentSimData.mass;
  document.getElementById('createV0').value = currentSimData.v0;
  document.getElementById('createAngle').value = currentSimData.angle_deg;
  document.getElementById('createDrag').value = currentSimData.drag_coefficient;
  document.getElementById('createArea').value = currentSimData.cross_section_area;
  document.getElementById('createMethod').value = currentSimData.integration_method || 'euler';

  const hasEngine = currentSimData.thrust != null;
  document.getElementById('toggleEngine').checked = hasEngine;
  toggleEngineFields();
  if (hasEngine) {
    document.getElementById('createThrust').value = currentSimData.thrust;
    document.getElementById('createBurnTime').value = currentSimData.burn_time;
    document.getElementById('createPropellant').value = currentSimData.propellant_mass;
  }

  const hasParachute = currentSimData.parachute_cd != null;
  document.getElementById('toggleParachute').checked = hasParachute;
  toggleParachuteFields();
  if (hasParachute) {
    document.getElementById('createParaCd').value = currentSimData.parachute_cd;
    document.getElementById('createParaArea').value = currentSimData.parachute_area;
  }

  document.getElementById('toggleDispersion').checked = false;
  toggleDispersionFields();
  document.getElementById('dispersionToggleLabel').classList.add('hidden');

  document.getElementById('createHeaderTitle').textContent = `Редагування симуляції #${editingSimulationId}:`;
  document.getElementById('createSubmitBtn').textContent = '💾 Зберегти зміни';

  document.getElementById('createPanel').classList.add('open');
}

function toggleEngineFields() {
  const on = document.getElementById('toggleEngine').checked;
  document.getElementById('engineFields').classList.toggle('hidden', !on);
}

function toggleParachuteFields() {
  const on = document.getElementById('toggleParachute').checked;
  document.getElementById('parachuteFields').classList.toggle('hidden', !on);
}

function toggleDispersionFields() {
  const on = document.getElementById('toggleDispersion').checked;
  document.getElementById('dispersionFields').classList.toggle('hidden', !on);
  document.getElementById('createSubmitBtn').textContent = on ? '📊 Показати розкид' : '▶ Запустити';
}

function readBaseCreateFields() {
  return {
    mass: parseFloat(document.getElementById('createMass').value),
    v0: parseFloat(document.getElementById('createV0').value),
    angle_deg: parseFloat(document.getElementById('createAngle').value),
    drag_coefficient: parseFloat(document.getElementById('createDrag').value),
    cross_section_area: parseFloat(document.getElementById('createArea').value),
  };
}

function extractErrorMessage(err, fallback) {
  if (err && Array.isArray(err.detail)) return err.detail.map(d => d.msg).join('; ');
  if (err && err.detail) return String(err.detail);
  return fallback;
}

async function findOptimalAngle() {
  const errorEl = document.getElementById('createError');
  const noteEl = document.getElementById('createNote');
  errorEl.textContent = '';
  noteEl.textContent = '';

  const payload = {
    mass: parseFloat(document.getElementById('createMass').value),
    v0: parseFloat(document.getElementById('createV0').value),
    drag_coefficient: parseFloat(document.getElementById('createDrag').value),
    cross_section_area: parseFloat(document.getElementById('createArea').value),
  };
  if (Object.values(payload).some(v => Number.isNaN(v))) {
    errorEl.textContent = 'Заповни масу, швидкість, опір і площу коректними числами.';
    return;
  }

  const btn = document.getElementById('createOptimalBtn');
  btn.disabled = true;

  try {
    const res = await fetch('/simulate/optimal-angle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => null);
      errorEl.textContent = extractErrorMessage(err, 'Не вдалося знайти оптимальний кут.');
      return;
    }

    const data = await res.json();
    document.getElementById('createAngle').value = data.angle_deg;
    noteEl.textContent = `Оптимальний кут: ${data.angle_deg}° → дальність ${data.landing_x.toFixed(1)} м`;
  } catch (err) {
    errorEl.textContent = 'Не вдалося зв\'язатись із сервером.';
  } finally {
    btn.disabled = false;
  }
}

async function submitCreateSimulation() {
  const errorEl = document.getElementById('createError');
  const noteEl = document.getElementById('createNote');
  errorEl.textContent = '';
  noteEl.textContent = '';

  const base = readBaseCreateFields();
  if (Object.values(base).some(v => Number.isNaN(v))) {
    errorEl.textContent = 'Заповни всі основні поля коректними числами.';
    return;
  }

  const engineOn = document.getElementById('toggleEngine').checked;
  const parachuteOn = document.getElementById('toggleParachute').checked;
  const dispersionOn = document.getElementById('toggleDispersion').checked;

  const payload = { ...base };
  if (!dispersionOn) {
    payload.integration_method = document.getElementById('createMethod').value;
  }

  if (engineOn) {
    payload.thrust = parseFloat(document.getElementById('createThrust').value);
    payload.burn_time = parseFloat(document.getElementById('createBurnTime').value);
    payload.propellant_mass = parseFloat(document.getElementById('createPropellant').value);
    if ([payload.thrust, payload.burn_time, payload.propellant_mass].some(Number.isNaN)) {
      errorEl.textContent = 'Заповни всі поля двигуна коректними числами.';
      return;
    }
  }

  if (parachuteOn) {
    payload.parachute_cd = parseFloat(document.getElementById('createParaCd').value);
    payload.parachute_area = parseFloat(document.getElementById('createParaArea').value);
    if ([payload.parachute_cd, payload.parachute_area].some(Number.isNaN)) {
      errorEl.textContent = 'Заповни всі поля парашута коректними числами.';
      return;
    }
  }

  const submitBtn = document.getElementById('createSubmitBtn');
  submitBtn.disabled = true;

  try {
    if (dispersionOn) {
      payload.trials = parseInt(document.getElementById('createTrials').value, 10);
      payload.angle_std_deg = parseFloat(document.getElementById('createAngleStd').value);
      payload.v0_std_pct = parseFloat(document.getElementById('createV0Std').value);

      const res = await fetch('/simulate/dispersion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        errorEl.textContent = extractErrorMessage(err, 'Не вдалося розрахувати розкид.');
        return;
      }

      const data = await res.json();
      exitCreateMode();
      showDispersionResult(data);
    } else if (editingSimulationId !== null) {
      const res = await fetch(`/simulations/${editingSimulationId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        errorEl.textContent = extractErrorMessage(err, 'Не вдалося зберегти зміни.');
        return;
      }

      const data = await res.json();
      exitCreateMode();
      await populateSimSelect(data.id);
    } else {
      const res = await fetch('/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        errorEl.textContent = extractErrorMessage(err, 'Не вдалося створити симуляцію.');
        return;
      }

      const data = await res.json();
      exitCreateMode();
      await populateSimSelect(data.id);
      if (!playing) {
        togglePlay();
      }
    }
  } catch (err) {
    errorEl.textContent = 'Не вдалося зв\'язатись із сервером.';
  } finally {
    submitBtn.disabled = false;
  }
}

let dispersionMode = false;
let dispersionData = null; // { nominalTrajectory, points, mean, std }

function showDispersionResult(data) {
  dispersionMode = true;
  dispersionData = {
    nominalTrajectory: data.nominal.trajectory,
    points: data.points,
    mean: data.landing_x_mean,
    std: data.landing_x_std,
  };

  document.getElementById('restartBtn').disabled = true;
  document.getElementById('playBtn').disabled = true;
  document.getElementById('deleteBtn').disabled = true;
  playing = false;
  document.getElementById('playBtn').textContent = '▶ Play';

  document.getElementById('compareLegend').classList.add('hidden');
  drawDispersionFrame();
}

function drawDispersionFrame() {
  const data = dispersionData;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const maxX = Math.max(
    data.nominalTrajectory[data.nominalTrajectory.length - 1][2],
    ...data.points.map(p => p.landing_x)
  ) * 1.05;
  const maxY = Math.max(...data.nominalTrajectory.map(p => p[3])) * 1.15;
  scaleX = (canvas.width - 2 * PADDING) / (maxX || 1);
  scaleY = (canvas.height - 2 * PADDING) / (maxY || 1);

  const ground = toScreen(0, 0);
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, ground.sy);
  ctx.lineTo(canvas.width, ground.sy);
  ctx.stroke();

  ctx.strokeStyle = 'rgba(96, 165, 250, 0.5)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.nominalTrajectory.forEach((p, i) => {
    const { sx, sy } = toScreen(p[2], p[3]);
    if (i === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
  });
  ctx.stroke();

  data.points.forEach((p, i) => {
    const { sx, sy } = toScreen(p.landing_x, 0);
    const jitter = ((i * 37) % 24) - 12;
    ctx.beginPath();
    ctx.arc(sx, sy - 6 - Math.abs(jitter) * 0.5, 3, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(248, 113, 113, 0.55)';
    ctx.fill();
  });

  const meanScreen = toScreen(data.mean, 0);
  ctx.strokeStyle = '#facc15';
  ctx.lineWidth = 2;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(meanScreen.sx, ground.sy);
  ctx.lineTo(meanScreen.sx, ground.sy - 26);
  ctx.stroke();
  ctx.setLineDash([]);

  document.getElementById('info').textContent =
    `Розкид приземлення: μ = ${data.mean.toFixed(2)} м, σ = ${data.std.toFixed(2)} м (${data.points.length} прогонів, номінал ${data.nominalTrajectory[data.nominalTrajectory.length - 1][2].toFixed(2)} м)`;
}

async function toggleCompareMode() {
  const panel = document.getElementById('comparePanel');
  const isOpen = panel.classList.contains('open');

  document.getElementById('createPanel').classList.remove('open');

  if (!isOpen) {
    const res = await fetch('/simulations');
    const list = await res.json();
    const checkboxesEl = document.getElementById('compareCheckboxes');
    checkboxesEl.innerHTML = '';

    list.forEach(sim => {
      const label = document.createElement('label');
      label.className = 'compare-checkbox-item';
      const isChecked = selectedCompareIds.has(sim.id);
      label.innerHTML = `
        <input type="checkbox" value="${sim.id}" ${isChecked ? 'checked' : ''} onchange="onCompareCheck(this)">
        #${sim.id}
        <div class="compare-tooltip">
          Апогей: ${sim.apogee.toFixed(1)}м<br>
          Дальність: ${sim.landing_x.toFixed(1)}м<br>
          Час: ${sim.flight_time.toFixed(2)}с
        </div>
      `;
      checkboxesEl.appendChild(label);
    });

    updateCompareCount();
    panel.classList.add('open');
  } else {
    panel.classList.remove('open');
  }
}

function onCompareCheck(checkbox) {
  const id = parseInt(checkbox.value);
  if (checkbox.checked) {
    selectedCompareIds.add(id);
  } else {
    selectedCompareIds.delete(id);
  }
  updateCompareCount();
}

function updateCompareCount() {
  const checkboxes = document.querySelectorAll('#compareCheckboxes input');
  document.getElementById('compareCount').textContent = `${selectedCompareIds.size} обрано (макс. 6)`;

  checkboxes.forEach(cb => {
    if (!cb.checked && selectedCompareIds.size >= 6) {
      cb.disabled = true;
    } else {
      cb.disabled = false;
    }
  });
}

function exitCompareMode() {
  compareMode = false;
  compareSims = [];
  document.getElementById('comparePanel').classList.remove('open');
  document.getElementById('compareLegend').classList.add('hidden');

  document.getElementById('simSelect').disabled = false;
  document.getElementById('fixedScale').disabled = false;

  document.getElementById('telemetrySingle').classList.remove('hidden');
  document.getElementById('telemetryCompare').classList.add('hidden');

  playing = false;
  document.getElementById('playBtn').textContent = '▶ Play';
  loadSimulation();
}

async function applyCompare() {
  dispersionMode = false;
  const checked = Array.from(selectedCompareIds);

  if (checked.length < 2) {
    alert('Обери щонайменше 2 симуляції для порівняння.');
    return;
  }
  if (checked.length > 6) {
    alert('Максимум 6 симуляцій одночасно.');
    return;
  }

  compareSims = [];
  for (let i = 0; i < checked.length; i++) {
    const res = await fetch(`/simulations/${checked[i]}`);
    const data = await res.json();
    compareSims.push({
      id: data.id,
      trajectory: data.trajectory,
      maxT: data.trajectory[data.trajectory.length - 1][1],
      apogee: data.apogee,
      flight_time: data.flight_time,
      landing_x: data.landing_x,
      color: COMPARE_COLORS[i % COMPARE_COLORS.length],
    });
  }

  compareMaxT = Math.max(...compareSims.map(s => s.maxT));
  compareMode = true;
  simTime = 0;
  playing = false;
  document.getElementById('playBtn').textContent = '▶ Play';

  document.getElementById('simSelect').disabled = true;
  document.getElementById('fixedScale').checked = true;
  document.getElementById('fixedScale').disabled = true;
  document.getElementById('comparePanel').classList.remove('open');
  document.getElementById('restartBtn').disabled = false;
  document.getElementById('playBtn').disabled = false;

  document.getElementById('telemetrySingle').classList.add('hidden');
  document.getElementById('telemetryCompare').classList.remove('hidden');

  renderCompareLegend();
  computeCompareScale();
  drawCompareFrame();
}

function computeCompareScale() {
  const maxX = Math.max(...compareSims.map(s => Math.max(...s.trajectory.map(p => p[2]))));
  const maxY = Math.max(...compareSims.map(s => Math.max(...s.trajectory.map(p => p[3])))) * 1.15;
  scaleX = (canvas.width - 2 * PADDING) / (maxX || 1);
  scaleY = (canvas.height - 2 * PADDING) / (maxY || 1);
}

function renderCompareLegend() {
  const legendEl = document.getElementById('compareLegend');
  legendEl.innerHTML = compareSims.map(s => `
    <div class="compare-legend-row">
      <div class="compare-legend-swatch" style="background:${s.color}"></div>
      <span>#${s.id}: ${s.apogee.toFixed(1)}м, ${s.flight_time.toFixed(2)}с, ${s.landing_x.toFixed(1)}м</span>
    </div>
  `).join('');
  legendEl.classList.remove('hidden');
}

function drawCompareFrame() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const ground = toScreen(0, 0);
  ctx.strokeStyle = '#475569';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, ground.sy);
  ctx.lineTo(canvas.width, ground.sy);
  ctx.stroke();

  const maxY = Math.max(...compareSims.map(s => Math.max(...s.trajectory.map(p => p[3]))));
  const maxX = Math.max(...compareSims.map(s => Math.max(...s.trajectory.map(p => p[2]))));

  ctx.strokeStyle = 'rgba(148, 163, 184, 0.1)';
  ctx.fillStyle = '#64748b';
  ctx.font = '11px sans-serif';
  ctx.lineWidth = 1;

  const yStep = niceStep(maxY);
  for (let yVal = 0; yVal <= maxY * 1.15; yVal += yStep) {
    const { sy } = toScreen(0, yVal);
    ctx.beginPath();
    ctx.moveTo(PADDING, sy);
    ctx.lineTo(canvas.width - 10, sy);
    ctx.stroke();
    ctx.textAlign = 'right';
    ctx.fillText(`${yVal.toFixed(0)}м`, PADDING - 6, sy + 4);
  }

  const xStep = niceStep(maxX);
  for (let xVal = 0; xVal <= maxX; xVal += xStep) {
    const { sx } = toScreen(xVal, 0);
    ctx.beginPath();
    ctx.moveTo(sx, 10);
    ctx.lineTo(sx, canvas.height - PADDING);
    ctx.stroke();
    ctx.textAlign = 'center';
    ctx.fillText(`${xVal.toFixed(0)}м`, sx, canvas.height - PADDING + 16);
  }

  compareSims.forEach(sim => {
    ctx.strokeStyle = sim.color + '40';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    sim.trajectory.forEach((p, i) => {
      const { sx, sy } = toScreen(p[2], p[3]);
      if (i === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
    });
    ctx.stroke();

    const localTime = Math.min(simTime, sim.maxT);
    ctx.strokeStyle = sim.color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    sim.trajectory.forEach((p, i) => {
      if (p[1] > localTime) return;
      const { sx, sy } = toScreen(p[2], p[3]);
      if (i === 0) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy);
    });
    ctx.stroke();

    const point = interpolateAtGeneric(sim.trajectory, sim.maxT, localTime);
    const [, , x, y, vx, vy] = point;
    const { sx, sy } = toScreen(x, Math.max(y, 0));
    const angle = Math.atan2(-vy, vx);

    ctx.save();
    ctx.translate(sx, sy);
    ctx.rotate(-angle);
    ctx.font = '20px serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🚀', 0, 0);
    ctx.restore();
  });

  updateCompareTelemetry();
}

function interpolateAtGeneric(trajectory, maxT, t) {
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

function updateCompareTelemetry() {
  const html = compareSims.map(sim => {
    const localTime = Math.min(simTime, sim.maxT);
    const point = interpolateAtGeneric(sim.trajectory, sim.maxT, localTime);
    const [, t, x, y, vx, vy] = point;
    const speed = Math.sqrt(vx ** 2 + vy ** 2);
    return `
      <div class="compare-tel-row">
        <div class="compare-tel-swatch" style="background:${sim.color}"></div>
        <span class="compare-tel-id">#${sim.id}</span>
        <span class="compare-tel-values">t=${t.toFixed(2)}с y=${y.toFixed(1)}м x=${x.toFixed(1)}м v=${speed.toFixed(1)}м/с</span>
      </div>
    `;
  }).join('');
  document.getElementById('telemetryCompare').innerHTML = html;
}

populateSimSelect();
updateSpeedLabel();