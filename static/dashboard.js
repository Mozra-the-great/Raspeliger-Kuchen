// VERSION: dropdowns-v2-20260527
// ============================================
// Dashboard v3 - Wetter, Verkehr, Räume
// ============================================

// ----- UHR -----
function updateClock() {
    const now = new Date();
    const t = [now.getHours(), now.getMinutes(), now.getSeconds()]
        .map(n => String(n).padStart(2, "0")).join(":");
    document.getElementById("clock").textContent = t;
}
setInterval(updateClock, 1000);
updateClock();


// ----- WETTER -----
async function ladeWetter() {
    try {
        const res = await fetch("/api/wetter");
        if (!res.ok) throw new Error("Server-Fehler");
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        document.getElementById("weather-icon").textContent = data.current.icon;
        document.getElementById("weather-temp").textContent = data.current.temp;
        document.getElementById("weather-text").textContent = data.current.text;
        document.getElementById("weather-feels").textContent = data.current.feels_like + "°";
        document.getElementById("weather-wind").textContent = data.current.wind + " km/h";
        document.getElementById("weather-humidity").textContent = data.current.humidity + "%";
        document.getElementById("weather-update").textContent = data.abgerufen;

        const fc = data.forecast.slice(1, 4);
        document.getElementById("weather-forecast").innerHTML = fc.map(d => `
            <div class="forecast-day">
                <div class="forecast-tag">${d.tag}</div>
                <div class="forecast-icon">${d.icon}</div>
                <div class="forecast-temps"><strong>${d.max}°</strong> / ${d.min}°</div>
                ${d.regen_pct > 30 ? `<div class="forecast-regen">💧 ${d.regen_pct}%</div>` : ''}
            </div>
        `).join("");

        document.getElementById("sunrise").textContent = data.tag.sunrise;
        document.getElementById("sunset").textContent = data.tag.sunset;
        document.getElementById("uv").textContent = data.tag.uv;

    } catch (err) {
        console.error("Wetter-Fehler:", err);
        document.getElementById("weather-text").textContent = "Wetter offline";
    }
}
ladeWetter();
setInterval(ladeWetter, 600000);


// ----- VERKEHR -----
async function ladeVerkehr() {
    try {
        const res = await fetch("/api/verkehr");
        const data = await res.json();
        const card = document.getElementById("traffic-card");
        const light = document.getElementById("traffic-light");
        const badge = document.getElementById("traffic-badge");

        card.classList.remove("status-gruen", "status-gelb", "status-rot");
        light.classList.remove("gruen", "gelb", "rot");

        card.classList.add(`status-${data.status}`);
        light.classList.add(data.status);
        badge.textContent = data.label;
        document.getElementById("traffic-label").textContent = data.label;
        document.getElementById("traffic-desc").textContent = data.beschreibung;
        document.getElementById("traffic-details").innerHTML =
            data.details.map(d => `<li>${d}</li>`).join("");

    } catch (err) {
        console.error("Verkehr-Fehler:", err);
    }
}
ladeVerkehr();
setInterval(ladeVerkehr, 60000);


// ----- RÄUME -----
async function ladeRaeume() {
    try {
        const res = await fetch("/api/raeume");
        const raeume = await res.json();
        zeigeRaeume(raeume);
    } catch (err) {
        console.error("Räume-Fehler:", err);
    }
}

function zeigeRaeume(raeume) {
    const grid = document.getElementById("room-grid");
    grid.innerHTML = "";

    raeume.forEach(raum => {
        const frei = !raum.belegt;
        const raumId = raum.name.toLowerCase().replace(/\s+/g, "_");

        let detailText = "Verfügbar";
        if (raum.belegt && raum.nutzer && raum.bis) {
            detailText = `${raum.nutzer} · bis ${raum.bis}`;
        } else if (raum.naechste_buchung) {
            detailText = `Nächste: ${raum.naechste_buchung.start} ${raum.naechste_buchung.nutzer}`;
        }

        const card = document.createElement("div");
        card.className = `room-card ${frei ? "frei" : "belegt"}`;
        card.innerHTML = `
            <div class="room-header">
                <span class="room-name">${raum.name}</span>
                <span class="room-badge ${frei ? "frei" : "belegt"}">${frei ? "Frei" : "Belegt"}</span>
            </div>
            <div class="room-details">${detailText}</div>
        `;
        card.addEventListener("click", () => {
            window.location.href = `/raum/${raumId}`;
        });
        grid.appendChild(card);
    });
}
ladeRaeume();
setInterval(ladeRaeume, 30000);


// ----- BUCHUNGS-MODAL -----
const modal = document.getElementById("booking-modal");

function fuelleDatumOptionen() {
    const select = document.getElementById("input-datum");
    select.innerHTML = "";
    const heute = new Date();
    for (let i = 0; i < 15; i++) {
        const d = new Date(heute.getTime() + i * 86400000);
        const iso = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
        const anzeige = `${String(d.getDate()).padStart(2,"0")}.${String(d.getMonth()+1).padStart(2,"0")}.${d.getFullYear()}`;
        let label = anzeige;
        if (i === 0) label += " (heute)";
        else if (i === 1) label += " (morgen)";
        const opt = document.createElement("option");
        opt.value = iso;
        opt.textContent = label;
        select.appendChild(opt);
    }
}

function fuelleZeitOptionen(selectId, vorauswahl) {
    const select = document.getElementById(selectId);
    select.innerHTML = "";
    for (let h = 8; h <= 18; h++) {
        const mins = (h < 18) ? [0, 30] : [0];
        for (const m of mins) {
            const zeit = `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
            const opt = document.createElement("option");
            opt.value = zeit;
            opt.textContent = zeit;
            if (zeit === vorauswahl) opt.selected = true;
            select.appendChild(opt);
        }
    }
}

function naechsteHalbeStunde() {
    const jetzt = new Date();
    let h = jetzt.getHours();
    let m = jetzt.getMinutes();
    if (m < 30) m = 30;
    else { m = 0; h += 1; }
    if (h < 8) { h = 8; m = 0; }
    if (h >= 18) { h = 17; m = 30; }
    return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
}

document.getElementById("btn-new-booking").addEventListener("click", () => {
    fuelleDatumOptionen();
    const startZeit = naechsteHalbeStunde();
    const [sh, sm] = startZeit.split(":").map(Number);
    let eh = sh + 1, em = sm;
    if (eh > 18) { eh = 18; em = 0; }
    const endeZeit = `${String(eh).padStart(2,"0")}:${String(em).padStart(2,"0")}`;
    fuelleZeitOptionen("input-start", startZeit);
    fuelleZeitOptionen("input-ende", endeZeit);
    modal.classList.add("active");
});

document.getElementById("btn-cancel").addEventListener("click", () => {
    modal.classList.remove("active");
});

document.getElementById("btn-save").addEventListener("click", async () => {
    const raum    = document.getElementById("input-raum").value;
    const nutzer  = document.getElementById("input-nutzer").value;
    const datum   = document.getElementById("input-datum").value;
    const vonZeit = document.getElementById("input-start").value;
    const bisZeit = document.getElementById("input-ende").value;

    if (!nutzer || !datum || !vonZeit || !bisZeit) {
        alert("Bitte alle Felder ausfüllen!");
        return;
    }
    if (bisZeit <= vonZeit) {
        alert("BIS muss nach VON liegen!");
        return;
    }

    const daten = {
        raum: raum,
        nutzer: nutzer,
        start: `${datum} ${vonZeit}`,
        ende:  `${datum} ${bisZeit}`
    };

    try {
        const res = await fetch("/buchen", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(daten)
        });
        const result = await res.json();
        if (result.status === "ok") {
            modal.classList.remove("active");
            document.getElementById("input-nutzer").selectedIndex = 0;
            ladeRaeume();
        } else {
            alert("Fehler: " + result.nachricht);
        }
    } catch (err) {
        alert("Verbindungsfehler: " + err.message);
    }
});
