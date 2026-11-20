import sys
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

"""
Arma el Excel de revisión para Natalia y Daniela a partir de la salida de clasificar_ia.py.

Uso:  python armar_excel_revision.py total_g31.xlsx Revision_clasificacion_IA.xlsx

Hojas: Resumen (datos), Cómo leer, 2011-2021, Otros años (INCLUIR, POSIBLE, EXCLUIR) y REVISAR.
"""
SRC = sys.argv[1]
OUT = sys.argv[2]

d = pd.read_excel(SRC, sheet_name="Resultados")
d.columns = ["id", "tit", "dec", "sinred", "dim", "ejes", "cp", "tec", "col", "tema", "mot", "ev", "nA", "ban",
             "prio", "link", "res"]


def fix(s):
    if isinstance(s, str) and "Ã" in s:
        try:
            return s.encode("latin1").decode("utf8")
        except Exception:
            return s
    return s


for c in ["tit", "res", "ev", "mot", "tema"]:
    d[c] = d[c].map(fix)

d["periodo"] = d.prio.map({"Sí": "2011-2021", "No": "Otros años"})
d["ip"] = d.dec.isin(["INCLUIR", "POSIBLE"])

F = "Arial"
f_norm = Font(name=F, size=10)
f_bold = Font(name=F, size=10, bold=True)
f_title = Font(name=F, size=14, bold=True)
f_sec = Font(name=F, size=11, bold=True)
f_note = Font(name=F, size=10)
thin = Side(style="thin", color="000000")
b_bottom = Border(bottom=thin)
wrap_top = Alignment(wrap_text=True, vertical="top")

wb = Workbook()

# ------------------------------------------------------------------ Hojas de datos
COLS = [
    ("N.º", 6), ("Título", 45), ("Decisión IA", 12), ("Dimensión agraria", 13),
    ("Ejes", 38), ("Conflicto/paz", 11), ("Técnico agronómico", 12), ("Colombia", 11),
    ("Motivo IA", 50), ("Evidencia", 50), ("Decisión revisión", 14),
    ("Comentarios / motivo del cambio", 35), ("Link", 38), ("Resumen", 90),
]
col_map = {"si": "Sí", "no": "No", "no_claro": "No claro", "comparado": "Comparado"}
orden_dec = {"INCLUIR": 0, "POSIBLE": 1, "EXCLUIR": 2}
orden_dim = {"central": 0, "secundaria": 1, "contexto": 2, "ninguna": 3}


def hoja(nombre, periodo):
    ws = wb.create_sheet(nombre)
    x = d[(d.periodo == periodo) & d.dec.isin(["INCLUIR", "POSIBLE", "EXCLUIR"])].copy()
    x["o1"] = x.dec.map(orden_dec)
    x["o2"] = x.dim.map(orden_dim).fillna(9)
    x = x.sort_values(["o1", "o2", "tit"])
    for j, (h, w) in enumerate(COLS, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = f_bold
        c.border = b_bottom
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[c.column_letter].width = w
    ws.row_dimensions[1].height = 30
    n = 0
    for _, r in x.iterrows():
        n += 1
        rev = r.dec == "REVISAR"
        vals = [
            n, r.tit, r.dec,
            None if rev else r.dim,
            None if rev else r.ejes,
            None if rev else r.cp,
            None if rev else r.tec,
            None if rev else col_map.get(r.col, r.col),
            "Sin resumen o con resumen muy corto (menos de 100 caracteres): la IA no lo clasificó. Revisar con el título."
            if rev else r.mot,
            None if rev else r.ev,
            None, None, r.id,
            None if pd.isna(r.res) else r.res,
        ]
        for j, v in enumerate(vals, 1):
            if isinstance(v, float) and pd.isna(v):
                v = None
            c = ws.cell(row=n + 1, column=j, value=v)
            c.font = f_norm
            c.alignment = wrap_top
        link = ws.cell(row=n + 1, column=13)
        if link.value:
            link.hyperlink = link.value
            link.font = f_norm
        ws.row_dimensions[n + 1].height = 78
    ws.freeze_panes = "C2"
    dv = DataValidation(type="list", formula1='"INCLUIR,POSIBLE,EXCLUIR"', allow_blank=True)
    dv.add(f"K2:K{n + 1}")
    ws.add_data_validation(dv)
    return n


n1 = hoja("2011-2021", "2011-2021")
n2 = hoja("Otros años", "Otros años")


def hoja_revisar():
    ws = wb.create_sheet("REVISAR")
    cols = [("N.º", 6), ("Título", 60), ("Período", 13), ("Motivo", 38), ("Decisión revisión", 14),
            ("Comentarios / motivo del cambio", 35), ("Link", 38), ("Resumen", 60)]
    for j, (h, w) in enumerate(cols, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = f_bold
        c.border = b_bottom
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[c.column_letter].width = w
    ws.row_dimensions[1].height = 30
    x = d[d.dec == "REVISAR"].copy()
    x["o"] = x.periodo.map({"2011-2021": 0, "Otros años": 1})
    x = x.sort_values(["o", "tit"])
    n = 0
    for _, r in x.iterrows():
        n += 1
        motivo = "Sin resumen" if pd.isna(r.res) else "Resumen de menos de 100 caracteres"
        vals = [n, r.tit, r.periodo, motivo, None, None, r.id, None if pd.isna(r.res) else r.res]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=n + 1, column=j, value=v)
            c.font = f_norm
            c.alignment = wrap_top
        link = ws.cell(row=n + 1, column=7)
        link.hyperlink = link.value
        link.font = f_norm
        ws.row_dimensions[n + 1].height = 45
    ws.freeze_panes = "C2"
    dv = DataValidation(type="list", formula1='"INCLUIR,POSIBLE,EXCLUIR"', allow_blank=True)
    dv.add(f"E2:E{n + 1}")
    ws.add_data_validation(dv)
    return n


n3 = hoja_revisar()

# ------------------------------------------------------------------ Resumen
rs = wb.active
rs.title = "Resumen"
rs.column_dimensions["A"].width = 58
for L in "BCDEFGH":
    rs.column_dimensions[L].width = 15

row = 1


def put(r, c, v, font=f_norm, fmt=None, border=None, align=None):
    cell = rs.cell(row=r, column=c, value=v)
    cell.font = font
    if fmt:
        cell.number_format = fmt
    if border:
        cell.border = border
    if align:
        cell.alignment = align
    return cell


def header(r, labels):
    for j, h in enumerate(labels, 1):
        put(r, j, h, f_bold, border=b_bottom, align=Alignment(wrap_text=True, horizontal="left" if j == 1 else "center"))


def count(mask):
    return int(mask.sum())


P = ["2011-2021", "Otros años"]

put(1, 1, "Resumen de la clasificación con IA", f_title)
put(2, 1, "Corpus candidato: 16.132 documentos del repositorio institucional (filtro por clasificación Dewey, sin filtro de años). "
          "La IA leyó el título y el resumen de cada documento. Las hojas 2011-2021 y Otros años traen los documentos clasificados "
          "(INCLUIR, POSIBLE y EXCLUIR); los que no tienen resumen están en la hoja REVISAR.", f_note,
    align=Alignment(wrap_text=True, vertical="top"))
rs.merge_cells("A2:H2")
rs.row_dimensions[2].height = 42

# 1. Totales
r = 4
put(r, 1, "1. ¿Cuántos documentos quedaron en cada grupo?", f_sec)
r += 1
header(r, ["Grupo", "INCLUIR", "POSIBLE", "EXCLUIR", "REVISAR", "Total", "INCLUIR + POSIBLE", "% INCLUIR + POSIBLE"])
rs.row_dimensions[r].height = 30
r_all = r + 1
r_p1 = r + 2
r_p2 = r + 3
for rr, lab, per in [(r_p1, "2011-2021", "2011-2021"), (r_p2, "Otros años", "Otros años")]:
    put(rr, 1, lab)
    for j, dec in enumerate(["INCLUIR", "POSIBLE", "EXCLUIR", "REVISAR"], 2):
        put(rr, j, count((d.periodo == per) & (d.dec == dec)), fmt="#,##0")
put(r_all, 1, "Todos los años", f_bold)
for j in range(2, 6):
    L = rs.cell(row=1, column=j).column_letter
    put(r_all, j, f"={L}{r_p1}+{L}{r_p2}", f_bold, "#,##0")
for rr in (r_all, r_p1, r_p2):
    fb = f_bold if rr == r_all else f_norm
    put(rr, 6, f"=SUM(B{rr}:E{rr})", fb, "#,##0")
    put(rr, 7, f"=B{rr}+C{rr}", fb, "#,##0")
    put(rr, 8, f"=G{rr}/F{rr}", fb, "0.0%")
r = r_p2

# 2. REVISAR
r += 2
put(r, 1, "2. Documentos en REVISAR (la IA no los clasificó)", f_sec)
r += 1
header(r, ["Motivo", "2011-2021", "Otros años", "Total"])
rev = d[d.dec == "REVISAR"]
motivos = [
    ("Sin resumen (campo vacío)", rev.res.isna()),
    ("Resumen de menos de 100 caracteres", rev.res.notna()),
]
r0 = r + 1
for lab, m in motivos:
    r += 1
    put(r, 1, lab)
    put(r, 2, count(m & (rev.periodo == "2011-2021")), fmt="#,##0")
    put(r, 3, count(m & (rev.periodo == "Otros años")), fmt="#,##0")
    put(r, 4, f"=B{r}+C{r}", fmt="#,##0")
r += 1
put(r, 1, "Total REVISAR", f_bold)
for j, L in enumerate("BCD", 2):
    put(r, j, f"=SUM({L}{r0}:{L}{r - 1})", f_bold, "#,##0")
r += 1
put(r, 1, "Sin resumen la IA no puede decidir con seguridad, por eso van a revisión humana (se ven por el título).", f_note)

# 3. Dimensión agraria
r += 2
put(r, 1, "3. ¿Qué tan central es el tema agrario? (según la IA)", f_sec)
r += 1
header(r, ["Dimensión agraria", "INCLUIR 2011-2021", "POSIBLE 2011-2021", "INCLUIR otros años", "POSIBLE otros años", "Total"])
r_d0 = r + 1
rs.row_dimensions[r].height = 30
dims = [("central", "Central (es el tema principal)"), ("secundaria", "Secundaria (aparece, pero no es el foco)"),
        ("contexto", "Contexto (solo es el escenario)"), ("ninguna", "Ninguna")]
for k, lab in dims:
    r += 1
    put(r, 1, lab)
    for j, (dec, per) in enumerate([("INCLUIR", "2011-2021"), ("POSIBLE", "2011-2021"),
                                    ("INCLUIR", "Otros años"), ("POSIBLE", "Otros años")], 2):
        put(r, j, count((d.dec == dec) & (d.periodo == per) & (d.dim == k)), fmt="#,##0")
    put(r, 6, f"=SUM(B{r}:E{r})", fmt="#,##0")
r += 1
put(r, 1, "Total", f_bold)
for j in range(2, 7):
    L = rs.cell(row=1, column=j).column_letter
    put(r, j, f"=SUM({L}{r_d0}:{L}{r - 1})", f_bold, "#,##0")

# 4. Ejes
ip = d[d.ip].copy()
ip["ej"] = ip.ejes.fillna("").str.split("; ")
ee = ip.explode("ej")
ee = ee[ee.ej.fillna("") != ""]
r += 2
put(r, 1, "4. Ejes temáticos más frecuentes (INCLUIR y POSIBLE)", f_sec)
r += 1
header(r, ["Eje", "2011-2021", "Otros años", "Total"])
tab = ee.groupby(["ej", "periodo"]).size().unstack(fill_value=0)
for p in P:
    if p not in tab:
        tab[p] = 0
tab["t"] = tab[P].sum(axis=1)
for ej, rw in tab.sort_values("t", ascending=False).iterrows():
    r += 1
    put(r, 1, ej)
    put(r, 2, int(rw["2011-2021"]), fmt="#,##0")
    put(r, 3, int(rw["Otros años"]), fmt="#,##0")
    put(r, 4, f"=B{r}+C{r}", fmt="#,##0")
r += 1
put(r, 1, "Un documento puede tener varios ejes, por eso la suma supera el número de documentos.", f_note)

# 5-7. Colombia, conflicto, técnico
def tabla_cat(r, titulo, col, valores):
    put(r, 1, titulo, f_sec)
    r += 1
    header(r, ["Valor", "2011-2021", "Otros años", "Total"])
    for lab, val in valores:
        r += 1
        put(r, 1, lab)
        for j, p in enumerate(P, 2):
            put(r, j, count((ip.periodo == p) & (ip[col] == val)), fmt="#,##0")
        put(r, 4, f"=B{r}+C{r}", fmt="#,##0")
    return r


r += 2
r = tabla_cat(r, "5. ¿El documento trata de Colombia? (INCLUIR y POSIBLE)", "col",
              [("Sí", "si"), ("Comparado (Colombia y otros países)", "comparado"), ("No claro", "no_claro"), ("No", "no")])
r += 2
r = tabla_cat(r, "6. ¿Se relaciona con conflicto o paz? (INCLUIR y POSIBLE)", "cp", [("Sí", "Sí"), ("No", "No")])
r += 1
put(r, 1, "No es requisito: el tema es lo social alrededor de la tierra. Es solo un dato descriptivo.", f_note)
r += 2
r = tabla_cat(r, "7. ¿Es un trabajo técnico agronómico? (INCLUIR y POSIBLE)", "tec", [("Sí", "Sí"), ("No", "No")])
r += 1
put(r, 1, "Técnico agronómico = laboratorio o ensayos sobre cultivos, suelos o animales, sin análisis social.", f_note)

# Nota metodológica
r += 2
put(r, 1, "Cómo se hizo", f_sec)
for t in [
    "Modelo de IA local (gemma4:31b-it-qat), una sola lectura por documento, con los criterios y el prompt dados.",
    "La IA leyó solo título y resumen por tiempo: clasificar los 16.132 documentos tomó unas 11 horas y media; leerlos completos tomaría semanas.",
    "Los documentos de 2011-2021 y de otros años se clasificaron igual; la separación es solo para organizar la revisión.",
]:
    r += 1
    put(r, 1, t)

# ------------------------------------------------------------------ Cómo leer
cl = wb.create_sheet("Cómo leer", 1)
cl.column_dimensions["A"].width = 30
cl.column_dimensions["B"].width = 95
cl.column_dimensions["C"].width = 40
rr = 1


def cput(r, c, v, font=f_norm, border=None):
    cell = cl.cell(row=r, column=c, value=v)
    cell.font = font
    cell.alignment = wrap_top
    if border:
        cell.border = border
    return cell


cput(1, 1, "Cómo leer este archivo", f_title)
cput(2, 1, "Este archivo trae todos los documentos clasificados por la IA, en tres hojas: 2011-2021 y Otros años (mismas columnas) "
           "y REVISAR (los documentos sin resumen, que la IA no pudo clasificar).", f_norm)
cl.merge_cells("A2:C2")
cl.row_dimensions[2].height = 30

r = 4
cput(r, 1, "Las decisiones de la IA", f_sec)
r += 1
for j, h in enumerate(["Decisión", "Qué significa", ""], 1):
    cput(r, j, h, f_bold, b_bottom)
for a, b in [
    ("INCLUIR", "El tema social de la tierra (reforma agraria, campesinado, tenencia, desarrollo rural…) es el foco del documento."),
    ("POSIBLE", "El tema aparece, pero no es claro o no es el foco. Ante la duda, la IA marca POSIBLE y nunca EXCLUIR."),
    ("EXCLUIR", "No tiene que ver con el tema. Están al final de cada hoja, por si quieren revisarlos."),
    ("REVISAR", "No tiene resumen o es muy corto (menos de 100 caracteres), así que la IA no lo clasificó. Están en su propia hoja; se decide mirando el título o abriendo el documento."),
]:
    r += 1
    cput(r, 1, a, f_bold)
    cput(r, 2, b)
    cl.row_dimensions[r].height = 30

r += 2
cput(r, 1, "Las columnas", f_sec)
r += 1
for j, h in enumerate(["Columna", "Qué es", "Valores posibles"], 1):
    cput(r, j, h, f_bold, b_bottom)
cols_desc = [
    ("N.º", "Número de fila dentro de cada hoja.", ""),
    ("Título", "Título del documento en el repositorio.", ""),
    ("Decisión IA", "Lo que decidió la IA.", "INCLUIR, POSIBLE o EXCLUIR"),
    ("Dimensión agraria", "Qué tan central es el tema de la tierra y lo rural en el documento.",
     "Central (es el tema principal), Secundaria (aparece, pero no es el foco), Contexto (solo es el escenario), Ninguna"),
    ("Ejes", "Los temas del documento, según los ejes del proyecto. Puede tener más de uno, separados por punto y coma.", ""),
    ("Conflicto/paz", "Si el documento se relaciona con el conflicto armado o la paz. No es requisito para entrar.", "Sí o No"),
    ("Técnico agronómico", "Si es un trabajo técnico (laboratorio o ensayos sobre cultivos, suelos o animales) sin análisis social.", "Sí o No"),
    ("Colombia", "Si el documento trata de Colombia.", "Sí, No, No claro o Comparado (Colombia y otros países)"),
    ("Motivo IA", "La razón que dio la IA para su decisión, en una o dos frases.", ""),
    ("Evidencia", "Frases tomadas del resumen en las que se apoyó la IA. Sirven para verificar la decisión sin leer todo.", ""),
    ("Decisión revisión", "Para ustedes: su decisión final. Hay una lista desplegable.", "INCLUIR, POSIBLE o EXCLUIR"),
    ("Comentarios / motivo del cambio", "Para ustedes: cualquier comentario. Si cambian la decisión de la IA, anoten aquí por qué.", ""),
    ("Link", "Enlace al documento en el repositorio.", ""),
    ("Resumen", "Resumen del documento, tal como está en el repositorio. Haga clic en la celda para leerlo completo.", ""),
]
for a, b, c in cols_desc:
    r += 1
    cput(r, 1, a, f_bold)
    cput(r, 2, b)
    cput(r, 3, c)
    cl.row_dimensions[r].height = 30 if (len(b) > 90 or len(c) > 40) else 16

r += 2
cput(r, 1, "Cómo revisar", f_sec)
for t in [
    "Dentro de cada hoja el orden es: INCLUIR, POSIBLE y EXCLUIR. Dentro de cada grupo, primero los más cercanos al tema (dimensión Central, luego Secundaria, Contexto y Ninguna).",
    "La IA solo leyó título y resumen. Si la decisión no convence, se puede abrir el documento con el Link.",
    "Si están de acuerdo con la IA, basta dejar vacía la columna Decisión revisión; si no, escriban la suya.",
]:
    r += 1
    cput(r, 1, t)
    cl.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)

wb.save(OUT)
print("filas hoja 2011-2021:", n1, "| otros años:", n2, "| revisar:", n3)
