# ============================================================
#  Proyecto de Aula - Ecuaciones Diferenciales (V semestre)
#  Mantenimiento predictivo con la Ley de Paris (EDO de 1er orden)
#  Backend sencillo con Flask: solo calcula y devuelve JSON.
#  Ejecutar:  pip install flask   y luego   python app.py
# ============================================================

import math                                   # funciones matemáticas (sqrt, pi, exp, log)
from flask import Flask, render_template, request, jsonify  # herramientas de Flask

app = Flask(__name__)                         # crea la aplicación web


# ------------------------------------------------------------
# Método numérico RK4 (Runge-Kutta de 4º orden) hecho a mano.
# Sirve para "comprobar con software" la solución analítica.
# f: función derivada f(x, y); y0: valor inicial; x0..x1: intervalo
# ------------------------------------------------------------
def rk4(f, x0, y0, x1, pasos=4000):
    h = (x1 - x0) / pasos                     # tamaño de cada paso
    x, y = x0, y0                             # punto de partida
    puntos = [(x, y)]                         # guardamos la trayectoria
    for _ in range(pasos):                    # repetimos paso a paso
        k1 = f(x, y)                          # pendiente al inicio
        k2 = f(x + h / 2, y + h * k1 / 2)     # pendiente a la mitad (1)
        k3 = f(x + h / 2, y + h * k2 / 2)     # pendiente a la mitad (2)
        k4 = f(x + h, y + h * k3)             # pendiente al final
        y = y + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6  # promedio ponderado
        x = x + h                             # avanzamos en x
        puntos.append((x, y))                 # guardamos el nuevo punto
    return puntos                             # lista de (x, y)


# ------------------------------------------------------------
# Funciones de la Ley de Paris:  da/dN = beta * a^(m/2)
# ------------------------------------------------------------
def calc_beta(D, m, sigma, alpha):
    # beta = D * (2*sigma*sqrt(pi*alpha))^m   (ecuación 3 del documento)
    return D * (2 * sigma * math.sqrt(math.pi * alpha)) ** m


def calc_af(KIc, sigma, alpha):
    # tamaño crítico: a_f = (KIc / sigma_max)^2 / (pi*alpha), con sigma_max = 2*sigma (R = 0)
    return (KIc / (2 * sigma)) ** 2 / (math.pi * alpha)


def a_de_N(N, a0, beta, m):
    # solución analítica por variables separables (ecuación 6)
    if m == 2:                                # caso lineal: crecimiento exponencial
        return a0 * math.exp(beta * N)
    base = a0 ** (1 - m / 2) + (1 - m / 2) * beta * N  # lo que está entre corchetes
    if base <= 0:                             # la solución "explota" (asíntota vertical)
        return float("inf")
    return base ** (2 / (2 - m))              # se eleva a 2/(2-m)


def N_de_a(a, a0, beta, m):
    # ciclos necesarios para que la grieta pase de a0 a "a" (ecuación 7)
    if m == 2:
        return math.log(a / a0) / beta
    return (a ** (1 - m / 2) - a0 ** (1 - m / 2)) / ((1 - m / 2) * beta)


# ------------------------------------------------------------
# Página principal: devuelve el HTML
# ------------------------------------------------------------
@app.route("/")
def inicio():
    return render_template("index.html")      # busca templates/index.html


# ------------------------------------------------------------
# API 1: problema real (Ley de Paris + RUL)
# ------------------------------------------------------------
@app.route("/api/paris", methods=["POST"])
def api_paris():
    d = request.get_json()                    # datos enviados desde la página
    D = float(d["D"])                         # constante de Paris
    m = float(d["m"])                         # exponente de Paris
    sigma = float(d["sigma"])                 # amplitud de esfuerzo (MPa)
    alpha = float(d["alpha"])                 # factor geométrico
    KIc = float(d["KIc"])                     # tenacidad a la fractura (MPa*sqrt(m))
    a0 = float(d["a0"]) / 1000                # defecto inicial: mm -> metros
    a_det = float(d["a_det"]) / 1000          # tamaño detectable por inspección: mm -> m

    beta = calc_beta(D, m, sigma, alpha)      # constante de la EDO
    af = calc_af(KIc, sigma, alpha)           # tamaño crítico de falla (m)
    if af <= a0:                              # si la grieta ya es crítica, no hay vida
        return jsonify({"error": "El defecto inicial ya supera el tamaño crítico a_f."})
    Nf = N_de_a(af, a0, beta, m)              # vida total = RUL desde N = 0

    # tiempo de "explosión" N* (solo existe si m > 2)
    N_exp = 2 * a0 ** (1 - m / 2) / ((m - 2) * beta) if m > 2 else None

    # curva analítica para la gráfica (100 puntos entre 0 y Nf)
    curva = [{"N": Nf * i / 100, "a": a_de_N(Nf * i / 100, a0, beta, m) * 1000}
             for i in range(101)]

    # verificación numérica con RK4 (a en metros)
    num = rk4(lambda N, a: beta * a ** (m / 2), 0, a0, Nf)
    tabla = []                                # tabla analítica vs numérica
    for frac in [0, 0.25, 0.5, 0.75, 1]:      # 5 puntos como en la Tabla 4
        i = round(frac * (len(num) - 1))      # índice del punto numérico
        N_i, a_num = num[i]                   # ciclo y valor numérico
        a_ana = a_de_N(N_i, a0, beta, m)      # valor analítico en ese ciclo
        tabla.append({"N": N_i, "a_ana": a_ana * 1000, "a_num": a_num * 1000,
                      "err": abs(a_ana - a_num) / a_ana})  # error relativo

    # inspección: ¿cuándo se detecta la grieta y cuánta vida queda?
    insp = None
    if a0 < a_det < af:                       # solo tiene sentido entre a0 y af
        N_det = N_de_a(a_det, a0, beta, m)    # ciclo en que se detecta
        insp = {"N_det": N_det, "rul": Nf - N_det, "porc": 100 * (Nf - N_det) / Nf}

    # sensibilidad al esfuerzo (Tabla 5)
    sens_sigma = []
    for s in [50, 75, 100, 125, 150]:
        b = calc_beta(D, m, s, alpha)         # beta con ese esfuerzo
        f = calc_af(KIc, s, alpha)            # a_f con ese esfuerzo
        n = N_de_a(f, a0, b, m) if f > a0 else 0  # vida con ese esfuerzo
        sens_sigma.append({"sigma": s, "beta": b, "af": f * 1000, "Nf": n})

    # sensibilidad al defecto inicial (Tabla 6)
    sens_a0 = []
    for a in [0.10, 0.25, 0.50, 1.00, 2.00]:
        n = N_de_a(af, a / 1000, beta, m) if a / 1000 < af else 0
        sens_a0.append({"a0": a, "Nf": n, "rel": n / Nf})

    # campo de direcciones: pendientes da/dN en una rejilla (para dibujar)
    campo = []
    for i in range(13):                       # 13 columnas en N
        for j in range(1, 11):                # 10 filas en a
            N = Nf * 1.1 * i / 12
            a = af * 1000 * j / 10            # a en mm
            campo.append({"N": N, "a": a, "p": beta * (a / 1000) ** (m / 2) * 1000})

    return jsonify({                          # se envía todo a la página
        "beta": beta, "af": af * 1000, "Nf": Nf, "N_exp": N_exp,
        "curva": curva, "tabla": tabla, "insp": insp,
        "sens_sigma": sens_sigma, "sens_a0": sens_a0, "campo": campo})


# ------------------------------------------------------------
# API 2: ejercicio complementario (Torricelli) dh/dt = -k*sqrt(h)
# ------------------------------------------------------------
@app.route("/api/torricelli", methods=["POST"])
def api_torricelli():
    d = request.get_json()
    k = float(d["k"])                         # constante de vaciado
    h0 = float(d["h0"])                       # nivel inicial (cm)
    t_vacio = 2 * math.sqrt(h0) / k           # h = 0  ->  t = 2*sqrt(h0)/k

    def h(t):                                 # solución analítica h(t) = (sqrt(h0) - k t/2)^2
        return max(math.sqrt(h0) - k * t / 2, 0) ** 2

    curva = [{"t": t_vacio * i / 100, "h": h(t_vacio * i / 100)} for i in range(101)]

    # RK4 hasta un poco antes de vaciarse (cerca de h=0 se pierde la unicidad)
    t_fin = t_vacio * 15 / 16
    num = rk4(lambda t, y: -k * math.sqrt(max(y, 0)), 0, h0, t_fin, 3000)
    tabla = []
    for frac in [0, 0.25, 0.5, 0.75, 15 / 16]:     # fracciones del tiempo de vaciado (0,4,8,12,15 min en el ejemplo)
        i = round(frac / (15 / 16) * (len(num) - 1))  # índice del punto numérico
        t_i, h_num = num[i]                         # tiempo y valor numérico
        tabla.append({"t": t_i, "h_ana": h(t_i), "h_num": h_num, "err": abs(h(t_i) - h_num)})

    return jsonify({"t_vacio": t_vacio, "curva": curva, "tabla": tabla})


# ------------------------------------------------------------
# API 3: umbrales de falla del dataset AI4I 2020 (fresadora CNC)
# ------------------------------------------------------------
@app.route("/api/ai4i", methods=["POST"])
def api_ai4i():
    d = request.get_json()
    T_aire = float(d["T_aire"])               # temperatura del aire (K)
    T_proc = float(d["T_proc"])               # temperatura de proceso (K)
    rpm = float(d["rpm"])                     # velocidad de rotación
    par = float(d["par"])                     # par / torque (Nm)
    desgaste = float(d["desgaste"])           # desgaste de herramienta (min)
    calidad = d["calidad"]                    # calidad del producto: L, M o H

    dT = T_proc - T_aire                      # diferencia de temperaturas
    potencia = par * rpm * 2 * math.pi / 60   # P = par * velocidad angular (W)
    limite_osf = {"L": 11000, "M": 12000, "H": 13000}[calidad]  # límite de sobrecarga

    fallas = [                                # cada modo de falla con su regla
        {"nombre": "TWF - Desgaste de herramienta",
         "valor": f"{desgaste:.0f} min", "regla": "falla entre 200 y 240 min",
         "falla": desgaste >= 200},
        {"nombre": "HDF - Disipación de calor",
         "valor": f"ΔT = {dT:.1f} K, {rpm:.0f} rpm", "regla": "ΔT < 8,6 K y rpm < 1380",
         "falla": dT < 8.6 and rpm < 1380},
        {"nombre": "PWF - Falla de potencia",
         "valor": f"{potencia:.0f} W", "regla": "fuera de 3500–9000 W",
         "falla": potencia < 3500 or potencia > 9000},
        {"nombre": "OSF - Sobrecarga",
         "valor": f"{desgaste * par:.0f} min·Nm", "regla": f"> {limite_osf} min·Nm (calidad {calidad})",
         "falla": desgaste * par > limite_osf},
    ]
    return jsonify({"fallas": fallas, "algunaFalla": any(f["falla"] for f in fallas)})


# Arranca el servidor en http://127.0.0.1:5000
if __name__ == "__main__":
    app.run(debug=True)
