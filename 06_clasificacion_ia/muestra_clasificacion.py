"""
Arma la muestra para que Natalia clasifique a mano (sirve para medir la exactitud de la IA).

Genera dos archivos:
  1) Muestra_clasificacion_Natalia.xlsx   -> el que se le manda a Natalia (N°, Título, Resumen, Decisión, Comentarios, Link, ¿Abrí el documento?)
  2) clave_muestra_NO_COMPARTIR.xlsx      -> solo para nosotros (grupo ajuste/evaluación, tipo, peso, fila original)

Uso:
  python muestra_clasificacion.py Documentos_filtrados_repositorio_UNAL2.xlsx --salida ./salida --n 300 --semilla 2026
"""
import argparse, random
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

FONT = 'Calibri'
ap = argparse.ArgumentParser()
ap.add_argument('entrada')
ap.add_argument('--salida', default='.')
ap.add_argument('--n', type=int, default=300)
ap.add_argument('--n_ajuste', type=int, default=100)      # el resto (n - n_ajuste) es el grupo de evaluación final
ap.add_argument('--semilla', type=int, default=2026)
ap.add_argument('--min_resumen', type=int, default=100)   # caracteres mínimos para considerar que "tiene resumen"
args = ap.parse_args()
out = Path(args.salida); out.mkdir(parents=True, exist_ok=True)

# ---------- 1. leer el Excel de los 8.837 (con links reales) ----------
wb = load_workbook(args.entrada)              # no read_only: así se pueden leer los hipervínculos
ws = wb['Documentos']
hdr = [c.value for c in ws[1]]
ix = {h: i for i, h in enumerate(hdr)}
filas = []
for r in ws.iter_rows(min_row=2):
    link = r[ix['Link']].hyperlink.target if r[ix['Link']].hyperlink else None
    filas.append({
        'fila_original': r[ix['N°']].value,
        'Título': r[ix['Título']].value,
        'Resumen': r[ix['Resumen']].value,
        'Tipo': r[ix['Tipo']].value or '(sin tipo)',
        'Link': link,
    })
df = pd.DataFrame(filas)
df['Resumen'] = df['Resumen'].fillna('').astype(str).str.strip()
total = len(df)
df = df[df['Resumen'].str.len() >= args.min_resumen].reset_index(drop=True)
# quitar títulos repetidos (mismo documento registrado dos veces): evita que uno caiga en ajuste y otro en evaluación
df['_t'] = df['Título'].fillna('').astype(str).str.lower().str.replace(r'\s+', ' ', regex=True).str.strip()
repetidos = df.duplicated('_t').sum()
df = df.drop_duplicates('_t').drop(columns='_t').reset_index(drop=True)
print(f'{total} documentos en el Excel, {len(df)} con resumen (>= {args.min_resumen} caracteres) y sin título repetido ({repetidos} repetidos quitados)')

# ---------- 2. cuántos de cada Tipo (mínimo por tipo para ver cómo le va a la IA con lo que no son tesis) ----------
def reparto(cuotas, total_objetivo):
    """Largest remainder: convierte cuotas decimales en enteros que suman total_objetivo."""
    base = {k: int(v) for k, v in cuotas.items()}
    faltan = total_objetivo - sum(base.values())
    resto = sorted(cuotas, key=lambda k: cuotas[k] - base[k], reverse=True)
    for k in resto[:faltan]:
        base[k] += 1
    return base

tam = df.groupby('Tipo').size().to_dict()
piso = {t: min(n, 15 if n >= 100 else 3) for t, n in tam.items()}
sobra = args.n - sum(piso.values())
disp = {t: tam[t] - piso[t] for t in tam}
cuotas = {t: sobra * disp[t] / sum(disp.values()) for t in tam}
extra = reparto(cuotas, sobra)
cupo = {t: min(tam[t], piso[t] + extra[t]) for t in tam}
# si algún tipo se pasó de su tamaño, lo que falte se reparte a los que aún tienen documentos libres
while sum(cupo.values()) < args.n:
    t = max((t for t in tam if cupo[t] < tam[t]), key=lambda t: tam[t] - cupo[t])
    cupo[t] += 1

# ---------- 3. muestreo al azar dentro de cada tipo + división ajuste / evaluación ----------
rng = random.Random(args.semilla)
elegidos = []
for t, k in cupo.items():
    idx = list(df.index[df['Tipo'] == t])
    rng.shuffle(idx)
    elegidos += [(i, t) for i in idx[:k]]
m = df.loc[[i for i, _ in elegidos]].copy()
m['Peso'] = m['Tipo'].map(lambda t: tam[t] / cupo[t])        # para promediar sin sesgo por haber sobremuestreado tipos chicos

# grupo: se asigna proporcional dentro de cada tipo
cuotas_aj = {t: cupo[t] * args.n_ajuste / args.n for t in cupo}
aj = reparto(cuotas_aj, args.n_ajuste)
grupo = {}
for t in cupo:
    ids = list(m.index[m['Tipo'] == t]); rng.shuffle(ids)
    for j, i in enumerate(ids):
        grupo[i] = 'AJUSTE' if j < aj[t] else 'EVALUACIÓN'
m['Grupo'] = pd.Series(grupo)

# orden final mezclado (Natalia no debe notar ni el tipo ni el grupo)
orden = list(m.index); rng.shuffle(orden)
m = m.loc[orden].reset_index(drop=True)
m.insert(0, 'N°', range(1, len(m) + 1))

# ---------- 4. Excel de Natalia (formato plano) ----------
borde = Border(*(Side(style='thin', color='BFBFBF'),) * 4)
nw = Workbook()
w = nw.active; w.title = 'Clasificar'
cols = [('N°', 6), ('Título', 45), ('Resumen', 100), ('Decisión', 14), ('Comentarios', 35), ('Link', 18), ('¿Abrí el documento?', 14)]
for j, (h, ancho) in enumerate(cols, 1):
    c = w.cell(row=1, column=j, value=h)
    c.font = Font(name=FONT, bold=True, size=11)
    c.fill = PatternFill('solid', fgColor='E7E6E6')
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    c.border = borde
    w.column_dimensions[chr(64 + j)].width = ancho
w.row_dimensions[1].height = 32
cuerpo = Font(name=FONT, size=10)
for i, r in m.iterrows():
    f = i + 2
    vals = [r['N°'], r['Título'], r['Resumen'], None, None, None, 'No']
    for j, v in enumerate(vals, 1):
        c = w.cell(row=f, column=j, value=v)
        c.font = cuerpo; c.border = borde
        c.alignment = Alignment(vertical='top', horizontal='center' if j in (1, 4, 7) else None, wrap_text=True)
    if r['Link']:
        c = w.cell(row=f, column=6, value='Ver en repositorio')
        c.hyperlink = r['Link']
        c.font = Font(name=FONT, size=10, color='0563C1', underline='single')
        c.alignment = Alignment(vertical='top', horizontal='center')
    lineas = max(len(r['Resumen']) / 115, len(str(r['Título'])) / 48) + 1
    w.row_dimensions[f].height = min(409, max(60, lineas * 13.5))
ult = len(m) + 1
dv = DataValidation(type='list', formula1='"INCLUIR,POSIBLE,EXCLUIR"', allow_blank=True)
dv.error = 'Elige INCLUIR, POSIBLE o EXCLUIR'; dv.errorTitle = 'Valor no válido'
w.add_data_validation(dv); dv.add(f'D2:D{ult}')
dv2 = DataValidation(type='list', formula1='"Sí,No"', allow_blank=False)
w.add_data_validation(dv2); dv2.add(f'G2:G{ult}')
w.freeze_panes = 'D2'

g = nw.create_sheet('Instrucciones')
g.sheet_view.showGridLines = False
g.column_dimensions['A'].width = 3; g.column_dimensions['B'].width = 120
lineas = [
    ('Cómo clasificar', True),
    ('Clasifica usando solo el título y el resumen. Es lo mismo que va a leer la IA, así la comparación es justa.', False),
    ('', False),
    ('Columna Decisión (lista desplegable):', True),
    ('INCLUIR: el documento claramente entra en el alcance del asistente.', False),
    ('POSIBLE: no estás segura, o hay que revisarlo con más detalle. Ante la duda, POSIBLE.', False),
    ('EXCLUIR: claramente no entra.', False),
    ('', False),
    ('Columna ¿Abrí el documento?: viene en "No". Si el título y el resumen no te alcanzaron y tuviste que abrir el documento (con el Link), cámbialo a "Sí".', False),
    ('Columna Comentarios: opcional, para lo que quieras anotar.', False),
    ('', False),
    ('No tienes que clasificar todo de una vez. Los documentos están en orden mezclado a propósito: clasifica en el orden en que aparecen, desde el N° 1, hasta donde alcances.', False),
    ('', False),
    (f'Avance: ', True),
]
for i, (t, neg) in enumerate(lineas, 1):
    c = g.cell(row=i, column=2, value=t); c.font = Font(name=FONT, size=11, bold=neg)
    c.alignment = Alignment(wrap_text=True, vertical='top')
fila_av = len(lineas)
g.cell(row=fila_av, column=2, value=f'="Avance: "&COUNTA(Clasificar!D2:D{ult})&" de {len(m)} clasificados"').font = Font(name=FONT, size=11, bold=True)
nw.save(out / 'Muestra_clasificacion_Natalia.xlsx')

# ---------- 5. clave interna ----------
kw = Workbook(); k = kw.active; k.title = 'Clave'
head = ['N°', 'Grupo', 'Tipo', 'Peso', 'Fila en el Excel de 8.837', 'Título', 'Link']
k.append(head)
for _, r in m.iterrows():
    k.append([r['N°'], r['Grupo'], r['Tipo'], round(r['Peso'], 3), r['fila_original'], r['Título'], r['Link']])
for j, ancho in enumerate([6, 14, 30, 8, 14, 60, 50], 1):
    k.column_dimensions[chr(64 + j)].width = ancho
for c in k[1]: c.font = Font(name=FONT, bold=True)
n2 = kw.create_sheet('Parámetros')
for fila in [['semilla', args.semilla], ['n', args.n], ['n_ajuste', args.n_ajuste], ['min_resumen', args.min_resumen],
             ['documentos con resumen (universo)', len(df)], ['', ''], ['Tipo', 'universo / en muestra']] + \
            [[t, f'{tam[t]} / {cupo[t]}'] for t in sorted(tam, key=tam.get, reverse=True)]:
    n2.append(fila)
n2.column_dimensions['A'].width = 38; n2.column_dimensions['B'].width = 22
kw.save(out / 'clave_muestra_NO_COMPARTIR.xlsx')

print(m.groupby(['Tipo', 'Grupo']).size().unstack(fill_value=0))
print('Total:', len(m), '| ajuste:', (m.Grupo == 'AJUSTE').sum(), '| evaluación:', (m.Grupo == 'EVALUACIÓN').sum())
