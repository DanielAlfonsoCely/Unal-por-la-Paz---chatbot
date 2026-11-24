"""
Excel de revisión manual de la ampliación (Memoria histórica/colectiva y Participación política) para Natalia y Daniela.
Se puede correr en cualquier momento, aunque la clasificación no haya terminado (sale con lo que haya).

Uso:  python armar_excel_ampliacion.py entrada_ampliacion.csv ampl_g31.jsonl
Salida: Revision_ampliacion_memoria_participacion.xlsx
Formato plano (sin filtros en encabezados, texto negro, Calibri), igual que el Excel de reforma agraria.
"""
import json, sys
from collections import Counter
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font

entrada, jsonl = sys.argv[1], sys.argv[2]
SALIDA = "Revision_ampliacion_memoria_participacion.xlsx"
df = pd.read_csv(entrada, dtype=str, encoding="utf-8-sig").fillna("").set_index("ID")
res = {}
for l in open(jsonl, encoding="utf-8"):
    if l.strip():
        r = json.loads(l); res[r["id"]] = r


def limpio(v):
    return ILLEGAL_CHARACTERS_RE.sub("", str(v)) if v is not None else ""


def categorias(r):
    out = []
    if r.get("dimension_memoria") in ("central", "secundaria"):
        out.append("Memoria histórica y colectiva")
    if r.get("dimension_participacion") in ("central", "secundaria"):
        out.append("Participación política")
    return "; ".join(out)


ORDEN = {"INCLUIR": 0, "POSIBLE": 1, "EXCLUIR": 2, "REVISAR": 3}
filas = []
for i, r in res.items():
    if i not in df.index:
        continue
    d = df.loc[i]
    filas.append({
        "dec": r["decision_final"], "grupo": d["Grupo"],
        "vals": [None, d["Fuente"], r["decision_final"], categorias(r), d["Título"], d["Autor"], d["Año"], d["Tipo"],
                 r.get("tema_central", ""), r.get("motivo", ""), "\n".join(r.get("evidencia") or []),
                 "", "", d["Link"], d["Resumen"][:32000]],
    })
filas.sort(key=lambda f: (ORDEN.get(f["dec"], 9), f["grupo"]))

COLS = [("N°", 7), ("Fuente", 22), ("Decisión IA", 12), ("Categoría(s)", 22), ("Título", 50), ("Autor", 25),
        ("Año", 7), ("Tipo", 16), ("Tema central (IA)", 40), ("Motivo IA", 45), ("Evidencia", 40),
        ("Decisión revisión", 14), ("Comentarios (motivo del cambio)", 30), ("Link", 30), ("Resumen", 80)]
F, FB = Font(name="Calibri", size=11), Font(name="Calibri", size=11, bold=True)
TOP = Alignment(vertical="top", wrap_text=True)

wb = Workbook()
wr = wb.active; wr.title = "Resumen"
wc = wb.create_sheet("Cómo leer")


def hoja(nombre, sub):
    ws = wb.create_sheet(nombre)
    for j, (h, w) in enumerate(COLS, 1):
        c = ws.cell(1, j, h); c.font = FB; c.alignment = TOP
        ws.column_dimensions[c.column_letter].width = w
    for n, f in enumerate(sub, 1):
        vals = list(f["vals"]); vals[0] = n
        for j, v in enumerate(vals, 1):
            c = ws.cell(n + 1, j, limpio(v) if j != 1 else v); c.font = F; c.alignment = TOP
    ws.freeze_panes = "F2"


hoja("Para revisar", [f for f in filas if f["dec"] in ("INCLUIR", "POSIBLE", "EXCLUIR")])
hoja("REVISAR (sin resumen)", [f for f in filas if f["dec"] == "REVISAR"])

# ---- Resumen ----
wr.column_dimensions["A"].width = 38; wr.column_dimensions["B"].width = 14
for k in "CDEF": wr.column_dimensions[k].width = 14
wr.append(["Ampliación del corpus: Memoria histórica/colectiva y Participación política (2011-2021)"])
wr.append([f"Documentos clasificados: {len(filas)} de {len(df)}"]); wr.append([])
decs = ["INCLUIR", "POSIBLE", "EXCLUIR", "REVISAR"]
wr.append(["Fuente"] + decs + ["Total"])
fuentes = Counter()
for f in filas:
    for fu in f["vals"][1].split("; "): fuentes[fu] += 1
for fu, _ in fuentes.most_common():
    cnt = Counter(f["dec"] for f in filas if fu in f["vals"][1].split("; "))
    wr.append([fu] + [cnt.get(k, 0) for k in decs] + [sum(cnt.values())])
cnt = Counter(f["dec"] for f in filas)
wr.append(["Total (sin repetir)"] + [cnt.get(k, 0) for k in decs] + [len(filas)])
wr.append([])
wr.append(["Categoría (INCLUIR y POSIBLE)", "Documentos"])
cat = Counter(c for f in filas if f["dec"] in ("INCLUIR", "POSIBLE") for c in f["vals"][3].split("; ") if c)
for c in ["Memoria histórica y colectiva", "Participación política"]:
    wr.append([c, cat.get(c, 0)])
wr.append(["Las dos", sum(1 for f in filas if f["dec"] in ("INCLUIR", "POSIBLE") and ";" in f["vals"][3])])
wr.append([])
wr.append(["Nota: un documento que está en varias fuentes aparece una sola vez; la columna Fuente las nombra todas,"])
wr.append(["por eso la suma por fuente puede ser mayor que el total."])
for row in wr.iter_rows():
    for c in row: c.font = FB if c.row in (1, 4) or c.column == 1 and c.value and str(c.value).startswith("Total") else F

# ---- Cómo leer ----
wc.column_dimensions["A"].width = 30; wc.column_dimensions["B"].width = 100
texto = [
    ("Qué es", "Documentos de 2011-2021 del repositorio UNAL y de las bases de Natalia (Base William Mancera, Base Legado "
               "de octubre y Base final 2010-2021), clasificados por la IA con las palabras clave del correo del 23-nov."),
    ("Decisión IA", "INCLUIR = el tema es central. POSIBLE = hay relación pero no es clara o es secundaria (ante la duda la "
                    "IA elige POSIBLE). EXCLUIR = sin relación. REVISAR = no tiene resumen suficiente; la IA no lo leyó."),
    ("Categoría(s)", "En cuál de las dos categorías cae según la IA. Puede ser una, las dos o ninguna."),
    ("Fuente", "De dónde viene el documento. Si está en varias, aparecen todas separadas por ';'."),
    ("Tema central / Motivo / Evidencia", "Lo que entendió la IA y por qué decidió así. La evidencia es texto copiado "
                                          "literal del título o del resumen."),
    ("Decisión revisión / Comentarios", "Para llenar en la revisión manual. En Comentarios, el motivo cuando se cambia la decisión de la IA."),
    ("Orden", "Primero INCLUIR, luego POSIBLE y luego EXCLUIR; dentro de cada una, primero las bases de Natalia y después el repositorio."),
]
for a, b in texto:
    wc.append([a, b])
for row in wc.iter_rows():
    for c in row: c.font = FB if c.column == 1 else F; c.alignment = TOP

wb.save(SALIDA)
print(f"Excel guardado: {SALIDA}  ({len(filas)} documentos; " + ", ".join(f"{k} {cnt.get(k, 0)}" for k in decs) + ")")
