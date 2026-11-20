"""
Arma la DB tentativa: los documentos INCLUIR de 2011-2021 con todas las columnas del reporte de
objetos (reordenadas y renombradas, ID = número del handle). Sin columnas de la IA.

Uso:  python armar_db.py candidatos_todos_anios.csv total_g31.xlsx DB_prototipo_INCLUIR_2011-2021.xlsx
"""
import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side

CSV, CLASIF, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
c = pd.read_csv(CSV, low_memory=False)
k = pd.read_excel(CLASIF, sheet_name="Resultados", usecols=["ID", "Decisión IA", "Prioridad (2011-2021)"])
ids = set(k[(k["Decisión IA"] == "INCLUIR") & (k["Prioridad (2011-2021)"] == "Sí")].ID)
orig = ['comm_3', 'comm_2', 'comm_1', 'collection', 'handle', 'Fecha de publicación', 'Fecha del documento',
        'Título', 'Autor', 'Tipo', 'Modalidad', 'Publisher', 'identifier_eprints', 'Dewey', 'Publisher program',
        'Línea de Investigación', 'Grupo de Investigación', 'Área curricular', 'Direct', 'subject', 'Abstract']
x = c[c.handle.isin(ids)][orig + ["anio"]].copy()
assert len(x) == len(ids), (len(x), len(ids))


def fix(s):
    if isinstance(s, str) and "Ã" in s:
        try:
            return s.encode("latin1").decode("utf8")
        except Exception:
            return s
    return s


for col in orig:
    if x[col].dtype == object:
        x[col] = x[col].map(fix)
x = x.sort_values(["anio", "Título"]).drop(columns="anio")

MAP = [("ID", None), ("Título", "Título"), ("Autor", "Autor"), ("Director", "Direct"), ("Año", "Fecha del documento"),
       ("Tipo", "Tipo"), ("Nivel", "Modalidad"),
       ("Categoría", "comm_3"), ("Sede", "comm_2"), ("Facultad", "comm_1"), ("Colección", "collection"),
       ("Programa", "Publisher program"), ("Institución", "Publisher"), ("Área curricular", "Área curricular"),
       ("Línea de investigación", "Línea de Investigación"), ("Grupo de investigación", "Grupo de Investigación"),
       ("Dewey", "Dewey"), ("Temas", "subject"),
       ("Link repositorio", "handle"), ("Link biblioteca digital (antiguo)", "identifier_eprints"),
       ("Fecha de publicación al repositorio", "Fecha de publicación"), ("Resumen", "Abstract")]
x["ID"] = x.handle.str.extract(r"/unal/(\d+)$")[0].astype(int)
assert x.ID.is_unique
x = x[[src if src else "ID" for _, src in MAP]]
x.columns = [n for n, _ in MAP]
orig = list(x.columns)
W = {"ID": 8, "Título": 50, "Autor": 30, "Director": 28, "Año": 7, "Tipo": 22, "Nivel": 13, "Categoría": 20, "Sede": 16,
     "Facultad": 28, "Colección": 30, "Programa": 32, "Institución": 28, "Área curricular": 22,
     "Línea de investigación": 25, "Grupo de investigación": 25, "Dewey": 32, "Temas": 35, "Link repositorio": 42,
     "Link biblioteca digital (antiguo)": 32, "Fecha de publicación al repositorio": 20, "Resumen": 90}
wb = Workbook()
ws = wb.active
ws.title = "Documentos"
fn, fb = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
al = Alignment(wrap_text=True, vertical="top")
for j, h in enumerate(orig, 1):
    cell = ws.cell(row=1, column=j, value=h)
    cell.font, cell.border = fb, Border(bottom=Side(style="thin"))
    cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.column_dimensions[cell.column_letter].width = W[h]
ws.row_dimensions[1].height = 30
hcol = orig.index("Link repositorio") + 1
for i, row in enumerate(x.itertuples(index=False), 2):
    for j, v in enumerate(row, 1):
        if isinstance(v, float) and pd.isna(v):
            v = None
        cell = ws.cell(row=i, column=j, value=v)
        cell.font, cell.alignment = fn, al
    h = ws.cell(row=i, column=hcol)
    if h.value:
        h.hyperlink = h.value
    ws.row_dimensions[i].height = 60
ws.freeze_panes = "C2"
wb.save(OUT)
print(len(x), "documentos |", x["Año"].astype(str).str[:4].value_counts().sort_index().to_dict())
