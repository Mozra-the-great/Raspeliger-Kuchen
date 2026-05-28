// VERSION: compact-3sections-v10-20260527

function askNutzer() {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:9999;';
    overlay.innerHTML = `
      <div style="background:#1a1f2e;border:1px solid #2a3343;border-radius:12px;padding:24px;min-width:320px;color:#e4e7ec;font-family:inherit;">
        <div style="font-size:13px;color:#8a92a3;letter-spacing:.5px;margin-bottom:12px;">WER BUCHT?</div>
        <select id="__nutzer-select" style="width:100%;padding:10px;background:#0f1421;border:1px solid #2a3343;border-radius:8px;color:#e4e7ec;font-size:15px;margin-bottom:16px;">
          <option value="Nick">Nick</option>
          <option value="Moritz">Moritz</option>
          <option value="Robin">Robin</option>
          <option value="Niklas">Niklas</option>
        </select>
        <div style="display:flex;gap:8px;justify-content:flex-end;">
          <button id="__nutzer-cancel" style="padding:10px 16px;background:transparent;border:1px solid #2a3343;border-radius:8px;color:#e4e7ec;cursor:pointer;font-size:14px;">Abbrechen</button>
          <button id="__nutzer-ok" style="padding:10px 16px;background:#4aa3ff;border:none;border-radius:8px;color:#fff;cursor:pointer;font-size:14px;font-weight:500;">Buchen</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const cleanup = () => overlay.remove();
    overlay.querySelector('#__nutzer-ok').onclick = () => { const v = overlay.querySelector('#__nutzer-select').value; cleanup(); resolve(v); };
    overlay.querySelector('#__nutzer-cancel').onclick = () => { cleanup(); resolve(null); };
    overlay.onclick = (e) => { if (e.target === overlay) { cleanup(); resolve(null); } };
  });
}

// ============================================
const RAUM_ID = document.body.dataset.raumId;
const RAUM_NAME = document.body.dataset.raumName;

function isoDate(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}
function plusTage(n) {
    return new Date(new Date().getTime() + n * 86400000);
}

function getWeekNumber(d) {
    const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const dayNum = date.getUTCDay() || 7;
    date.setUTCDate(date.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

let selectedDate = isoDate(plusTage(2));


// ----- HILFE: relative Zeit -----
function relativeZeit(sek) {
    if (sek == null || isNaN(sek) || sek < 0) return "—";
    if (sek < 5) return "gerade eben";
    if (sek < 60) return `vor ${sek} Sek`;
    if (sek < 3600) return `vor ${Math.floor(sek/60)} Min`;
    if (sek < 86400) return `vor ${Math.floor(sek/3600)} Std`;
    return `vor ${Math.floor(sek/86400)} Tg`;
}


// ----- UHR -----
function updateClock() {
    const now = new Date();
    const t = [now.getHours(), now.getMinutes(), now.getSeconds()]
        .map(n => String(n).padStart(2, "0")).join(":");
    document.getElementById("clock").textContent = t;
}
setInterval(updateClock, 1000);
updateClock();


// ----- TOAST -----
function toast(msg, type = "success") {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `toast show ${type}`;
    setTimeout(() => el.classList.remove("show"), 2200);
}


// ----- LABELS -----
function updateDayLabels() {
    const heute = new Date();
    const morgen = plusTage(1);
    const fmt = d => d.toLocaleDateString("de-DE", {weekday: "long", day: "numeric", month: "long"});

    const lt = document.getElementById("label-today");
    if (lt) lt.textContent = `HEUTE · ${fmt(heute).toUpperCase()}`;

    const lm = document.getElementById("label-tomorrow");
    if (lm) lm.textContent = `MORGEN · ${fmt(morgen).toUpperCase()}`;
}


// ----- TABS: 5 Folgetage (heute+2 bis heute+6) -----
function renderDateTabs() {
    const container = document.getElementById("date-tabs");
    if (!container) return;
    const heute = new Date();
    const tabs = [];
    for (let i = 2; i < 7; i++) {
        const d = new Date(heute.getTime() + i * 86400000);
        const iso = isoDate(d);
        const wt = d.toLocaleDateString("de-DE", {weekday: "short"});
        const datum = `${String(d.getDate()).padStart(2,"0")}.${String(d.getMonth()+1).padStart(2,"0")}.`;
        const label = `${wt} ${datum}`;
        const active = selectedDate === iso;
        tabs.push(`<button data-iso="${iso}" style="flex:1;flex-shrink:0;padding:6px 5px;background:${active ? '#4aa3ff' : 'rgba(15,20,33,.6)'};color:${active ? '#fff' : '#cbd5e1'};border:1px solid ${active ? '#4aa3ff' : '#2a3343'};border-radius:6px;font-size:11px;font-weight:${active ? '600' : '500'};cursor:pointer;white-space:nowrap;transition:all .15s;">${label}</button>`);
    }
    container.innerHTML = tabs.join("");
    container.querySelectorAll("button[data-iso]").forEach(btn => {
        btn.addEventListener("click", () => {
            selectedDate = btn.dataset.iso;
            renderDateTabs();
            loadDay(selectedDate, "bookings-future");
        });
    });
}


// ----- ANWESENHEIT (live) -----
async function loadPresence() {
    try {
        const res = await fetch(`/api/raum/${RAUM_ID}/anwesenheit`);
        const data = await res.json();
        renderPresence(data);
    } catch (err) {
        console.error("Anwesenheit-Fehler:", err);
    }
}

function renderPresence(data) {
    const card    = document.getElementById("presence-card");
    const iconEl  = document.getElementById("presence-icon");
    const statusEl= document.getElementById("presence-status");
    const pulseEl = document.getElementById("presence-pulse");
    const lastEl  = document.getElementById("presence-last");
    if (!card || !iconEl || !statusEl || !lastEl) return;

    if (data.occupied === true) {
        iconEl.textContent = "👤";
        statusEl.textContent = "PERSON ERKANNT";
        statusEl.style.color = "#4aa3ff";
        card.style.borderColor = "#4aa3ff";
        card.style.background = "rgba(74,163,255,.08)";
        if (pulseEl) pulseEl.style.background = "#4aa3ff";
    } else if (data.occupied === false) {
        iconEl.textContent = "🚪";
        statusEl.textContent = "NIEMAND IM RAUM";
        statusEl.style.color = "#94a3b8";
        card.style.borderColor = "#1e293b";
        card.style.background = "rgba(15,20,33,.4)";
        if (pulseEl) pulseEl.style.background = "#22c55e";
    } else {
        iconEl.textContent = "⏳";
        statusEl.textContent = "KEINE DATEN";
        statusEl.style.color = "#64748b";
        card.style.borderColor = "#1e293b";
        card.style.background = "rgba(15,20,33,.4)";
        if (pulseEl) pulseEl.style.background = "#64748b";
    }

    lastEl.textContent = data.alter_sek != null
        ? `Aktualisiert ${relativeZeit(data.alter_sek)}`
        : "Noch keine Daten empfangen";
}


// ----- SENSORDATEN -----
function sensorMessage(typ, wert) {
    if (wert == null || isNaN(wert)) return "";
    if (typ === "temperatur") {
        if (wert < 17) return "Heizung höher";
        if (wert < 19) return "Etwas wärmer";
        if (wert > 26) return "Kühlen";
        if (wert > 24) return "Etwas kühler";
    } else if (typ === "luftfeuchte") {
        if (wert < 30) return "Befeuchten";
        if (wert < 40) return "Luft trocken";
        if (wert > 70) return "Sehr feucht — lüften";
        if (wert > 60) return "Etwas feucht";
    } else if (typ === "co2") {
        if (wert > 1400) return "Sofort lüften";
        if (wert > 1000) return "Lüften";
        if (wert > 900) return "Bald lüften";
    }
    return "";
}

function updateSensorStatus(data) {
    const items = [
        { typ: "temperatur",  wert: data.temperatur,  idS: "d-temp-status", idM: "d-temp-msg" },
        { typ: "luftfeuchte", wert: data.luftfeuchte, idS: "d-hum-status",  idM: "d-hum-msg"  },
        { typ: "co2",         wert: data.co2,         idS: "d-co2-status",  idM: "d-co2-msg"  }
    ];
    items.forEach(({ typ, wert, idS, idM }) => {
        const b = bewerteWert(typ, wert);
        const s = document.getElementById(idS);
        const m = document.getElementById(idM);
        if (s) {
            const icon = b.kls === "ok" ? "✓" : (b.kls === "unknown" ? "?" : "⚠");
            s.style.background = b.color + "22";
            s.style.color = b.color;
            s.style.border = "1px solid " + b.color + "55";
            s.textContent = icon + " " + b.label;
        }
        if (m) m.textContent = sensorMessage(typ, wert);
    });
}

function updateDatum() {
    const now = new Date();
    const wd = document.getElementById("datum-weekday");
    const inf = document.getElementById("datum-info");
    if (wd) wd.textContent = now.toLocaleDateString("de-DE", { weekday: "long" }).toUpperCase();
    if (inf) {
        const datum = now.toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
        const kw = getWeekNumber(now);
        inf.textContent = `${datum} · KW ${kw}`;
    }
}


// ----- BUCHUNGS-STATUS -----
function updateRaumStatus(belegt) {
    const badge = document.getElementById("raum-status-badge");
    badge.textContent = belegt ? "BELEGT" : "FREI";
    badge.className = `status-badge ${belegt ? "belegt" : "frei"}`;
}


// ----- STEUERUNG -----
async function loadControlState() {
    try {
        const res = await fetch(`/api/raum/${RAUM_ID}/status`);
        const state = await res.json();
        renderControls(state);
    } catch (err) {
        console.error("Status-Fehler:", err);
    }
}

function renderControls(state) {
    document.querySelectorAll("[data-licht]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.licht === state.licht);
    });
    document.getElementById("state-licht").textContent = state.licht.toUpperCase();

    document.querySelectorAll("[data-rollo]").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.rollo === state.rollo);
    });
    const rolloLabel = {up: "OBEN", down: "UNTEN", stop: "STOPP"};
    document.getElementById("state-rollo").textContent = rolloLabel[state.rollo] || state.rollo.toUpperCase();

    document.querySelectorAll("[data-klima]").forEach(btn => {
        const aktiv = btn.dataset.klima === state.klima_modus;
        btn.classList.remove("active", "active-warm", "active-cool");
        if (aktiv) {
            if (state.klima_modus === "heat") btn.classList.add("active-warm");
            else if (state.klima_modus === "cool") btn.classList.add("active-cool");
            else btn.classList.add("active");
        }
    });
    document.getElementById("state-klima-soll").textContent = state.klima_soll;

    document.getElementById("btn-checkin").classList.toggle("checked", state.checkin);
    document.getElementById("btn-checkin").textContent = state.checkin ? "✓ EINGECHECKT" : "✓ CHECK-IN";
}

document.querySelectorAll("[data-licht]").forEach(btn => {
    btn.addEventListener("click", async () => {
        const action = btn.dataset.licht;
        try {
            const res = await fetch(`/api/raum/${RAUM_ID}/licht`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({action})
            });
            const data = await res.json();
            renderControls(data.state);
            toast(`Licht ${action.toUpperCase()}`);
        } catch (err) { toast("Fehler: " + err.message, "error"); }
    });
});

document.querySelectorAll("[data-rollo]").forEach(btn => {
    btn.addEventListener("click", async () => {
        const action = btn.dataset.rollo;
        try {
            const res = await fetch(`/api/raum/${RAUM_ID}/rollo`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({action})
            });
            const data = await res.json();
            renderControls(data.state);
            toast(`Rollo ${action.toUpperCase()}`);
        } catch (err) { toast("Fehler: " + err.message, "error"); }
    });
});

document.querySelectorAll("[data-klima]").forEach(btn => {
    btn.addEventListener("click", async () => {
        const modus = btn.dataset.klima;
        try {
            const res = await fetch(`/api/raum/${RAUM_ID}/klima`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({modus})
            });
            const data = await res.json();
            renderControls(data.state);
            const labels = {heat: "Heizen", cool: "Kühlen", off: "Aus"};
            toast(`Klima: ${labels[modus]}`);
        } catch (err) { toast("Fehler: " + err.message, "error"); }
    });
});

async function changeTemp(delta) {
    const aktuell = parseInt(document.getElementById("state-klima-soll").textContent);
    const neu = Math.max(15, Math.min(30, aktuell + delta));
    try {
        const res = await fetch(`/api/raum/${RAUM_ID}/klima`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({soll: neu})
        });
        const data = await res.json();
        renderControls(data.state);
    } catch (err) { toast("Fehler: " + err.message, "error"); }
}
document.getElementById("temp-up").addEventListener("click", () => changeTemp(1));
document.getElementById("temp-down").addEventListener("click", () => changeTemp(-1));

document.getElementById("btn-checkin").addEventListener("click", async () => {
    try {
        const res = await fetch(`/api/raum/${RAUM_ID}/checkin`, {method: "POST"});
        const data = await res.json();
        renderControls(data.state);
        toast(data.state.checkin ? "Eingecheckt!" : "Check-Out");
    } catch (err) { toast("Fehler: " + err.message, "error"); }
});

document.querySelectorAll("[data-quick]").forEach(btn => {
    btn.addEventListener("click", async () => {
        const dauer = parseInt(btn.dataset.quick);
        const nutzer = await askNutzer();
        if (!nutzer) return;
        try {
            const res = await fetch("/buchen-schnell", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({raum: RAUM_NAME, dauer_minuten: dauer, nutzer})
            });
            const data = await res.json();
            if (data.status === "ok") {
                toast(`Gebucht: ${data.start} – ${data.ende}`);
                loadBookings();
            } else {
                toast("Fehler: " + data.nachricht, "error");
            }
        } catch (err) { toast("Fehler: " + err.message, "error"); }
    });
});


// ----- KOMFORT-SCHWELLWERTE -----
const SCHWELLWERTE = {
    temperatur:  { ok: [19, 24],  warn: [17, 26],  unit: "°C", label: "Temperatur" },
    luftfeuchte: { ok: [40, 60],  warn: [30, 70],  unit: "%",       label: "Luftfeuchte" },
    co2:         { ok: [0, 1000], warn: [0, 1400], unit: "ppm",     label: "CO₂" }
};

function bewerteWert(typ, wert) {
    if (wert == null || isNaN(wert)) return { kls: "unknown", label: "keine Daten", color: "#64748b" };
    const s = SCHWELLWERTE[typ];
    const [okMin, okMax] = s.ok;
    const [warnMin, warnMax] = s.warn;
    if (wert >= okMin && wert <= okMax) return { kls: "ok", label: "Optimal", color: "#22c55e" };
    if (wert >= warnMin && wert <= warnMax) {
        return { kls: "warn", label: wert < okMin ? "etwas niedrig" : "etwas hoch", color: "#fbbf24" };
    }
    return { kls: "bad", label: wert < warnMin ? "kritisch niedrig" : "kritisch hoch", color: "#ef4444" };
}


// ----- TIMELINE-RENDERER (kompakter v10) -----
function renderTimelineInto(containerId, dateIso, buchungen) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const RANGE_START = 7;
    const RANGE_END = 20;
    const RANGE_MIN = (RANGE_END - RANGE_START) * 60;
    const toMin = (hhmm) => {
        const [h, m] = String(hhmm).split(":").map(Number);
        return h * 60 + (m || 0);
    };
    const toPct = (min) => ((min - RANGE_START * 60) / RANGE_MIN) * 100;

    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    const heuteIso = isoDate(now);
    const istHeute = dateIso === heuteIso;
    const valid = (buchungen || []).filter(b => b && b.start && b.ende);

    const sorted = [...valid].sort((a, b) => toMin(a.start) - toMin(b.start));
    const lanes = [];
    for (const b of sorted) {
        const sMin = toMin(b.start);
        let placed = false;
        for (let i = 0; i < lanes.length; i++) {
            const last = lanes[i][lanes[i].length - 1];
            if (toMin(last.ende) <= sMin) {
                b._lane = i;
                lanes[i].push(b);
                placed = true;
                break;
            }
        }
        if (!placed) {
            b._lane = lanes.length;
            lanes.push([b]);
        }
    }
    const isEmpty = sorted.length === 0;
    const laneCount = Math.max(1, lanes.length);
    const laneHeight = isEmpty ? 20 : 30;
    const lanePad = isEmpty ? 4 : 6;
    const timelineHeight = laneCount * laneHeight + Math.max(0, laneCount - 1) * 3 + lanePad * 2;

    const colorMap = {
        aktiv:   { bg: "rgba(74,163,255,.28)",  bd: "#4aa3ff", tx: "#dbeafe" },
        geplant: { bg: "rgba(148,163,184,.18)", bd: "#64748b", tx: "#cbd5e1" },
        vorbei:  { bg: "rgba(100,116,139,.1)",  bd: "#475569", tx: "#64748b" }
    };

    const labelHours = [];
    for (let h = RANGE_START; h <= RANGE_END; h += 2) labelHours.push(h);
    const labels = labelHours.map((h, idx) => {
        const isFirst = idx === 0;
        const isLast = idx === labelHours.length - 1;
        const tx = isFirst ? "0" : (isLast ? "-100%" : "-50%");
        return `<span style="position:absolute;top:0;left:${toPct(h*60)}%;transform:translateX(${tx});font-size:10px;color:#64748b;white-space:nowrap;line-height:1;">${String(h).padStart(2,"0")}:00</span>`;
    });

    let nowLine = "";
    if (istHeute && nowMin >= RANGE_START*60 && nowMin <= RANGE_END*60) {
        const np = toPct(nowMin);
        nowLine = `<div style="position:absolute;left:${np}%;top:0;bottom:0;width:2px;background:#22c55e;z-index:5;"><div style="position:absolute;top:-18px;left:50%;transform:translateX(-50%);background:#22c55e;color:#fff;font-size:9px;padding:1px 5px;border-radius:3px;white-space:nowrap;font-weight:600;letter-spacing:.3px;">JETZT</div></div>`;
    }

    const blocks = sorted.map(b => {
        const sMin = toMin(b.start);
        const eMin = toMin(b.ende);
        const left = Math.max(0, toPct(sMin));
        const width = Math.min(100, toPct(eMin)) - left;
        if (width <= 0) return "";
        const c = colorMap[b.status] || colorMap.geplant;
        const top = lanePad + b._lane * (laneHeight + 3);
        const dauer = eMin - sMin;
        const content = dauer < 45
            ? `<div style="font-weight:600;font-size:10px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;line-height:1.2;">${b.nutzer}</div><div style="font-size:8px;opacity:.7;white-space:nowrap;">${b.start}</div>`
            : `<div style="font-weight:600;font-size:11px;white-space:nowrap;text-overflow:ellipsis;overflow:hidden;">${b.nutzer}</div><div style="font-size:9px;opacity:.75;">${b.start}–${b.ende}</div>`;
        return `<div data-buchung-id="${b.id}" data-nutzer="${b.nutzer}" data-start="${b.start}" data-ende="${b.ende}" title="${b.nutzer} · ${b.start}–${b.ende} — Klick zum Stornieren" style="cursor:pointer;position:absolute;top:${top}px;height:${laneHeight}px;left:${left}%;width:${width}%;background:${c.bg};border:1px solid ${c.bd};border-radius:5px;padding:3px 6px;color:${c.tx};font-size:11px;overflow:hidden;z-index:2;line-height:1.2;box-sizing:border-box;">${content}</div>`;
    }).join("");

    const emptyMsg = istHeute ? "Keine Buchungen heute" : (dateIso === isoDate(new Date(now.getTime()+86400000)) ? "Keine Buchungen morgen" : "Keine Buchungen an diesem Tag");

    container.innerHTML = `
        <div style="position:relative;height:${timelineHeight}px;margin-top:6px;border-radius:6px;background:rgba(15,20,33,.4);border:1px solid #1e293b;">
            ${nowLine}
            ${blocks}
        </div>
        <div style="position:relative;height:13px;margin-top:2px;">
            ${labels.join("")}
        </div>
        ${sorted.length === 0 ? `<div style="text-align:center;color:#64748b;font-size:11px;margin-top:3px;">${emptyMsg}</div>` : ''}
    `;

    container.querySelectorAll('[data-buchung-id]').forEach(block => {
        block.onclick = () => stornoBuchung(
            block.dataset.buchungId,
            block.dataset.nutzer,
            block.dataset.start,
            block.dataset.ende
        );
    });

    return sorted;
}


// ----- LADE-FUNKTIONEN -----
async function loadDay(dateIso, containerId) {
    try {
        const res = await fetch(`/api/raum/${RAUM_ID}/buchungen?datum=${dateIso}`);
        const buchungen = await res.json();
        return renderTimelineInto(containerId, dateIso, Array.isArray(buchungen) ? buchungen : []);
    } catch (err) {
        console.error(`Buchungs-Fehler ${dateIso}:`, err);
        return [];
    }
}

async function loadBookings() {
    const heuteIso = isoDate(new Date());
    const morgenIso = isoDate(plusTage(1));

    const heuteBuchungen = await loadDay(heuteIso, "bookings-today");
    const aktiv = (heuteBuchungen || []).find(b => b && b.status === "aktiv");
    updateRaumStatus(!!aktiv);

    await loadDay(morgenIso, "bookings-tomorrow");
    await loadDay(selectedDate, "bookings-future");
}


// ----- STORNO -----
async function stornoBuchung(id, nutzer, start, ende) {
    if (!confirm(`Buchung wirklich stornieren?\n\n${nutzer} \u00B7 ${start}\u2013${ende}`)) return;
    try {
        const res = await fetch(`/stornieren/${id}`, { method: "POST" });
        const json = await res.json();
        if (json.status === "ok") {
            toast("Buchung storniert", "ok");
            loadBookings();
        } else {
            alert("Fehler: " + (json.nachricht || "unbekannt"));
        }
    } catch (err) {
        alert("Fehler: " + err.message);
    }
}


// ----- SENSOREN -----
async function loadSensors() {
    try {
        const res = await fetch(`/api/sensoren/${RAUM_ID}`);
        const data = await res.json();
        const setV = (id, val, dec) => {
            const el = document.getElementById(id);
            if (el) el.textContent = (val == null || isNaN(val)) ? "--" : (dec == null ? val : Number(val).toFixed(dec));
        };
        setV("d-temp", data.temperatur, 1);
        setV("d-hum", data.luftfeuchte, 1);
        setV("d-co2", data.co2, 0);
        updateSensorStatus(data);
    } catch (err) {
        console.error("Sensoren-Fehler:", err);
    }
}


// ----- INIT + AUTO-REFRESH -----
updateDatum();
updateDayLabels();
renderDateTabs();
loadSensors();
loadBookings();
loadControlState();
loadPresence();

setInterval(loadSensors, 10000);
setInterval(loadBookings, 30000);
setInterval(loadControlState, 5000);
setInterval(loadPresence, 5000);

setInterval(() => {
    if (selectedDate < isoDate(plusTage(2))) {
        selectedDate = isoDate(plusTage(2));
    }
    updateDatum();
    updateDayLabels();
    renderDateTabs();
}, 60000);
