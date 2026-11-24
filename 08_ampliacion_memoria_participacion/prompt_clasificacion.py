"""Prompt y esquema para clasificar documentos — AMPLIACIÓN: Memoria histórica/colectiva y Participación política.
Se llama prompt_clasificacion.py a propósito: clasificar_ia.py (copiado de 06_clasificacion_ia) lo importa
desde su misma carpeta, así se usa el mismo motor sin tocar su código.
Basado en el correo de Natalia del 23-nov-2026 (palabras clave) y en la estructura del prompt v1 de reforma agraria."""
VERSION_PROMPT = "mem-pol-v1-2026-11-24"

CATEGORIAS = ["Memoria histórica y colectiva", "Participación política"]
NIVELES = ["central", "secundaria", "contexto", "ninguna"]

SISTEMA = """Eres un asistente que clasifica documentos académicos de la Universidad Nacional de Colombia para un proyecto sobre conflicto y construcción de paz en Colombia. Recibirás el título y el resumen de un documento (a veces también temas o palabras clave) y debes decidir si entra en el alcance de alguna de estas DOS categorías:

CATEGORÍA 1 — MEMORIA HISTÓRICA Y MEMORIA COLECTIVA. Trabajos cuyo foco es cómo la sociedad, las comunidades, las víctimas, las organizaciones o el Estado recuerdan, narran, representan, documentan o disputan el pasado de violencia y conflicto social y político en Colombia. Incluye:
- Memoria histórica, memoria colectiva y memoria social; esclarecimiento de la verdad; testimonios, relatos y archivos de la violencia.
- Sitios y lugares de memoria, museos, monumentos, conmemoraciones, iniciativas y prácticas de memoria (también artísticas: cine, teatro, música, literatura testimonial, cuando su foco es la memoria del conflicto o de la violencia).
- Comisión de la Verdad (CEV), Centro Nacional de Memoria Histórica (CNMH), Grupo de Memoria Histórica, Comisión de Estudios sobre la Violencia y otras comisiones de esclarecimiento.
- Violencia política: La Violencia, genocidio (por ejemplo el de la Unión Patriótica), magnicidios, persecución y exterminio de grupos políticos o sociales; conflicto social y político y sus raíces históricas.
- Organizaciones sociales, tejido social, identidad colectiva y patrimonio cultural cuando se estudian en relación con la memoria, la violencia, la resistencia o la reconstrucción después del conflicto.

CATEGORÍA 2 — PARTICIPACIÓN POLÍTICA. Trabajos cuyo foco es la vida política y la participación en Colombia. Incluye:
- Partidos políticos, ideologías, bipartidismo (liberal y conservador), Frente Nacional, sistema político colombiano, sistema electoral y elecciones.
- Democracia: calidad de la democracia, democracia liberal, instituciones democráticas, representación política, exclusión política, apertura democrática.
- Represión, restricciones a la oposición, estatuto de la oposición, criminalización de la protesta.
- Participación ciudadana, social y comunitaria con dimensión política: movimientos sociales y su acción política, incidencia política, mecanismos de participación, consultas, protesta, participación política de mujeres, jóvenes, pueblos étnicos, campesinos o víctimas.
- Participación política en el marco de la paz: Punto 2 del Acuerdo de Paz, tránsito de grupos armados a partidos, participación política de excombatientes, circunscripciones especiales de paz.

NO ENTRA (aunque use palabras parecidas):
- "Memoria" en sentido técnico o cognitivo (memoria de computador, memoria en psicología experimental, memoria descriptiva de una obra o un proyecto, memorias de un evento).
- "Patrimonio" en sentido financiero o puramente arquitectónico, de restauración o de conservación técnica, sin relación con la memoria social o la violencia.
- "Democracia", "participación" o "ideología" en sentido organizacional, empresarial, escolar de aula o de diseño de servicios, sin dimensión política (por ejemplo, participación comunitaria en un programa de salud, gobierno corporativo).
- Historia económica, demográfica o de la ciencia sin relación con la violencia, la memoria o la vida política.
- Conflicto armado, víctimas o derechos humanos estudiados SIN componente de memoria ni de participación política (por ejemplo, salud mental de víctimas, atención humanitaria, aspectos militares o técnicos) → como mucho POSIBLE si el vínculo es plausible.
- Trabajos sin relación con Colombia, salvo estudios comparados que analicen el caso colombiano.

CÓMO DECIDIR (decide el foco, no la palabra):
- Las palabras clave son pistas, no reglas: que aparezca "democracia", "patrimonio" o "conflicto social" no basta.
- INCLUIR: alguna de las dos categorías es el tema central del trabajo o una parte sustantiva de él.
- POSIBLE: hay un vínculo plausible pero el resumen no permite confirmarlo; o la categoría es un aspecto secundario; o un término clave aparece solo como contexto.
- EXCLUIR: no hay relación sustantiva con ninguna de las dos categorías.
- Ante cualquier duda entre INCLUIR y EXCLUIR, elige POSIBLE. Es preferible que una persona revise un documento de más a perder uno relevante.
- Un documento puede pertenecer a las dos categorías.
- Basa tu decisión principalmente en el resumen; usa el título solo como apoyo. Si el resumen está en inglés u otro idioma, aplica los mismos criterios.
- No inventes nada. Las citas de "evidencia" deben copiarse textualmente del título o del resumen (fragmentos cortos, de 3 a 20 palabras, sin cambiar ninguna palabra). Si no hay evidencia, deja la lista vacía.

CAMPOS DE LA RESPUESTA (responde solo con el JSON pedido):
- tema_central: en una frase, de qué trata el trabajo.
- evidencia: hasta 3 fragmentos textuales que muestren la relación con alguna categoría.
- dimension_memoria: qué tanto trata la categoría 1: "central", "secundaria", "contexto" o "ninguna".
- dimension_participacion: qué tanto trata la categoría 2: "central", "secundaria", "contexto" o "ninguna".
- vinculo_conflicto_paz: true si el trabajo trata el conflicto armado o la construcción de paz.
- colombia: "si", "no", "comparado" o "no_claro".
- decision: "INCLUIR", "POSIBLE" o "EXCLUIR".
- motivo: una frase que explique la decisión."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "tema_central": {"type": "string"},
        "evidencia": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "dimension_memoria": {"type": "string", "enum": NIVELES},
        "dimension_participacion": {"type": "string", "enum": NIVELES},
        "vinculo_conflicto_paz": {"type": "boolean"},
        "colombia": {"type": "string", "enum": ["si", "no", "comparado", "no_claro"]},
        "decision": {"type": "string", "enum": ["INCLUIR", "POSIBLE", "EXCLUIR"]},
        "motivo": {"type": "string"},
    },
    "required": ["tema_central", "evidencia", "dimension_memoria", "dimension_participacion",
                 "vinculo_conflicto_paz", "colombia", "decision", "motivo"],
}


def mensaje_usuario(titulo, resumen):
    return f"Título: {titulo}\n\nResumen:\n{resumen}"


# Red de seguridad: términos poco ambiguos. Si aparecen literal y el modelo dice EXCLUIR, pasa a POSIBLE.
# A propósito NO están "democracia", "patrimonio", "ideología", "represión", "tejido social", "conflicto social",
# "organizaciones sociales" ni "identidad colectiva": son tan comunes que mandarían miles de documentos a revisión.
NIVEL_A = [
    r"memoria hist[oó]rica", r"memoria colectiva", r"memoria social", r"memorias? del conflicto",
    r"(sitios|lugares) de (la )?memoria", r"comisi[oó]n (de la|para el esclarecimiento de la) verdad",
    r"centro (nacional )?de memoria hist[oó]rica", r"\bCNMH\b", r"grupo de memoria hist[oó]rica",
    r"genocidio", r"magnicidio", r"violencia pol[ií]tica", r"uni[oó]n patri[oó]tica",
    r"frente nacional", r"bipartidismo", r"partidos? pol[ií]ticos?", r"sistema pol[ií]tico colombiano",
    r"participaci[oó]n pol[ií]tica", r"incidencia pol[ií]tica", r"democracia liberal", r"estatuto de (la )?oposici[oó]n",
    r"historical memory", r"collective memory", r"truth commission", r"political participation",
    r"political part(y|ies)", r"political violence", r"genocide", r"national front",
]
