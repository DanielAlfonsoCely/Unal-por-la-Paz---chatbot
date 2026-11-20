import re, sys
from collections import Counter, defaultdict
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.formatting.rule import FormulaRule
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.data_source import AxDataSource, StrRef, NumDataSource, NumRef
from openpyxl.chart.label import DataLabelList
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

SRC = sys.argv[1]
OUT = sys.argv[2]
df = pd.read_csv(SRC, dtype=str)
df.columns = [c.lstrip('﻿') for c in df.columns]
N = len(df)

FONT = 'Arial'
AZUL = '1F4E79'
CLARO = 'DDEBF7'

def limpio(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    v = ILLEGAL_CHARACTERS_RE.sub('', str(v)).strip()
    return v or None

# ---------- Tipo: unificar etiquetas duplicadas ----------
TIPO_MAP = {'Trabajo de grado – Maestría': 'Trabajo de grado - Maestría',
            'Otros': 'Otro', 'otros': 'Otro',
            'Libro Completo': 'Libro completo'}
df['Tipo'] = df['Tipo'].replace(TIPO_MAP)

# ---------- Dewey: diccionario código -> tema ----------
def norm_code(c):
    c = c.strip()
    if len(c) == 1:
        return c + '00'
    if len(c) == 2:
        return c + '0'
    return c[:3]

names = defaultdict(Counter)
for txt in df['Dewey'].dropna():
    for seg in re.split(r'::| / ', txt):
        m = re.match(r'^\s*(\d{1,3})\s*(?:-\s*)?(.+?)\s*$', seg)
        if m and re.search(r'[A-Za-zÁÉÍÓÚáéíóúñ]', m.group(2)):
            nm = re.sub(r'\s+', ' ', m.group(2)).strip(' -;,')
            names[norm_code(m.group(1))][nm] += 1
DEWEY = {k: v.most_common(1)[0][0] for k, v in names.items()}
CENTENA_STD = {'000': 'Generalidades', '100': 'Filosofía y psicología', '200': 'Religión',
               '300': 'Ciencias sociales', '400': 'Lenguas', '500': 'Ciencias naturales y matemáticas',
               '600': 'Tecnología (ciencias aplicadas)', '700': 'Las artes', '800': 'Literatura',
               '900': 'Historia y geografía'}
EXTRA = {'114': 'Espacio', '122': 'Causalidad', '127': 'Lo inconsciente y lo subconsciente', '128': 'Humanidad',
         '649': 'Crianza de niños y cuidado de personas en el hogar', '898': 'Literaturas en lenguas indígenas de América del Sur',
         '904': 'Colecciones de relatos de eventos'}
CENTENA_STD.update(EXTRA)
for k, v in CENTENA_STD.items():
    DEWEY.setdefault(k, v)

def codigos(row):
    s = row
    if not isinstance(s, str) or not s.strip():
        return []
    out = []
    for c in s.split('|'):
        c = norm_code(c)
        if c not in out:
            out.append(c)
    return out

df['_codes'] = df['dewey_codigos'].apply(codigos)
faltan = sorted({c for cs in df['_codes'] for c in cs if c not in DEWEY})
print('códigos sin nombre:', faltan)

def etiqueta(c):
    return f'{c} – {DEWEY.get(c, "(sin nombre en el repositorio)")}'

df['_dewey_txt'] = df['_codes'].apply(lambda cs: '\n'.join(etiqueta(c) for c in cs) if cs else None)

# ---------- Libro ----------
wb = Workbook()
ws_res = wb.active
ws_res.title = 'Resumen'
ws_gra = wb.create_sheet('Gráficas')
ws_doc = wb.create_sheet('Documentos')
ws_como = wb.create_sheet('Cómo se filtró')
ws_dat = wb.create_sheet('Datos')
ws_dd = wb.create_sheet('DatosDewey')

thin = Side(style='thin', color='BFBFBF')
borde = Border(left=thin, right=thin, top=thin, bottom=thin)
H_FONT = Font(name=FONT, bold=True, color='FFFFFF')
H_FILL = PatternFill('solid', fgColor=AZUL)
SEL_FILL = PatternFill('solid', fgColor='FFF2CC')
C_RES, C_RES_CL = '0F766E', 'CCFBF1'   # Resumen: verde azulado
C_CON, C_CON_CL = '6D28D9', 'EDE9FE'   # Gráficas, conteo: violeta
C_DEW, C_DEW_CL = 'C2410C', 'FFEDD5'   # Gráficas, Dewey: naranja
C_DOC = '4D7C0F'                        # Documentos: verde oliva

# ================= Documentos =================
cols = [
    ('N°', 7), ('Título', 50), ('Autor', 28), ('Año', 8), ('Tipo', 22), ('Sede o comunidad', 18),
    ('Facultad o colección', 26), ('Programa', 30), ('Director', 26), ('Dewey (número – tema)', 38),
    ('Resumen', 80), ('Link', 16), ('Decisión', 13), ('Comentarios', 35),
]
for j, (h, w) in enumerate(cols, 1):
    c = ws_doc.cell(row=1, column=j, value=h)
    c.font = H_FONT; c.fill = PatternFill('solid', fgColor=C_DOC)
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws_doc.column_dimensions[get_column_letter(j)].width = w
ws_doc.row_dimensions[1].height = 30

df = df.sort_values(['anio', 'Título'], kind='stable').reset_index(drop=True)
body = Font(name=FONT, size=10)
link_font = Font(name=FONT, size=10, color='0563C1', underline='single')
top_wrap = Alignment(vertical='top', wrap_text=True)
top_center = Alignment(vertical='top', horizontal='center')

def lineas(v):
    v = limpio(v)
    return v.replace(' / ', '\n') if v else None

for i, r in df.iterrows():
    fila = i + 2
    anio = str(int(float(r['anio']))) if limpio(r['anio']) else None
    vals = [i + 1, limpio(r['Título']), lineas(r['Autor']), anio, limpio(r['Tipo']),
            limpio(r['comm_2']), limpio(r['comm_1']), limpio(r['collection']), lineas(r['Direct']),
            r['_dewey_txt'] or '(sin Dewey)', limpio(r['Abstract']), None, None, None]
    for j, v in enumerate(vals, 1):
        c = ws_doc.cell(row=fila, column=j, value=v)
        c.font = body
        c.alignment = top_center if j in (1, 4, 13) else top_wrap
    h = limpio(r['handle'])
    if h:
        c = ws_doc.cell(row=fila, column=12, value='Ver en repositorio')
        c.hyperlink = h
        c.font = link_font
    ws_doc.row_dimensions[fila].height = 90

last = N + 1
tab = Table(displayName='Documentos', ref=f'A1:{get_column_letter(len(cols))}{last}')
tab.tableStyleInfo = TableStyleInfo(name='TableStyleLight1', showRowStripes=True)
ws_doc.add_table(tab)
ws_doc.freeze_panes = 'C2'

dv = DataValidation(type='list', formula1='"INCLUIR,POSIBLE,EXCLUIR,REVISAR"', allow_blank=True)
dv.error = 'Elige una opción de la lista'; dv.errorTitle = 'Decisión'
ws_doc.add_data_validation(dv)
dv.add(f'M2:M{last}')
colores = {'INCLUIR': 'C6EFCE', 'POSIBLE': 'FFEB9C', 'EXCLUIR': 'FFC7CE', 'REVISAR': 'D9D9D9'}
for k, col in colores.items():
    ws_doc.conditional_formatting.add(f'M2:M{last}', FormulaRule(formula=[f'$M2="{k}"'], fill=PatternFill('solid', fgColor=col)))

# ================= Datos para gráficas =================
TOP = 15
def bloque(serie, ordenar_por_etiqueta=False, top=TOP):
    return _bloque(serie, ordenar_por_etiqueta, top)

def _bloque(serie, ordenar_por_etiqueta=False, top=TOP):
    s = serie.map(limpio)
    vacios = int(s.isna().sum())
    vc = s.dropna().value_counts()
    if ordenar_por_etiqueta:
        vc = vc.sort_index()
    items = list(vc.items())
    if len(items) > top:
        otros = sum(v for _, v in items[top:])
        items = items[:top] + [(f'Otros ({len(vc) - top} más)', otros)]
    if vacios:
        items.append(('(vacío)', vacios))
    return items

anio_txt = df['anio'].map(lambda x: str(int(float(x))) if limpio(x) else None)

# Por qué pasó el filtro (motivo agrupado)
def motivo(m):
    if m.startswith('rescatado'):
        return 'Rescatado por palabra clave'
    return {'pasa_3xx': '3xx – Ciencias sociales', 'dewey_vacio': 'Sin Dewey (pasa para revisión)',
            'si_630': '630–639 – Agricultura', 'pasa_9xx': '9xx – Historia y geografía',
            'pasa_7xx': '710–719 – Planificación y paisaje'}.get(m, 'Otros códigos aceptados (5xx/6xx)')

# Dewey por centena (documento cuenta en cada centena que tenga)
cent_cnt = Counter()
code_cnt = defaultdict(Counter)
for cs in df['_codes']:
    cents = {c[0] for c in cs}
    for ce in cents:
        cent_cnt[ce] += 1
    for c in cs:
        code_cnt[c[0]][c] += 1
cent_items = [(etiqueta(ce + '00'), n) for ce, n in sorted(cent_cnt.items())]
sin_dewey = int((df['_codes'].map(len) == 0).sum())
cent_items.append(('(sin Dewey)', sin_dewey))

def doble(serie, completa=False, **kw):
    graf = bloque(serie, **kw)
    tabla = bloque(serie, top=10**6, **kw) if completa else graf
    return tabla, graf

VARS = [
    ('Año',) + doble(anio_txt, ordenar_por_etiqueta=True),
    ('Tipo',) + doble(df['Tipo']),
    ('Dewey por centena', cent_items, cent_items),
    ('Sede o comunidad',) + doble(df['comm_2']),
    ('Facultad o colección',) + doble(df['comm_1'], completa=True),
    ('Programa',) + doble(df['collection']),
    ('Tipo de colección (comm_3)',) + doble(df['comm_3']),
    ('Modalidad',) + doble(df['Modalidad']),
    ('Área curricular',) + doble(df['Área curricular']),
]

def escribir(ws, k, nombre, tabla, graf, lista=None):
    ca = 5 * k + 1
    ws.cell(row=1, column=ca, value=nombre)
    for off, h in enumerate([' (n)', ' (g)', ' (gn)', ' (lista)'], 1):
        ws.cell(row=1, column=ca + off, value=nombre + h)
    for i, (lab, n) in enumerate(tabla):
        ws.cell(row=i + 2, column=ca, value=str(lab)); ws.cell(row=i + 2, column=ca + 1, value=int(n))
    for i, (lab, n) in enumerate(graf):
        ws.cell(row=i + 2, column=ca + 2, value=str(lab)); ws.cell(row=i + 2, column=ca + 3, value=int(n))
    for i, lab in enumerate(lista or []):
        ws.cell(row=i + 2, column=ca + 4, value=lab)

MAXA = max(len(t) for _, t, _ in VARS)
MAXGA = max(len(gg) for _, _, gg in VARS)
print('filas tabla A:', MAXA, 'filas gráfica A:', MAXGA)
for k, (nombre, tabla, graf) in enumerate(VARS):
    escribir(ws_dat, k, nombre, tabla, graf)
# lista de variables para el desplegable
LISTCOL = 5 * len(VARS) + 2
for i, (nombre, _, _) in enumerate(VARS):
    ws_dat.cell(row=i + 1, column=LISTCOL, value=nombre)
ws_dat.sheet_state = 'hidden'

TOPB = 20
MAXLISTA = 0
cent_labels = []
for k, ce in enumerate(sorted(code_cnt)):
    lab = etiqueta(ce + '00')
    cent_labels.append(lab)
    items = [(etiqueta(c), n) for c, n in code_cnt[ce].most_common()]
    if len(items) > TOPB:
        items = items[:TOPB] + [(f'Otros códigos ({len(items) - TOPB} más)', sum(n for _, n in items[TOPB:]))]
    lista = [etiqueta(c) for c in sorted(code_cnt[ce])]
    MAXLISTA = max(MAXLISTA, len(lista))
    escribir(ws_dd, k, lab, items, items, lista)
LISTB = 5 * len(cent_labels) + 2
for i, l in enumerate(cent_labels):
    ws_dd.cell(row=i + 1, column=LISTB, value=l)
ws_dd.sheet_state = 'hidden'

# ================= Gráficas =================
g = ws_gra
g.sheet_view.showGridLines = False
for col, w in {'A': 2, 'B': 52, 'C': 13, 'D': 11, 'E': 3}.items():
    g.column_dimensions[col].width = w
g['B1'] = 'Gráficas: elige qué ver en la celda amarilla'
g['B1'].font = Font(name=FONT, size=16, bold=True, color='374151')

def seccion(fila0, titulo, opciones_ref, por_defecto, hoja_datos, nfil, ngraf, nota, color, claro, nlista=0):
    g.cell(row=fila0, column=2, value=titulo).font = Font(name=FONT, size=12, bold=True, color=color)
    sel = g.cell(row=fila0 + 1, column=2, value=por_defecto)
    sel.fill = SEL_FILL; sel.font = Font(name=FONT, size=12, bold=True); sel.border = borde
    dvx = DataValidation(type='list', formula1=opciones_ref, allow_blank=False)
    g.add_data_validation(dvx); dvx.add(sel.coordinate)
    g.cell(row=fila0 + 1, column=3, value='◄ haz clic y elige').font = Font(name=FONT, italic=True, color='808080')
    g.cell(row=fila0 + 2, column=2, value=nota).font = Font(name=FONT, size=9, italic=True, color='808080')
    zc = f'$Z${fila0 + 1}'
    g.cell(row=fila0 + 1, column=26, value=f'=MATCH({sel.coordinate},{hoja_datos}!$1:$1,0)')
    hdr = fila0 + 3
    for j, h in enumerate(['Categoría', 'Documentos', '%'], 2):
        c = g.cell(row=hdr, column=j, value=h)
        c.font = H_FONT; c.fill = PatternFill('solid', fgColor=color); c.alignment = Alignment(horizontal='center')
    alto = max(nfil, nlista)
    rng = f'{hoja_datos}!$A$2:$ZZ${alto + 1}'
    def idx(i, off):
        x = f'INDEX({rng},{i + 1},{zc}+{off})'
        return f'IFERROR(IF({x}="","",{x}),"")'
    f1 = hdr + 1
    for i in range(nfil):
        rr = f1 + i
        g.cell(row=rr, column=2, value=f'={idx(i, 0)}')
        g.cell(row=rr, column=3, value=f'=IF(B{rr}="","",{idx(i, 1)})')
        g.cell(row=rr, column=4, value=f'=IF(B{rr}="","",C{rr}/Resumen!$C$9)')
        for j in (2, 3, 4):
            c = g.cell(row=rr, column=j); c.font = Font(name=FONT, size=10); c.border = borde
        g.cell(row=rr, column=3).number_format = '#,##0'
        g.cell(row=rr, column=4).number_format = '0.0%'
        g.cell(row=rr, column=2).alignment = Alignment(wrap_text=True, vertical='center')
    # banda de color suave alternada (fija, sin formato de tabla)
    g.conditional_formatting.add(f'B{f1}:D{f1 + nfil - 1}',
        FormulaRule(formula=[f'AND($B{f1}<>"",MOD(ROW(),2)=0)'], fill=PatternFill('solid', fgColor=claro)))
    fl = f1 + nfil - 1
    # columnas auxiliares para la gráfica (X etiqueta, Y valor)
    for i in range(ngraf):
        rr = f1 + i
        g.cell(row=rr, column=24, value=f'={idx(i, 2)}')
        g.cell(row=rr, column=25, value=f'=IF(X{rr}="",NA(),{idx(i, 3)})')
    ch = BarChart()
    ch.type = 'bar'; ch.style = 10; ch.legend = None; ch.title = None
    ch.height = 0.6 * ngraf + 1.5; ch.width = 22
    ch.gapWidth = 40
    ch.visible_cells_only = False
    ch.roundedCorners = False
    ch.add_data(Reference(g, min_col=25, min_row=f1, max_row=f1 + ngraf - 1), titles_from_data=False)
    ch.set_categories(Reference(g, min_col=24, min_row=f1, max_row=f1 + ngraf - 1))
    sr = ch.series[0]
    sr.graphicalProperties.solidFill = color
    sr.graphicalProperties.line.solidFill = color
    sr.dLbls = DataLabelList(); sr.dLbls.showVal = True
    for a_ in ('showSerName', 'showCatName', 'showLegendKey', 'showPercent'):
        setattr(sr.dLbls, a_, False)
    ch.x_axis.scaling.orientation = 'maxMin'
    ch.x_axis.delete = False; ch.y_axis.delete = False
    ch.y_axis.majorGridlines = None
    ch.y_axis.numFmt = '#,##0'
    g.add_chart(ch, f'F{fila0}')
    if nlista:
        lh = fl + 2
        g.cell(row=lh, column=2, value='Todos los códigos de esta área que aparecen en los documentos (sin conteo)').font = Font(name=FONT, size=11, bold=True, color=color)
        c = g.cell(row=lh + 1, column=2, value='Código – tema')
        c.font = H_FONT; c.fill = PatternFill('solid', fgColor=color)
        for i in range(nlista):
            rr = lh + 2 + i
            c = g.cell(row=rr, column=2, value=f'={idx(i, 4)}')
            c.font = Font(name=FONT, size=10)
        g.conditional_formatting.add(f'B{lh + 2}:B{lh + 1 + nlista}',
            FormulaRule(formula=[f'$B{lh + 2}<>""'], border=borde, fill=PatternFill('solid', fgColor=claro)))
        fl = lh + 1 + nlista
    return fl

finA = seccion(3, '1. Conteo y % por columna', f'=Datos!${get_column_letter(LISTCOL)}$1:${get_column_letter(LISTCOL)}${len(VARS)}',
               'Año', 'Datos', MAXA, MAXGA,
               '% sobre el total de documentos. En "Dewey por centena" un documento cuenta en cada área que tenga, así que la suma pasa de 100 %. '
               'La gráfica muestra las 15 primeras; la tabla de Facultad muestra todas.', C_CON, C_CON_CL)
filaB = finA + 4
seccion(filaB, '2. Dewey por códigos: elige el área (centena)',
        f'=DatosDewey!${get_column_letter(LISTB)}$1:${get_column_letter(LISTB)}${len(cent_labels)}',
        '300 – ' + DEWEY['300'], 'DatosDewey', TOPB + 1, TOPB + 1,
        'Un documento puede tener varios códigos, por eso la suma pasa del total. Las áreas descartadas (000, 100, 200, 400, 800) aparecen '
        'porque esos documentos también traen otro código que sí pasó.', C_DEW, C_DEW_CL, nlista=MAXLISTA)
for col in ('X', 'Y', 'Z'):
    g.column_dimensions[col].hidden = True

# ================= Resumen =================
r = ws_res
r.sheet_view.showGridLines = False
r.column_dimensions['A'].width = 2
r.column_dimensions['B'].width = 52
r.column_dimensions['C'].width = 16
r.column_dimensions['D'].width = 3
r.column_dimensions['E'].width = 55
r['B1'] = 'Documentos del repositorio UNAL que pasaron el filtro'
r['B1'].font = Font(name=FONT, size=16, bold=True, color=C_RES)
r['B2'] = 'Piloto chatbot UNAL por la Paz · reforma agraria y tierras · documentos fechados 2011–2021'
r['B2'].font = Font(name=FONT, size=10, italic=True, color='808080')

def fila_kpi(f, texto, valor, fmt='#,##0', negrita=False, nota=None):
    a = r.cell(row=f, column=2, value=texto); a.font = Font(name=FONT, bold=negrita, size=11)
    b = r.cell(row=f, column=3, value=valor); b.font = Font(name=FONT, bold=negrita, size=11 if not negrita else 13)
    b.number_format = fmt; b.alignment = Alignment(horizontal='right')
    for c in (a, b):
        c.border = Border(bottom=thin)
    if negrita:
        for c in (a, b):
            c.fill = PatternFill('solid', fgColor=C_RES_CL)
    if nota:
        r.cell(row=f, column=5, value=nota).font = Font(name=FONT, size=9, italic=True, color='808080')

r['B4'] = 'Cómo quedó la base'; r['B4'].font = Font(name=FONT, size=12, bold=True, color=C_RES)
fila_kpi(5, 'Documentos del repositorio fechados 2011–2021', 21486, nota='Del reporte de objetos de DSpace (corte 10 jun 2026)')
fila_kpi(6, 'Quitados por no ser texto (audio, imágenes, partituras…)', 206)
fila_kpi(7, 'Quitados por área temática (Dewey)', 12443)
fila_kpi(8, 'De ellos, rescatados por palabras clave', 61, nota='Ya están incluidos en el total de abajo')
fila_kpi(9, 'Documentos que quedaron', '=COUNTA(Documentos!B:B)-1', negrita=True, nota='Se cuenta solo desde la hoja Documentos')
fila_kpi(10, 'Peso total de los archivos', 52.1, fmt='0.0" GB"', nota='Medido el 5 oct 2026 con la información del repositorio')

r['B12'] = 'Avance de la revisión (se actualiza solo con la columna Decisión)'
r['B12'].font = Font(name=FONT, size=12, bold=True, color=C_RES)
for i, k in enumerate(['INCLUIR', 'POSIBLE', 'EXCLUIR', 'REVISAR']):
    f = 13 + i
    fila_kpi(f, k, f'=COUNTIF(Documentos!M:M,"{k}")')
    r.cell(row=f, column=2).fill = PatternFill('solid', fgColor=colores[k])
fila_kpi(17, 'Sin revisar todavía', '=C9-SUM(C13:C16)', negrita=True)

r['B19'] = 'Qué hay en cada hoja'; r['B19'].font = Font(name=FONT, size=12, bold=True, color=C_RES)
guia = [('Gráficas', 'Elige una columna en la celda amarilla y la gráfica cambia sola'),
        ('Documentos', 'La lista completa, con filtros en cada encabezado y el link a cada documento'),
        ('Cómo se filtró', 'Los pasos del filtro, explicados en corto')]
for i, (a, b) in enumerate(guia):
    r.cell(row=20 + i, column=2, value=a).font = Font(name=FONT, bold=True)
    r.cell(row=20 + i, column=3, value=b).font = Font(name=FONT)

# gráfica por año fija
yr = VARS[0][1]
ych = BarChart(); ych.type = 'col'; ych.legend = None
ych.title = 'Documentos por año'
ych.height = 8; ych.width = 17; ych.gapWidth = 40
ych.add_data(Reference(ws_dat, min_col=2, min_row=2, max_row=1 + len(yr)), titles_from_data=False)
ych.set_categories(Reference(ws_dat, min_col=1, min_row=2, max_row=1 + len(yr)))
ys = ych.series[0]
ys.graphicalProperties.solidFill = C_RES; ys.graphicalProperties.line.solidFill = C_RES
ys.dLbls = DataLabelList(); ys.dLbls.showVal = True
for a in ('showSerName', 'showCatName', 'showLegendKey', 'showPercent'):
    setattr(ys.dLbls, a, False)
ych.x_axis.delete = False; ych.y_axis.delete = False; ych.y_axis.majorGridlines = None
ych.roundedCorners = False
r.add_chart(ych, 'B24')

# ================= Cómo se filtró =================
c = ws_como
c.sheet_view.showGridLines = False
c.column_dimensions['A'].width = 2; c.column_dimensions['B'].width = 6; c.column_dimensions['C'].width = 110
c['B1'] = 'Cómo se filtró'; c['B1'].font = Font(name=FONT, size=16, bold=True, color=AZUL)
pasos = [
    ('1', 'Se partió del reporte completo del repositorio de la UNAL (36.777 documentos, corte 10 de junio de 2026).'),
    ('2', 'Se dejaron solo los documentos fechados entre 2011 y 2021 (por la fecha del documento): quedaron 21.486.'),
    ('3', 'Se quitaron los que no son texto: audios, imágenes, partituras, presentaciones y similares (206).'),
    ('4', 'Se filtró por área temática con la clasificación Dewey que trae cada documento. Se descartaron áreas que no tocan el tema '
          '(religión, lenguas, literatura, filosofía, generalidades) y, dentro de ciencias naturales y tecnología, solo pasan las que tienen que ver con '
          'agro, ambiente, territorio y planificación. Ciencias sociales e historia de Colombia pasan casi completas.'),
    ('5', 'Basta con que uno de los códigos Dewey del documento pase. Los documentos sin Dewey se dejaron para revisión (no se botaron).'),
    ('6', 'De los descartados, se rescataron los que mencionan términos fuertes en título o resumen: reforma agraria, campesino, restitución de tierras, '
          'despojo, desplazamiento forzado, baldíos, zonas de reserva campesina, Ley 1448, etc. Volvieron 61.'),
    ('7', 'Resultado: 8.837 documentos. Este filtro es amplio a propósito; el siguiente paso es revisar por el resumen con el criterio de Natalia (INCLUIR / POSIBLE / EXCLUIR / REVISAR).'),
]
for i, (n, t) in enumerate(pasos):
    f = 3 + i
    c.cell(row=f, column=2, value=n).font = Font(name=FONT, bold=True, size=12, color=AZUL)
    c.cell(row=f, column=2).alignment = Alignment(vertical='top', horizontal='center')
    c.cell(row=f, column=3, value=t).font = Font(name=FONT, size=11)
    c.cell(row=f, column=3).alignment = Alignment(wrap_text=True, vertical='top')
    c.row_dimensions[f].height = 48 if len(t) > 110 else 22
c['B12'] = 'Notas'; c['B12'].font = Font(name=FONT, size=12, bold=True, color=AZUL)
notas = [
    'Columna Decisión (hoja Documentos): es la única que se llena a mano, junto con Comentarios. Tiene lista desplegable con INCLUIR, POSIBLE, EXCLUIR, REVISAR. '
    'Ejemplo: un documento sobre restitución de tierras a víctimas → INCLUIR. El avance se ve solo en la hoja Resumen.',
    'Los textos (títulos, resúmenes) están tal cual vienen del repositorio; si están en inglés, quedan en inglés.',
    'Se unificaron etiquetas de Tipo que venían repetidas con otra escritura ("Otros"/"otros" → "Otro", "Libro Completo" → "Libro completo").',
    'Las columnas "Sede o comunidad" y "Facultad o colección" a veces traen nombres de colecciones (ej. Biblioteca Digital Feminista) porque así está organizado el repositorio.',
    'En Dewey, cada código va en su propia línea. Los nombres de los temas salen del mismo repositorio.',
]
for i, t in enumerate(notas):
    f = 13 + i
    c.cell(row=f, column=2, value='•').alignment = Alignment(horizontal='center', vertical='top')
    c.cell(row=f, column=3, value=t).font = Font(name=FONT, size=10)
    c.cell(row=f, column=3).alignment = Alignment(wrap_text=True, vertical='top')
    c.row_dimensions[f].height = 30 if len(t) > 110 else 18

from openpyxl.workbook.properties import CalcProperties
wb.calculation = CalcProperties(fullCalcOnLoad=True)
wb.active = 0
wb.save(OUT)
print('ok', OUT, N)
