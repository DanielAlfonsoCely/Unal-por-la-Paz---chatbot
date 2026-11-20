import pandas as pd

df = pd.read_pickle("reporte.pkl")

df["anio"] = pd.to_numeric(
    df["Fecha del documento"].astype(str).str.extract(r"^(\d{4})")[0], errors="coerce"
)
d = df[df["anio"].between(2011, 2021)].copy()
d["anio"] = d["anio"].astype(int)

dw = d["Dewey"].astype("string")
d["Dewey (1 dígito)"] = dw.str.extract(r"^\s*(\d)")[0]
d["Dewey (3 dígitos, 1er código)"] = dw.str.extract(r"^\s*(\d{3})")[0]

salida = []


def out(txt=""):
    print(txt)
    salida.append(str(txt))


def vacio(col):
    s = d[col].astype("string").str.strip()
    return s.fillna("") == ""


def tabla(col):
    s = d[col].astype("string").str.strip()
    s = s.replace("", pd.NA).fillna("(VACÍO)")
    t = s.value_counts().rename("cantidad").to_frame()
    t["%"] = (t["cantidad"] / len(d) * 100).round(2)
    return t.sort_index() if col == "anio" else t


orig = [c for c in df.columns if c != "anio"]
comp = pd.DataFrame({"vacíos": [int(vacio(c).sum()) for c in orig]}, index=orig)
comp["% vacío"] = (comp["vacíos"] / len(d) * 100).round(2)

cats = [
    "anio",
    "comm_3",
    "comm_2",
    "comm_1",
    "collection",
    "Tipo",
    "Modalidad",
    "Publisher",
    "Dewey (1 dígito)",
    "Dewey (3 dígitos, 1er código)",
    "Publisher program",
    "Línea de Investigación",
    "Grupo de Investigación",
    "Área curricular",
]
tablas = {c: tabla(c) for c in cats}

with pd.option_context("display.max_colwidth", None):
    out(f"TOTAL DE REGISTROS 2011-2021: {len(d)}")
    out()
    out()
    out("COMPLETITUD POR COLUMNA")
    out(comp.to_string())
    for c in cats:
        out()
        out()
        out(c)
        out(tablas[c].to_string())
        out(f"(suma = {tablas[c]['cantidad'].sum()} de {len(d)})")

with open("estadisticas_2011_2021.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(salida))

with pd.ExcelWriter("estadisticas_2011_2021.xlsx") as w:
    comp.to_excel(w, sheet_name="completitud")
    for c in cats:
        tablas[c].to_excel(w, sheet_name=c[:31])


import re

pares = {}
for celda in d["Dewey"].dropna():
    for parte in str(celda).split("::"):
        m = re.match(r"\s*(\d+)\s*-\s*(.+)", parte)
        if m:
            pares[m.group(1)] = m.group(2).strip()
for cod in sorted(pares):
    print(cod, pares[cod])
