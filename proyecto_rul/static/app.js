// ============================================================
//  Lógica de la página: envía datos al backend y dibuja gráficas
// ============================================================

// ---------- Utilidades ----------
const $ = (id) => document.getElementById(id);                 // atajo para buscar por id
const fmt = (x, d = 0) => x.toLocaleString("es-CO", { maximumFractionDigits: d }); // número con formato colombiano
const sci = (x) => x.toExponential(3).replace(".", ",");       // notación científica
const graficas = {};                                           // guardamos las gráficas para poder borrarlas

// Envía un formulario como JSON a una ruta del backend y devuelve la respuesta
async function enviar(url, form) {
  const datos = Object.fromEntries(new FormData(form));       // lee todos los campos
  const r = await fetch(url, {                                 // petición POST
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  return r.json();                                             // convierte la respuesta a objeto
}

// Crea (o reemplaza) una gráfica de Chart.js en un <canvas>
function dibujar(id, config) {
  if (graficas[id]) graficas[id].destroy();                    // borra la anterior si existe
  graficas[id] = new Chart($(id), config);                     // crea la nueva
}

// Estilo común de las gráficas
Chart.defaults.font.family = "system-ui, sans-serif";
Chart.defaults.color = "#6b7684";
const AZUL = "#1f4e79", ROJO = "#c0504d", VERDE = "#2e8b57", GRIS = "#b8c4d0";

// ---------- Pestañas ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("activa"));     // quita la marca
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("visible"));  // oculta paneles
    btn.classList.add("activa");                                                       // marca la pestaña
    $(btn.dataset.tab).classList.add("visible");                                       // muestra su panel
  });
});

// ============================================================
//  Problema real: Ley de Paris
// ============================================================
$("formParis").addEventListener("submit", async (e) => {
  e.preventDefault();                                          // evita recargar la página
  const r = await enviar("/api/paris", e.target);              // pide los cálculos
  if (r.error) { $("msgInsp").textContent = r.error; return; } // muestra error si hay

  // --- Indicadores ---
  $("kBeta").textContent = sci(r.beta);
  $("kAf").textContent = fmt(r.af, 2);
  $("kNf").textContent = fmt(r.Nf);
  $("kNexp").textContent = r.N_exp ? fmt(r.N_exp) : "no aplica";

  // --- Mensaje de inspección ---
  $("msgInsp").textContent = r.insp
    ? `Si la inspección detecta la grieta en ${e.target.a_det.value} mm (N ≈ ${fmt(r.insp.N_det)} ciclos), ` +
      `solo quedarían ${fmt(r.insp.rul)} ciclos: el ${fmt(r.insp.porc, 1)} % de la vida total.`
    : "";

  // --- Gráfica de a(N) con línea del tamaño crítico ---
  const puntosNum = r.tabla.map((f) => ({ x: f.N, y: f.a_num }));  // puntos RK4
  dibujar("gCurva", {
    type: "scatter",
    data: {
      datasets: [
        { label: "Solución analítica", data: r.curva.map((p) => ({ x: p.N, y: p.a })),
          showLine: true, borderColor: AZUL, pointRadius: 0, borderWidth: 2.5 },
        { label: "Numérica RK4", data: puntosNum, backgroundColor: ROJO, pointRadius: 6 },
        { label: "a_f (falla)", data: [{ x: 0, y: r.af }, { x: r.Nf, y: r.af }],
          showLine: true, borderColor: ROJO, borderDash: [6, 4], pointRadius: 0 },
      ],
    },
    options: { scales: {
      x: { title: { display: true, text: "N (ciclos)" } },
      y: { title: { display: true, text: "a (mm)" } } } },
  });

  // --- Campo de direcciones: segmentos cortos con la pendiente en cada punto ---
  const Nmax = r.Nf * 1.1, Amax = r.af * 1.05;                 // rango de los ejes
  const seg = [];                                              // lista de segmentos
  r.campo.forEach((c) => {
    const s = c.p * Nmax / Amax;                               // pendiente en escala de pantalla
    const L = Math.hypot(1, s);                                // largo para normalizar
    const dx = 0.025 * Nmax / L, dy = 0.025 * Amax * s / L;    // mitad del segmento
    seg.push({ x: c.N - dx, y: c.a - dy }, { x: c.N + dx, y: c.a + dy }, { x: null, y: null }); // null corta la línea
  });
  dibujar("gCampo", {
    type: "scatter",
    data: { datasets: [
      { label: "Pendientes", data: seg, showLine: true, spanGaps: false,
        borderColor: GRIS, pointRadius: 0, borderWidth: 1.5 },
      { label: "a(N) con a₀ dado", data: r.curva.map((p) => ({ x: p.N, y: p.a })),
        showLine: true, borderColor: AZUL, pointRadius: 0, borderWidth: 2.5 },
    ] },
    options: { scales: {
      x: { min: 0, max: Nmax, title: { display: true, text: "N (ciclos)" } },
      y: { min: 0, max: Amax, title: { display: true, text: "a (mm)" } } } },
  });

  // --- Tabla analítica vs numérica ---
  $("tParis").innerHTML = r.tabla.map((f) =>
    `<tr><td>${fmt(f.N)}</td><td>${fmt(f.a_ana, 4)}</td><td>${fmt(f.a_num, 4)}</td><td>${sci(f.err)}</td></tr>`
  ).join("");

  // --- Sensibilidad (pestaña 3) ---
  $("tSigma").innerHTML = r.sens_sigma.map((f) =>
    `<tr><td>${f.sigma}</td><td>${sci(f.beta)}</td><td>${fmt(f.af, 1)}</td><td>${fmt(f.Nf)}</td></tr>`).join("");
  $("tA0").innerHTML = r.sens_a0.map((f) =>
    `<tr><td>${fmt(f.a0, 2)}</td><td>${fmt(f.Nf)}</td><td>${fmt(f.rel, 2)}</td></tr>`).join("");

  dibujar("gSigma", {                                          // RUL vs Δσ en escala log-log
    type: "line",
    data: { datasets: [{ label: "N_f", data: r.sens_sigma.map((f) => ({ x: 2 * f.sigma, y: f.Nf })),
      borderColor: AZUL, backgroundColor: AZUL, pointRadius: 5 }] },
    options: { plugins: { legend: { display: false } }, scales: {
      x: { type: "logarithmic", title: { display: true, text: "Δσ (MPa)" } },
      y: { type: "logarithmic", title: { display: true, text: "RUL (ciclos)" } } } },
  });
  dibujar("gA0", {                                             // RUL vs a0
    type: "line",
    data: { datasets: [{ label: "N_f", data: r.sens_a0.map((f) => ({ x: f.a0, y: f.Nf })),
      borderColor: VERDE, backgroundColor: VERDE, pointRadius: 5 }] },
    options: { plugins: { legend: { display: false } }, scales: {
      x: { type: "linear", title: { display: true, text: "a₀ (mm)" } },
      y: { title: { display: true, text: "RUL (ciclos)" } } } },
  });
});

// ============================================================
//  Ejercicio complementario: Torricelli
// ============================================================
$("formTorr").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await enviar("/api/torricelli", e.target);
  $("kVacio").textContent = fmt(r.t_vacio, 2);                 // tiempo en que h = 0

  dibujar("gTorr", {
    type: "scatter",
    data: { datasets: [
      { label: "Analítica h(t)", data: r.curva.map((p) => ({ x: p.t, y: p.h })),
        showLine: true, borderColor: AZUL, pointRadius: 0, borderWidth: 2.5 },
      { label: "Numérica RK4", data: r.tabla.map((f) => ({ x: f.t, y: f.h_num })),
        backgroundColor: ROJO, pointRadius: 6 },
    ] },
    options: { scales: {
      x: { title: { display: true, text: "t (min)" } },
      y: { title: { display: true, text: "h (cm)" } } } },
  });

  $("tTorr").innerHTML = r.tabla.map((f) =>
    `<tr><td>${fmt(f.t, 2)}</td><td>${fmt(f.h_ana, 4)}</td><td>${fmt(f.h_num, 4)}</td><td>${sci(f.err)}</td></tr>`
  ).join("");
});

// ============================================================
//  Umbrales de falla AI4I 2020
// ============================================================
$("formAi4i").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = await enviar("/api/ai4i", e.target);
  const est = $("estadoAi4i");
  est.className = "estado " + (r.algunaFalla ? "mal" : "ok");  // color según resultado
  est.textContent = r.algunaFalla ? "⚠ Riesgo de falla: intervenir la máquina" : "✓ Operación normal";
  $("listaFallas").innerHTML = r.fallas.map((f) => `
    <div class="falla ${f.falla ? "si" : ""}">
      <h3>${f.falla ? "✗" : "✓"} ${f.nombre}</h3>
      <p><b>Valor:</b> ${f.valor}</p>
      <p><b>Umbral:</b> ${f.regla}</p>
    </div>`).join("");
});

// Al abrir la página se calculan los valores del documento automáticamente
$("formParis").requestSubmit();
$("formTorr").requestSubmit();
$("formAi4i").requestSubmit();
