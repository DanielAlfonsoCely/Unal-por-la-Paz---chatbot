"""
Prueba de concurrencia DIRECTA contra Ollama (sin Dify).

Simula N usuarios preguntando al mismo tiempo, con un prompt del tamano real
de la demo: prompt de sistema + 6 fragmentos de ~2048 caracteres (Top K 6),
think=false y temperatura 0.3. Cada peticion lleva una marca unica al inicio
para que Ollama no reutilice la cache de otra peticion (seria tramposo).

Uso (en la torre, con Ollama abierto; el proxy NO hace falta aqui):
    python prueba_concurrencia_ollama.py
    python prueba_concurrencia_ollama.py --niveles 1 5 10 --pausa 10

Guarda dos CSV (detalle y resumen) en la carpeta "resultados" junto al script.
Solo libreria estandar.
"""
import argparse
import csv
import http.client
import json
import os
import statistics
import sys
import threading
import time
import uuid
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MODELO = "gemma4:12b"
TEMPERATURA = 0.3

PROMPT_SISTEMA = """Eres un asistente que responde preguntas sobre el Informe Final de la Comisión de la Verdad de Colombia.

Reglas:
- Responde SOLO con la información de los fragmentos que recibes. Si no alcanzan para responder, dilo con claridad ("No encuentro información sobre eso en los documentos disponibles") y no inventes.
- No uses conocimiento propio para completar cifras, fechas o nombres que no estén en los fragmentos.
- Responde en español, en máximo 3 párrafos cortos, sin títulos ni listas.
- Incluye cifras, fechas, leyes y nombres concretos cuando aparezcan en los fragmentos, y no mezcles datos de años distintos.
- Si la pregunta no tiene que ver con el conflicto armado, la paz o la verdad histórica de Colombia, di amablemente que no puedes ayudar con eso."""

# Parecido (no identico) a la plantilla que usa Dify para meter los fragmentos.
PLANTILLA_CONTEXTO = """Use the following context as your learned knowledge, inside <context></context> XML tags.
<context>
{contexto}
</context>
When answer to user:
- If you don't know, just say that you don't know.
- If you don't know when you are not sure, ask for clarification.
Avoid mentioning that you obtained the information from the context.
And answer according to the language of the user's question.

"""

# Los 6 fragmentos reales que Dify recupero para la pregunta de mujeres y tierra
# (Top K 6). Todas las preguntas de abajo se responden con ellos, asi las
# respuestas tienen un largo realista (no "no encuentro informacion").
FRAGMENTOS = [
    '70 mi cuerpo es la verdad\nLa mujer que tiene tierra no dejará morir a sus hijos de hambre. Hemos tenido \nluchas por la tierra y hemos estado amenazados de muerte por un pedazo de tierra. Pero hay muchas mujeres sin tierra. Entonces la idea mía es que toda mujer \ncampesina tenga, así sea, una hectárea. Porque ahí nosotras tenemos una vivienda, \nuna huerta y algunos otros cultivos que son la seguridad alimentaria para nosotras \ny nuestra familia. La cuestión es que la tierra sea titulada a la mujer, porque hay \nmuchas que tienen su marido, pero la tierra es del marido y cuando al marido no \nle da la gana no la deja sembrar ni una mata de yuca83.\nAunque el despojo no aparece como uno de los delitos más comunes contra las \nmujeres –al menos no de manera directa–, sí es uno de los que más las han afectado, al incrementar la dificultad –ya desproporcionada– de adquirir la tierra, cuya \nobtención suele ser indirecta (por matrimonio, convivencia o herencia) y no por una \ncompra que las convierta en titulares. En muchos casos, no tienen conocimiento \nde sus derechos como copropietarias u otras formas de tenencia, y no cuentan con \ndocumentos que prueben su relación conyugal, como escrituras públicas o actas de \nadjudicación, lo que representa trabas adicionales para ellas. En últimas, lo que hay \nen el fondo de estas dificultades es «la precariedad en el acceso a la propiedad y un \nejercicio restringido de derechos sobre la tierra» para las mujeres84.\n Según la base de datos de la Unidad de Restitución de Tierras (URT)85, de \nlas 35.158 sentencias, 17.308 (49 %) corresponden a mujeres y 17.848 (51 %) a \nhombres. Tan solo el 23 % de las sentencias cuenta con información del área restituida, donde se identificaron 52.084 hectáreas para mujeres y 97.204 hectáreas \npara hombres. A pesar de la casi paridad en las sentencias, en términos de la tierra \nefectivamente restituida, a las mujeres les correspondió la mitad de la tierra que se \nles devolvió a los hombres.',
    'El problema de la tierra',
    'recomendaciones 329\nel retorno seguro a los territorios y la titulación a nombre de las mujeres \ncomo una certeza de la propiedad593. En el caso de pueblos indígenas y \ncomunidades afrodescendientes, la tierra debe ser titulada colectivamente, \ndando prioridad a las mujeres indígenas, negras, afrodescendientes, \nraizales y palenqueras.\n– La Agencia Nacional de Tierras, para la compra de predios, debe verificar que sean tierras aptas para la agricultura. Todo esto implica que las \nvíctimas, y especialmente las mujeres, deben participar de manera activa \ndurante todo el proceso, ser consultadas sobre la disponibilidad de las tierras para la adjudicación y reparación, y ser informadas sobre la vocación \nproductiva de la región. Esto permitiría avanzar en la seguridad alimentaria \nde las familias y contribuiría a la tenencia segura de la tierra. \n– Los programas de titulación de tierras deben priorizar a las mujeres \nvíctimas del conflicto que son jefas de hogar, sumando a esto el acceso \na los beneficios sociales establecidos en la Ley 731 de 2020 o «ley de \nmujer rural», y a condiciones de seguridad y permanencia en las tierras \nrestituidas, adjudicadas o retornadas, para evitar que puedan enfrentar, \nnuevamente, hechos violentos. \n– Eliminar las barreras en el acceso a créditos formales para las mujeres \ny jóvenes campesinos(as), incluidos los apoyos y acompañamientos para \ngestionar, implementar, monitorear y evaluar proyectos productivos, eliminando así la intermediación y los riesgos de corrupción en los recursos \npúblicos destinados para tal fin.\n– Desarrollar programas laborales, y de acceso al empleo para las mujeres, que contemplen la relación entre las violencias basadas en género \ny el empoderamiento económico de las sobrevivientes, y promuevan la \nasociatividad a partir de las buenas prácticas realizadas por organizaciones y colectivos de mujeres.',
    'Del mismo modo, se da la concentración \ndel manejo de los bienes en los varones, otorgado por una recia tradición jurídica y \ncultural que, incluso, hasta hace muy poco tiempo concedía a los hombres el derecho \na administrar el dinero y los bienes de la sociedad conyugal (marital o de hecho), lo \nque causó que las mujeres perdieran su capacidad jurídica para agenciar la administración de los recursos1265.\nAún persisten sesgos de género que influyen en las decisiones importantes en temas \nciviles y de familia. Aunque progresivamente se han dado cambios culturales en las \nrelaciones de pareja, en la ruralidad se conservan prácticas patriarcales de dominación \ny desigualdad en las relaciones de poder hacia las mujeres (no solo frente a la tenencia \nde la tierra, sino en el conjunto del ejercicio de los derechos). Una lideresa de la región \ndel Catatumbo le dijo a la Comisión:\n«El problema de la falta de titulación de tierras, eso es otro que nos ha dejado \navanzar porque algunos como líderes hemos querido traer los mejores proyectos para \n1264 Ibíd. 1265 Ver caso Campesinas de Chimborazo en la transmedia de la Comisión de la Verdad.',
    'Era más \ndoloroso que la propia muerte. Esto era infame. El desarraigo para los wayuu es \nterrible porque tienen una concepción de la tierra diferente. Todos los seres paren: lo \nhacen las vacas, las cabras, las mujeres humanas; la tierra no. La tierra que nos dieron \nes del mismo tamaño que hay desde la creación, desde el principio del mundo, y no \nse reproduce.\nMatar a las mujeres era como matar la tierra porque la mujer es la metáfora de la \ntierra que es fija. Juyá, la lluvia, es masculino, es única y móvil. Pero la tierra es lo fijo, \nes el lugar, el territorio donde se nace, donde está el cementerio.',
    '¿qué pasó? significados y magnitudes de lo sucedido 69\nse suman las dificultades para acceder a la reparación por parte de las instituciones \nencargadas de implementar las políticas públicas para las víctimas80.\nDespojar a las mujeres de la tierra: exclusión social y jurídica\nAunque las luchas de las mujeres por la tierra han sido históricas, los procesos de exigibilidad de derechos en el marco de la restitución de tierras o de demandas administrativas81 han sido largos y llenos de obstáculos, no solo para demostrar que perdieron \nsus fincas, sus animales, el sustento de vida, sino también para que se reconozca el \ngran valor de eso que tenían. En palabras de Pilar,\n«[...] muchas mujeres han pasado por esta situación de sentir que su cuerpo no \nvale, que su finca o su tierra no vale, porque han tenido que dejarla y han tenido que \nabandonarla. Yo quisiera que el concepto de despojo se aplicara también a todo el \ntema de lo que significó ser sacado del territorio, a los campesinos de su tierra, perder \nconocimientos, perder a la familia»82.\nDe acuerdo con Pilar, la asociación que hace entre su cuerpo y el territorio, ese sentir en un momento dado que «su cuerpo y su tierra no valen», constituye una manera \nde nombrar la complejidad de las afectaciones del despojo. Por ello, esa sensación de \nmujer campesina; no valía es también el mensaje que han dejado los armados y las \ninstituciones: los primeros por haber sido los responsables del despojo o el abandono \nforzado, y los segundos por acción u omisión. \nPara entender la particularidad de esta experiencia, es preciso resaltar que las \nmujeres han sido históricamente excluidas de procesos de titulación, adjudicación y \nsucesión, mientras que los hombres han sido los principales propietarios o poseedores \nde la tierra. Estas y otras barreras no solo facilitaron su despojo, sino que redujeron \nal máximo las posibilidades de reclamación.',
]

PREGUNTAS = [
    "¿Cómo afectó el despojo de tierras a las mujeres campesinas?",
    "¿Qué dicen las cifras de restitución de tierras sobre las mujeres?",
    "¿Qué recomienda la Comisión sobre la titulación de tierras a las mujeres?",
    "¿Por qué a las mujeres les cuesta más demostrar que la tierra es suya?",
    "¿Qué relación hacen las mujeres campesinas entre su cuerpo y el territorio?",
    "¿Qué dice el informe sobre la tierra y la seguridad alimentaria de las mujeres?",
    "¿Qué barreras tienen las mujeres rurales para acceder a créditos y empleo?",
    "¿Qué significó el desarraigo para el pueblo wayuu?",
    "¿Cuánta tierra se restituyó a mujeres comparado con hombres?",
    "¿Qué papel tiene la Agencia Nacional de Tierras en las recomendaciones para las mujeres?",
]


def pedir(host, port, pregunta, nivel, idx, barrera):
    fila = {"modo": "ollama", "nivel": nivel, "usuario": idx + 1, "pregunta": pregunta,
            "ok": False, "error": "", "primera_palabra_s": None, "total_s": None,
            "cola_s": None, "lectura_s": None, "tokens_entrada": None,
            "tokens_salida": None, "generacion_tok_s": None, "penso": False,
            "inicio_respuesta": "", "_t_ini": None, "_t_fin": None}
    marca = uuid.uuid4().hex[:10]
    sistema = f"[consulta {marca}]\n" + PLANTILLA_CONTEXTO.format(
        contexto="\n\n".join(FRAGMENTOS)) + PROMPT_SISTEMA
    cuerpo = json.dumps({
        "model": MODELO,
        "messages": [{"role": "system", "content": sistema},
                     {"role": "user", "content": pregunta}],
        "stream": True,
        "think": False,
        "options": {"temperature": TEMPERATURA},
    }).encode("utf-8")

    if barrera is not None:
        barrera.wait()  # todos arrancan a la vez
    t0 = time.perf_counter()
    fila["_t_ini"] = t0
    conn = http.client.HTTPConnection(host, port, timeout=900)
    try:
        conn.request("POST", "/api/chat", body=cuerpo,
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            fila["error"] = f"HTTP {resp.status}: {resp.read(300)!r}"
            return fila
        texto, final = [], {}
        while True:
            linea = resp.readline()
            if not linea:
                break
            linea = linea.strip()
            if not linea:
                continue
            d = json.loads(linea)
            if "error" in d:
                fila["error"] = str(d["error"])[:300]
                return fila
            msg = d.get("message") or {}
            if msg.get("thinking"):
                fila["penso"] = True
            c = msg.get("content") or ""
            if c and fila["primera_palabra_s"] is None:
                fila["primera_palabra_s"] = time.perf_counter() - t0
            texto.append(c)
            if d.get("done"):
                final = d
        fin = time.perf_counter()
        fila["_t_fin"] = fin
        fila["total_s"] = fin - t0
        fila["tokens_entrada"] = final.get("prompt_eval_count")
        fila["tokens_salida"] = final.get("eval_count")
        if final.get("prompt_eval_duration"):
            fila["lectura_s"] = final["prompt_eval_duration"] / 1e9
        if final.get("eval_count") and final.get("eval_duration"):
            fila["generacion_tok_s"] = final["eval_count"] / (final["eval_duration"] / 1e9)
        if final.get("total_duration"):
            # lo que el cliente espero de mas = tiempo en la cola de Ollama (aprox.)
            fila["cola_s"] = max(0.0, fila["total_s"] - final["total_duration"] / 1e9)
        fila["inicio_respuesta"] = "".join(texto)[:80].replace("\n", " ")
        fila["ok"] = bool(final)
        if not final:
            fila["error"] = "la respuesta termino sin 'done'"
    except Exception as e:
        fila["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        conn.close()
    return fila


def percentil(valores, p):
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    k = max(0, min(len(v) - 1, round(p / 100 * len(v) + 0.5) - 1))
    return v[k]


def resumir(filas, nivel):
    ok = [f for f in filas if f["ok"]]
    ttft = [f["primera_palabra_s"] for f in ok]
    tot = [f["total_s"] for f in ok]
    ini = [f["_t_ini"] for f in filas if f["_t_ini"]]
    fin = [f["_t_fin"] for f in ok if f["_t_fin"]]
    pared = (max(fin) - min(ini)) if ini and fin else None
    toks = sum(f["tokens_salida"] or 0 for f in ok)
    gen = [f["generacion_tok_s"] for f in ok if f["generacion_tok_s"]]
    return {
        "modo": "ollama", "nivel": nivel, "ok": len(ok), "errores": len(filas) - len(ok),
        "primera_palabra_p50": percentil(ttft, 50), "primera_palabra_p95": percentil(ttft, 95),
        "primera_palabra_max": max(ttft) if ttft else None,
        "total_p50": percentil(tot, 50), "total_p95": percentil(tot, 95),
        "total_max": max(tot) if tot else None,
        "duracion_nivel_s": pared,
        "tok_s_conjunto": (toks / pared) if pared else None,
        "tok_s_por_usuario_mediana": statistics.median(gen) if gen else None,
        "tokens_entrada_mediana": statistics.median([f["tokens_entrada"] for f in ok if f["tokens_entrada"]] or [0]),
        "tokens_salida_mediana": statistics.median([f["tokens_salida"] for f in ok if f["tokens_salida"]] or [0]),
        "alguna_penso": any(f["penso"] for f in filas),
    }


def correr_nivel(host, port, n, cursor):
    barrera = threading.Barrier(n)
    filas = [None] * n
    hilos = []
    for i in range(n):
        q = PREGUNTAS[(cursor + i) % len(PREGUNTAS)]

        def trabajo(i=i, q=q):
            filas[i] = pedir(host, port, q, n, i, barrera)

        h = threading.Thread(target=trabajo, daemon=True)
        hilos.append(h)
        h.start()
    for h in hilos:
        h.join()
    return filas


def num(x, dec=2):
    """Numero con coma decimal para que Excel en espanol lo lea bien."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return "si" if x else "no"
    if isinstance(x, float):
        return f"{x:.{dec}f}".replace(".", ",")
    return x


def guardar_csv(ruta, filas):
    if not filas:
        return
    campos = [k for k in filas[0] if not k.startswith("_")]
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow({k: num(fila[k]) for k in campos})


def s(x):
    return "-" if x is None else f"{x:.1f}"


def main():
    ap = argparse.ArgumentParser(description="Prueba de concurrencia directa contra Ollama")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--niveles", type=int, nargs="+", default=[1, 5, 10, 15, 20])
    ap.add_argument("--pausa", type=float, default=5, help="segundos entre niveles")
    ap.add_argument("--etiqueta", default="", help="texto para el nombre del archivo, ej. paralelo4")
    a = ap.parse_args()

    carpeta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")
    os.makedirs(carpeta, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M")
    eti = f"_{a.etiqueta}" if a.etiqueta else ""
    ruta_det = os.path.join(carpeta, f"ollama{eti}_{sello}_detalle.csv")
    ruta_res = os.path.join(carpeta, f"ollama{eti}_{sello}_resumen.csv")

    print(f"Ollama en {a.host}:{a.port} | modelo {MODELO} | niveles {a.niveles}")
    print("Calentando (1 peticion, no cuenta)...", flush=True)
    f = pedir(a.host, a.port, PREGUNTAS[0], 0, 0, None)
    if not f["ok"]:
        print(f"Fallo el calentamiento: {f['error']}")
        sys.exit(1)
    print(f"  ok en {f['total_s']:.1f} s, {f['tokens_entrada']} tokens de entrada, "
          f"{f['tokens_salida']} de salida{'  OJO: PENSO' if f['penso'] else ''}\n", flush=True)

    todas, resumenes, cursor = [], [], 0
    for n in a.niveles:
        print(f"Nivel {n}: {n} peticiones a la vez...", flush=True)
        filas = correr_nivel(a.host, a.port, n, cursor)
        cursor += n
        r = resumir(filas, n)
        todas.extend(filas)
        resumenes.append(r)
        guardar_csv(ruta_det, todas)
        guardar_csv(ruta_res, resumenes)
        print(f"  {r['ok']}/{n} ok | 1a palabra p50 {s(r['primera_palabra_p50'])} s, "
              f"p95 {s(r['primera_palabra_p95'])} s, max {s(r['primera_palabra_max'])} s | "
              f"total p50 {s(r['total_p50'])} s, max {s(r['total_max'])} s | "
              f"{s(r['tok_s_conjunto'])} tok/s en conjunto, "
              f"{s(r['tok_s_por_usuario_mediana'])} tok/s por usuario"
              f"{'  OJO: alguna PENSO' if r['alguna_penso'] else ''}", flush=True)
        for e in [x for x in filas if not x["ok"]][:3]:
            print(f"    error usuario {e['usuario']}: {e['error']}")
        if n != a.niveles[-1]:
            time.sleep(a.pausa)

    print(f"\nListo. Detalle: {ruta_det}\nResumen: {ruta_res}")


if __name__ == "__main__":
    main()
