"""
Cruce de las bases de Natalia contra nuestra base del repositorio (sin filtro de años).

Para cada documento de sus Excels busca su equivalente en candidatos_todos_anios.csv:
  1) Por link: si el enlace apunta al repositorio UNAL se saca el handle
       /handle/unal/N  y  /bitstream/handle/unal/N/...   -> directo
       /items/<uuid>  y  .../bitstreams/<uuid>/content    -> se le pregunta a la API del
                                                              repositorio a qué ítem pertenecen
       (solo se consulta la ficha del ítem, NO se descarga nada; los links externos
        no se consultan nunca)
  2) Por título exacto (normalizado: minúsculas, sin tildes, sin signos)
  3) Por título parecido (RapidFuzz). Se confirma con año (±1) o apellido del autor.

Estados (y orden en el Excel):
  Dudoso -> No está -> Entra al quitar años -> Ya la tenemos

La "Base final 2010-2021" se separa por TIPO DE APORTE:
  documentos (libros, artículos, tesis...) -> se cruzan
  proyectos                               -> hoja "Proyectos (Hermes)"
  lo demás (asignaturas, convocatorias...) -> hoja "Otras actividades"
La "Base Legado" se cruza completa.

Uso:
  pip install pandas openpyxl rapidfuzz requests
  python cruce_natalia.py candidatos_todos_anios.csv "Base_final_2010_-_2021.xlsx" "Base_Legado_....xlsx"

Opción: --sin-api  -> no se conecta a nada; esos links se cruzan solo por título

Salida: cruce_natalia.xlsx  (+ cruce_cache_api.json, para no repetir consultas)
"""
import json
import os
import re
import sys
import time
import unicodedata

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from rapidfuzz import fuzz, process

# ---------------- CONFIGURACIÓN ----------------
SALIDA = "cruce_natalia.xlsx"
CACHE = "cruce_cache_api.json"
API = "https://bffrepositorio.unal.edu.co/server/api"
PAUSA = 0.3

UMBRAL_SEGURO = 92      # título parecido >= esto + año o autor que coincide -> encontrado
UMBRAL_DUDOSO = 85      # título completo parecido desde esto (sin año/autor que confirme) -> dudoso
UMBRAL_BUSQUEDA = 70    # parecido mínimo para considerar un candidato
UMBRAL_DUDOSO_AUTOR = 70  # si coincide el apellido del autor, basta este parecido para marcarlo dudoso
MIN_LARGO_CORTO = 20    # títulos normalizados más cortos que esto necesitan confirmación aunque sean exactos

TIPOS_DOC = r"libro|ebook|art[ií]culo|tesis|trabajo (de grado|final)|monograf|cap[ií]tulo|informe|cartilla|ponencia|revista|bolet[ií]n"
TIPOS_PROYECTO = r"proyecto"

ORDEN_ESTADO = {"Dudoso": 0, "No está": 1, "Entra al quitar años": 2, "Ya la tenemos": 3}
COLOR_ESTADO = {"Dudoso": "FFEB9C", "No está": "FFC7CE",
                "Entra al quitar años": "DDEBF7", "Ya la tenemos": "C6EFCE"}
# ------------------------------------------------


def limpio(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    v = ILLEGAL_CHARACTERS_RE.sub("", str(v)).strip()
    return v or None


def sin_tildes(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()


def norm_titulo(s):
    if not limpio(s):
        return ""
    s = sin_tildes(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def titulo_principal(s):
    """Parte antes del subtítulo (':' , ' - ', '. ')."""
    if not limpio(s):
        return ""
    return norm_titulo(re.split(r":|\s[-–—]\s|\.\s", str(s), maxsplit=1)[0])


NO_APELLIDO = {"varios", "autores", "autor", "otros", "editor", "editores", "compilador", "comp",
               "coord", "universidad", "nacional", "colombia", "maria", "jose", "juan", "carlos",
               "luis", "jorge", "andres", "ana", "diana", "paula", "andrea", "alejandro", "david",
               "camilo", "daniel", "fernando", "javier", "eduardo", "alberto", "antonio", "manuel",
               "francisco", "ricardo", "mauricio", "carolina", "claudia", "sandra", "patricia"}


def apellidos(*textos):
    out = set()
    for t in textos:
        if not limpio(t):
            continue
        for w in re.split(r"[^a-z]+", sin_tildes(t).lower()):
            if len(w) >= 4 and w not in NO_APELLIDO:
                out.add(w)
    return out


def primer_anio(v):
    m = re.search(r"(1[89]\d{2}|20\d{2})", str(v)) if limpio(v) else None
    return int(m.group(1)) if m else None


def links(*textos):
    out = []
    for t in textos:
        if limpio(t):
            out += re.findall(r"https?://[^\s,;\"'<>]+", str(t))
    return [l.rstrip(").]") for l in out]


def fuente(lista):
    if not lista:
        return "Sin enlace"
    l = lista[0].lower()
    if "repositorio.unal.edu.co" in l:
        return "Repositorio UNAL"
    if "revistas.unal.edu.co" in l:
        return "Revistas UNAL"
    if "hermes.unal.edu.co" in l:
        return "Hermes"
    if ".unal.edu.co" in l:
        return "Otro sitio UNAL"
    if "drive.google" in l or "docs.google" in l:
        return "Google Drive"
    return "Externo"


def handle_de(url):
    m = re.search(r"repositorio\.unal\.edu\.co/(?:bitstream/)?handle/(unal/\d+)", url)
    return m.group(1) if m else None


# ---------------- API (solo para links del repositorio UNAL sin handle) ----------------
class Api:
    """Pregunta a la API del repositorio a qué ítem (handle) pertenece un link /items/<uuid>
    o /bitstreams/<uuid>. Solo lee la ficha del ítem: NO descarga archivos. Los links
    externos (revistas, Drive, otros sitios) nunca se consultan."""

    def __init__(self, usar):
        self.usar = usar
        self.cache = {}
        if os.path.exists(CACHE):
            with open(CACHE, encoding="utf-8") as f:
                self.cache = json.load(f)
        self.s = None

    def guardar(self):
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=1)

    def get(self, url):
        import requests
        if self.s is None:
            self.s = requests.Session()
            self.s.headers["User-Agent"] = "UNAL-por-la-Paz-chatbot/1.0 (cruce de bases)"
        for intento in range(2):
            try:
                time.sleep(PAUSA)
                r = self.s.get(url, timeout=15)
                if r.status_code == 200:
                    return r.json()
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 * (intento + 1))
                    continue
                return None
            except Exception:
                time.sleep(2 * (intento + 1))
        return None

    def handle(self, url):
        """Handle 'unal/N' de un link /items/<uuid> o /bitstreams/<uuid> del repositorio UNAL, o None."""
        m_item = re.search(r"repositorio\.unal\.edu\.co/items/([0-9a-f-]{36})", url)
        m_bit = re.search(r"repositorio\.unal\.edu\.co/server/api/core/bitstreams/([0-9a-f-]{36})", url)
        if not (m_item or m_bit):
            return None
        clave = (m_item or m_bit).group(1)
        if clave in self.cache:
            return self.cache[clave]
        if not self.usar:
            return None
        print(f"  consultando la ficha en el repositorio: {clave}")
        h = None
        if m_item:
            j = self.get(f"{API}/core/items/{clave}")
            h = j.get("handle") if j else None
        else:
            b = self.get(f"{API}/core/bitstreams/{clave}/bundle")
            href = (b or {}).get("_links", {}).get("item", {}).get("href")
            if href:
                j = self.get(href)
                h = j.get("handle") if j else None
        self.cache[clave] = h
        self.guardar()
        return h


# ---------------- lectura ----------------
def leer_bases(rutas):
    final = legado = None
    for r in rutas:
        hojas = pd.ExcelFile(r).sheet_names
        if "Base datos" in hojas:
            final = pd.read_excel(r, sheet_name="Base datos", dtype=str)
        elif "Base_Legado_UNAL" in hojas:
            legado = pd.read_excel(r, sheet_name="Base_Legado_UNAL", dtype=str)
        else:
            sys.exit(f"No reconozco {r}: hojas {hojas}")
    if final is None or legado is None:
        sys.exit("Faltan bases: necesito la 'Base final' (hoja 'Base datos') y la 'Base Legado' (hoja 'Base_Legado_UNAL')")
    final = final.dropna(how="all")
    legado = legado.dropna(how="all")
    final = final[final["TITULO"].map(limpio).notna()]
    legado = legado[legado["Título del trabajo"].map(limpio).notna()]
    return final, legado


def registros_legado(df):
    out = []
    for _, r in df.iterrows():
        ls = links(r.get("Enlace"))
        out.append({
            "Base": "Legado", "ID": limpio(r.get("ID")),
            "Tipo": limpio(r.get("Tipo de publicación")),
            "Título": limpio(r.get("Título del trabajo")),
            "Año": primer_anio(r.get("Año")),
            "Autor": limpio(r.get("Autor")) or limpio(r.get("Varios Autores*")),
            "_apellidos": apellidos(r.get("Autor"), r.get("Varios Autores*")),
            "Enlace": ls[0] if ls else limpio(r.get("Enlace")),
            "_links": ls,
        })
    return out


def registros_final(df):
    docs, proys, otras = [], [], []
    for i, r in df.iterrows():
        tipo = limpio(r.get("TIPO DE APORTE")) or "(sin tipo)"
        todo = " ".join(str(v) for v in r.values if limpio(v))
        ls = links(todo)
        base = {
            "Base": "Base final", "ID": f"Fila {i + 2}",
            "Tipo": tipo, "Título": limpio(r.get("TITULO")),
            "Año": primer_anio(r.get("FECHA")),
            "Autor": limpio(r.get("AUTOR")) or limpio(r.get("COORDINADOR")),
            "_apellidos": apellidos(r.get("AUTOR"), r.get("COORDINADOR")),
            "Enlace": ls[0] if ls else None, "_links": ls, "_fila": r,
        }
        t = sin_tildes(tipo).lower()
        if re.search(sin_tildes(TIPOS_DOC), t):
            docs.append(base)
        elif re.search(TIPOS_PROYECTO, t):
            proys.append(base)
        else:
            otras.append(base)
    return docs, proys, otras


# ---------------- cruce ----------------
class Base:
    def __init__(self, ruta):
        df = pd.read_csv(ruta, dtype=str)
        df.columns = [c.lstrip("﻿") for c in df.columns]
        for c in ("handle", "Título", "anio", "en_2011_2021"):
            if c not in df.columns:
                sys.exit(f"Al CSV le falta la columna '{c}'. ¿Corriste filtro_dewey.py --sin-anios?")
        df["_h"] = df["handle"].fillna("").str.extract(r"(unal/\d+)")[0]
        df["_anio"] = pd.to_numeric(df["anio"], errors="coerce")
        df["_orig"] = df["en_2011_2021"].astype(str).str.lower().isin(["true", "1", "verdadero"])
        df["_ape"] = [apellidos(a, d) for a, d in zip(df.get("Autor"), df.get("Direct", pd.Series([None] * len(df))))]
        self.df = df.reset_index(drop=True)
        self.por_handle = {h: i for i, h in enumerate(self.df["_h"]) if isinstance(h, str)}
        # claves de título: completo y principal
        self.claves, self.idx = [], []
        self.exacto = {}
        for i, t in enumerate(self.df["Título"]):
            for k in {norm_titulo(t), titulo_principal(t)}:
                if len(k) >= 8 and (k == norm_titulo(t) or len(k) >= MIN_LARGO_CORTO):
                    self.claves.append(k)
                    self.idx.append(i)
            k = norm_titulo(t)
            if k:
                self.exacto.setdefault(k, []).append(i)
        print(f"Nuestra base: {len(self.df)} documentos ({int(self.df['_orig'].sum())} en 2011-2021)")

    def estado(self, i):
        return "Ya la tenemos" if self.df.at[i, "_orig"] else "Entra al quitar años"

    def confirma(self, reg, i):
        a1, a2 = reg["Año"], self.df.at[i, "_anio"]
        anio_ok = a1 is not None and pd.notna(a2) and abs(a1 - a2) <= 1
        autor_ok = bool(reg["_apellidos"] & self.df.at[i, "_ape"])
        return anio_ok or autor_ok, anio_ok, autor_ok

    def buscar(self, reg, api):
        # 1) link
        nota = ""
        for l in reg["_links"]:
            h = handle_de(l) or api.handle(l)
            if h:
                if h in self.por_handle:
                    i = self.por_handle[h]
                    return self.estado(i), "Link al repositorio", 100, i, ""
                nota = (f"El link apunta al repositorio ({h}) pero no está en nuestra base: "
                        "el filtro Dewey lo descartó o no es texto")
                break
            if re.search(r"repositorio\.unal\.edu\.co/items/|unal\.edu\.co/server/api/core/bitstreams/", l):
                nota = "Link al repositorio que no se pudo resolver (sin API o falló); se buscó por título"
        # 2) título exacto
        k = norm_titulo(reg["Título"])
        if k in self.exacto:
            cands = self.exacto[k]
            confirmados = [i for i in cands if self.confirma(reg, i)[0]]
            i = (confirmados or cands)[0]
            if len(k) >= MIN_LARGO_CORTO or confirmados:
                return self.estado(i), "Título exacto", 100, i, nota
            return "Dudoso", "Título exacto pero corto, sin año ni autor que coincidan", 100, i, nota
        # 3) título parecido
        mejores = []
        for q in {k, titulo_principal(reg["Título"])}:
            if len(q) < 8 or (q != k and len(q) < MIN_LARGO_CORTO):
                continue
            for _, score, pos in process.extract(q, self.claves, scorer=fuzz.token_sort_ratio,
                                                 limit=5, score_cutoff=UMBRAL_BUSQUEDA):
                mejores.append((score, self.idx[pos]))
        if not mejores:
            return "No está", "", None, None, nota
        mejores.sort(key=lambda x: (-x[0], not self.confirma(reg, x[1])[0]))

        def sim_completa(i):
            return round(fuzz.token_sort_ratio(k, norm_titulo(self.df.at[i, "Título"])))
        # preferir el mejor puntaje que además confirme
        for score, i in mejores:
            ok, anio_ok, autor_ok = self.confirma(reg, i)
            if score >= UMBRAL_SEGURO and ok:
                por = " y ".join([x for x, b in (("año", anio_ok), ("autor", autor_ok)) if b])
                return self.estado(i), f"Título parecido (coincide {por})", sim_completa(i), i, nota
        # dudoso solo si el título COMPLETO se parece de verdad (o se parece algo y coincide el autor)
        for score, i in mejores:
            sim = sim_completa(i)
            autor_ok = self.confirma(reg, i)[2]
            if sim >= UMBRAL_DUDOSO or (autor_ok and sim >= UMBRAL_DUDOSO_AUTOR):
                return "Dudoso", "Título parecido, revisar", sim, i, nota
        return "No está", "", None, None, nota


# ---------------- Excel ----------------
FONT = "Calibri"
thin = Side(style="thin", color="BFBFBF")
H_FONT = Font(name=FONT, bold=True, color="FFFFFF")
BODY = Font(name=FONT, size=10)
LINK = Font(name=FONT, size=10, color="0563C1", underline="single")
WRAP = Alignment(vertical="top", wrap_text=True)
CENTER = Alignment(vertical="top", horizontal="center", wrap_text=True)


def hoja_tabla(ws, cols, filas, color, links_cols=(), centrar=(), alto=45):
    for j, (h, w) in enumerate(cols, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = H_FONT
        c.fill = PatternFill("solid", fgColor=color)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[1].height = 32
    for i, fila in enumerate(filas, 2):
        for j, v in enumerate(fila, 1):
            v = limpio(v) if not isinstance(v, (int, float)) or isinstance(v, bool) else v
            c = ws.cell(row=i, column=j, value=v)
            c.font = BODY
            c.alignment = CENTER if j in centrar else WRAP
            if j in links_cols and isinstance(v, str) and v.startswith("http"):
                c.hyperlink = v
                c.font = LINK
        ws.row_dimensions[i].height = alto
    ws.freeze_panes = "B2"


def armar_excel(cruce, proys, otras, base, conteos):
    wb = Workbook()
    res = wb.active
    res.title = "Resumen"
    ws = wb.create_sheet("Cruce")
    wp = wb.create_sheet("Proyectos (Hermes)")
    wo = wb.create_sheet("Otras actividades")
    wc = wb.create_sheet("Cómo se cruzó")

    # --- Cruce ---
    cols = [("Estado", 16), ("¿Es el mismo? (solo dudosos)", 13), ("Cómo se encontró", 22), ("Similitud", 9),
            ("Base de Natalia", 11), ("ID / fila", 10), ("Tipo (Natalia)", 18), ("Título (Natalia)", 45),
            ("Año (Natalia)", 8), ("Autor (Natalia)", 24), ("Enlace (Natalia)", 30), ("Fuente del enlace", 15),
            ("Nota", 30), ("Título en nuestra base", 45), ("Año (nuestra)", 8), ("Autor (nuestra)", 24),
            ("Tipo (nuestra)", 18), ("Link repositorio", 30)]
    filas = []
    for c in cruce:
        i = c["_i"]
        d = base.df.iloc[i] if i is not None else None
        filas.append([
            c["Estado"], None, c["Método"], c["Similitud"], c["Base"], c["ID"], c["Tipo"], c["Título"],
            c["Año"], c["Autor"], c["Enlace"], fuente(c["_links"]), c["Nota"],
            d["Título"] if d is not None else None,
            int(d["_anio"]) if d is not None and pd.notna(d["_anio"]) else None,
            d.get("Autor") if d is not None else None,
            d.get("Tipo") if d is not None else None,
            d["handle"] if d is not None else None,
        ])
    hoja_tabla(ws, cols, filas, "1F4E79", links_cols=(11, 18), centrar=(1, 2, 4, 5, 6, 9, 15))
    n = len(filas) + 1
    for est, col in COLOR_ESTADO.items():
        ws.conditional_formatting.add(f"A2:A{n}", FormulaRule(formula=[f'$A2="{est}"'],
                                                              fill=PatternFill("solid", fgColor=col)))
    dv = DataValidation(type="list", formula1='"Sí,No"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"B2:B{n}")
    ws.freeze_panes = "I2"

    # --- Proyectos ---
    colsp = [("Fila en su Excel", 10), ("Código (ID - CODIGO)", 12), ("Id Hermes (del link)", 12),
             ("Tipo de aporte", 18), ("Título", 50), ("Año", 8), ("Coordinador", 24), ("Facultad", 22),
             ("Categoría", 18), ("Eje temático", 24), ("Objetivo", 50), ("Resumen", 50),
             ("Productos (lo que anotó ella)", 40), ("Enlaces", 35), ("Producto en nuestra base", 40)]
    filasp = []
    for p in proys:
        r = p["_fila"]
        idh = None
        for l in p["_links"]:
            m = re.search(r"idProyecto=(\d+)", l)
            if m:
                idh = m.group(1)
                break
        filasp.append([p["ID"], limpio(r.get("ID - CODIGO")), idh, p["Tipo"], p["Título"], p["Año"],
                       limpio(r.get("COORDINADOR")), limpio(r.get("FACULTAD")), limpio(r.get("CATEGORÍA")),
                       limpio(r.get("EJE TEMÁTICO")), limpio(r.get("OBJETIVO")), limpio(r.get("RESUMEN")),
                       limpio(r.get("PRODUCTOS")), "\n".join(p["_links"]) or None, p.get("_en_base")])
    hoja_tabla(wp, colsp, filasp, "7C2D12", centrar=(1, 2, 3, 6))

    # --- Otras actividades ---
    colso = [("Fila en su Excel", 10), ("Tipo de aporte", 20), ("Título", 50), ("Año", 8), ("Dependencia", 24),
             ("Facultad", 22), ("Categoría", 18), ("Eje temático", 24), ("Objetivo", 50), ("Resumen", 50),
             ("Enlaces", 35)]
    filaso = []
    for o in sorted(otras, key=lambda x: (x["Tipo"].lower(), x["Título"] or "")):
        r = o["_fila"]
        filaso.append([o["ID"], o["Tipo"], o["Título"], o["Año"], limpio(r.get("DEPENDENCIA")),
                       limpio(r.get("FACULTAD")), limpio(r.get("CATEGORÍA")), limpio(r.get("EJE TEMÁTICO")),
                       limpio(r.get("OBJETIVO")), limpio(r.get("RESUMEN")), "\n".join(o["_links"]) or None])
    hoja_tabla(wo, colso, filaso, "4B5563", centrar=(1, 4))

    # --- Resumen ---
    for col, w in {"A": 2, "B": 44, "C": 12, "D": 12, "E": 12, "F": 3, "G": 60}.items():
        res.column_dimensions[col].width = w
    res["B1"] = "Cruce de las bases de Natalia con nuestra base del repositorio"
    res["B1"].font = Font(name=FONT, size=12, bold=True)
    def miles(n):
        return f"{n:,}".replace(",", ".")
    res["B2"] = (f"Nuestra base: {miles(len(base.df))} documentos del repositorio filtrados por Dewey, sin filtro de años "
                 f"({miles(int(base.df['_orig'].sum()))} de ellos en 2011–2021)")
    res["B2"].font = Font(name=FONT, size=11)

    fila = 4
    for j, h in enumerate(["Documentos cruzados", "Legado", "Base final", "Total"], 2):
        c = res.cell(row=fila, column=j, value=h)
        c.font = H_FONT
        c.fill = PatternFill("solid", fgColor="1F4E79")
        c.alignment = Alignment(horizontal="center")
    for k, est in enumerate(ORDEN_ESTADO, 1):
        f = fila + k
        a = conteos.get(("Legado", est), 0)
        b = conteos.get(("Base final", est), 0)
        for j, v in enumerate([est, a, b, a + b], 2):
            c = res.cell(row=f, column=j, value=v)
            c.font = Font(name=FONT, size=11)
            c.border = Border(bottom=thin)
        res.cell(row=f, column=2).fill = PatternFill("solid", fgColor=COLOR_ESTADO[est])
    f = fila + len(ORDEN_ESTADO) + 1
    tl = sum(v for (b_, _), v in conteos.items() if b_ == "Legado")
    tf = sum(v for (b_, _), v in conteos.items() if b_ == "Base final")
    for j, v in enumerate(["Total", tl, tf, tl + tf], 2):
        c = res.cell(row=f, column=j, value=v)
        c.font = Font(name=FONT, size=11, bold=True)
    notas_estado = {
        "Dudoso": "Se parece a uno de nuestra base pero no hay certeza: revisar y marcar Sí/No en la hoja Cruce",
        "No está": "No aparece en nuestra base: candidato a sumar (ver Fuente del enlace)",
        "Entra al quitar años": "Está en el repositorio fuera de 2011–2021: entra si se amplían los años",
        "Ya la tenemos": "Ya está en la base actual (2011–2021)",
    }
    for k, est in enumerate(ORDEN_ESTADO, 1):
        res.cell(row=fila + k, column=7, value=notas_estado[est]).font = Font(name=FONT, size=11)

    f += 2
    res.cell(row=f, column=2, value="No está, según de dónde viene el enlace").font = Font(name=FONT, size=12, bold=True)
    no = [c for c in cruce if c["Estado"] == "No está"]
    fuentes = pd.Series([fuente(c["_links"]) for c in no]).value_counts() if no else pd.Series(dtype=int)
    for k, (fu, v) in enumerate(fuentes.items(), 1):
        res.cell(row=f + k, column=2, value=fu).font = Font(name=FONT, size=11)
        res.cell(row=f + k, column=3, value=int(v)).font = Font(name=FONT, size=11)
    f += len(fuentes) + 2

    # --- cuánto crece nuestra base al quitar el filtro de años ---
    res.cell(row=f, column=2, value="Nuestra base al quitar el filtro de años").font = Font(name=FONT, size=12, bold=True)
    for j, h in enumerate(["Período", "Documentos"], 2):
        c = res.cell(row=f + 1, column=j, value=h)
        c.font = H_FONT
        c.fill = PatternFill("solid", fgColor="1F4E79")
    def periodo(a):
        if pd.isna(a):
            return "Sin año"
        a = int(a)
        return ("Antes de 1990" if a < 1990 else "1990–1999" if a < 2000 else "2000–2010" if a < 2011
                else "2011–2021 (base actual)" if a <= 2021 else "2022 en adelante")
    orden = ["Antes de 1990", "1990–1999", "2000–2010", "2011–2021 (base actual)", "2022 en adelante", "Sin año"]
    per = base.df["_anio"].map(periodo).value_counts().reindex(orden, fill_value=0)
    for k, (lab, v) in enumerate(per.items(), 2):
        res.cell(row=f + k, column=2, value=lab).font = Font(name=FONT, size=11)
        res.cell(row=f + k, column=3, value=int(v)).font = Font(name=FONT, size=11)
    k = len(per) + 2
    res.cell(row=f + k, column=2, value="Total sin filtro de años").font = Font(name=FONT, size=11, bold=True)
    res.cell(row=f + k, column=3, value=len(base.df)).font = Font(name=FONT, size=11, bold=True)
    res.cell(row=f + k + 1, column=2, value="Documentos nuevos al quitar los años").font = Font(name=FONT, size=11, bold=True)
    res.cell(row=f + k + 1, column=3, value=int((~base.df["_orig"]).sum())).font = Font(name=FONT, size=11, bold=True)
    f += k + 3

    res.cell(row=f, column=2, value="Base final: filas que no son documentos").font = Font(name=FONT, size=12, bold=True)
    res.cell(row=f + 1, column=2, value="Proyectos (hoja Proyectos (Hermes))").font = Font(name=FONT, size=11)
    res.cell(row=f + 1, column=3, value=len(proys)).font = Font(name=FONT, size=11)
    res.cell(row=f + 2, column=2, value="Otras actividades (asignaturas, convocatorias, eventos…)").font = Font(name=FONT, size=11)
    res.cell(row=f + 2, column=3, value=len(otras)).font = Font(name=FONT, size=11)
    res.cell(row=f + 1, column=7, value="No se cruzan: un proyecto no es un documento. Sirven para buscar sus productos en Hermes").font = Font(name=FONT, size=11)
    res.cell(row=f + 2, column=7, value="No tienen documento asociado; queda por definir qué hacer con ellas").font = Font(name=FONT, size=11)

    # --- Cómo se cruzó ---
    wc.column_dimensions["A"].width = 2
    wc.column_dimensions["B"].width = 5
    wc.column_dimensions["C"].width = 110
    wc["B1"] = "Cómo se cruzó"
    wc["B1"].font = Font(name=FONT, size=12, bold=True)
    pasos = [
        "Nuestra base: los documentos del repositorio que pasan el filtro por área temática (Dewey), ahora sin filtro de años.",
        "De la Base final se cruzaron solo las filas que son documentos (libros, artículos, tesis, capítulos, informes, ponencias…). "
        "Los proyectos van a su propia hoja y las demás actividades (asignaturas, convocatorias, cátedras, eventos…) a otra.",
        "De la Base Legado se cruzaron todas las filas.",
        "Paso 1, por enlace: si el enlace lleva al repositorio de la UNAL, se identifica el documento exacto y se busca en nuestra base.",
        "Paso 2, por título exacto: se comparan los títulos sin tildes, mayúsculas ni signos.",
        f"Paso 3, por título parecido: si la similitud es de {UMBRAL_SEGURO}% o más y además coincide el año (±1) o el apellido de un autor, "
        f"se toma como el mismo documento. Si la similitud está entre {UMBRAL_DUDOSO}% y {UMBRAL_SEGURO}%, o es alta pero no coincide ni año ni autor, "
        "queda como Dudoso.",
        "Los Dudosos se revisan a mano: comparar el título de Natalia con el de nuestra base y marcar Sí o No en la columna ¿Es el mismo?.",
        "La hoja Cruce está ordenada: primero Dudosos, luego No está, luego Entra al quitar años y al final Ya la tenemos.",
    ]
    for k, t in enumerate(pasos):
        r = 3 + k
        wc.cell(row=r, column=2, value=k + 1).font = Font(name=FONT, bold=True)
        wc.cell(row=r, column=2).alignment = Alignment(horizontal="center", vertical="top")
        c = wc.cell(row=r, column=3, value=t)
        c.font = Font(name=FONT, size=11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        wc.row_dimensions[r].height = 32 if len(t) > 110 else 18

    wb.save(SALIDA)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 3:
        sys.exit("Uso: python cruce_natalia.py candidatos_todos_anios.csv <Base_final.xlsx> <Base_Legado.xlsx> [--sin-api]")
    usar_api = "--sin-api" not in sys.argv
    base = Base(args[0])
    final, legado = leer_bases(args[1:3])
    docs_f, proys, otras = registros_final(final)
    regs = registros_legado(legado) + docs_f
    api = Api(usar_api)
    print(f"Base final: {len(final)} filas -> {len(docs_f)} documentos, {len(proys)} proyectos, {len(otras)} otras")
    print(f"Legado: {len(legado)} filas")

    cruce, conteos = [], {}
    for n, reg in enumerate(regs, 1):
        est, met, sim, i, nota = base.buscar(reg, api)
        reg.update({"Estado": est, "Método": met, "Similitud": sim, "_i": i, "Nota": nota})
        cruce.append(reg)
        conteos[(reg["Base"], est)] = conteos.get((reg["Base"], est), 0) + 1
        if n % 50 == 0:
            print(f"  {n}/{len(regs)}")

    # proyectos: ¿algún link suyo lleva a un documento de nuestra base?
    for p in proys:
        for l in p["_links"]:
            h = handle_de(l) or api.handle(l)
            if h and h in base.por_handle:
                d = base.df.iloc[base.por_handle[h]]
                p["_en_base"] = f"{d['Título']} ({d['handle']})"
                break

    cruce.sort(key=lambda c: (ORDEN_ESTADO[c["Estado"]], c["Base"] != "Legado", -(c["Similitud"] or 0)))
    armar_excel(cruce, proys, otras, base, conteos)

    print("\nResultado:")
    for est in ORDEN_ESTADO:
        a, b = conteos.get(("Legado", est), 0), conteos.get(("Base final", est), 0)
        print(f"  {est:22} Legado {a:4}   Base final {b:4}   Total {a + b:4}")
    print(f"\nListo: {SALIDA}")


if __name__ == "__main__":
    main()