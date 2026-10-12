"""Shared Four Pillars interpretation constraints; no calculation or IO."""

_RULES = {
    "en": [
        "Use the calculated YAML as the only calculation source. Do not recalculate pillars or cycles from birth information, alter values, or invent missing sections.",
        "Read the Day Master, month command, pillars, hidden stems, Ten Gods, twelve stages, Five Elements and empty branches. Treat auxiliary stars as supporting evidence.",
        "Prioritize normalized_data.structural_analysis: roots, exposed stems and ten_god_strength over simple counts. The Day Master itself is not included in Ten God strength.",
        "pattern_analysis and useful_god_analysis are experimental candidates by method, not established classifications or favorable elements. Read confidence, reasons, conflicting_rules and methodology.limitations; never select a useful element just because its count is low.",
        "ten_god_flow and element_flow with both_present indicate coexistence, not a proven functional result. Check day_master_support, roots and exposure; verify combination_screening before treating combinations as transformations.",
        "annual_fortune is the annual influence at original creation, not automatically the year of this conversation. For annual_forecasts use the requested effective_year, natal_analysis and daiun_contexts. Interpret only included years; never infer or calculate missing years.",
        "Annual periods run from Lichun to the following Lichun. Luck-cycle boundaries are approximate, based on approximate starting age. For daiun_boundary_in_window use each overlap_start_approx and overlap_end_approx; do not claim an exact transition date.",
        "For unknown or approximate birth time follow birth_time.accuracy, time_sensitive_reference and time_basis. Prefer the three reliable pillars; do not use assumed hour pillars, hidden stems, stages, empty branches, auxiliary stars or hour-dependent interactions as certain evidence. Legacy all-pillar counts and strength scores are reference values.",
        "Keep natal pillars, luck-cycle index, annual effective_year and interaction participants distinct. Do not merge equal stems, branches or relations across contexts. If evidence_id cannot be resolved, do not invent its evidence.",
        "Separate calculated facts, astrological interpretation, the user's real-world information and practical advice. Avoid uniform good/bad judgments; explain relevant limitations, favorable tendencies and cautions.",
    ],
    "es": [
        "Utiliza el YAML calculado como única fuente de cálculo. No recalcules pilares ni ciclos a partir del nacimiento, no cambies valores ni inventes secciones ausentes.",
        "Lee el Maestro del Día, el mandato mensual, los pilares, tallos ocultos, Diez Dioses, doce etapas, Cinco Elementos y ramas vacías. Las estrellas auxiliares son evidencia complementaria.",
        "Prioriza normalized_data.structural_analysis: raíces, tallos expuestos y ten_god_strength frente a los recuentos simples. El Maestro del Día no se incluye en la fuerza de los Diez Dioses.",
        "pattern_analysis y useful_god_analysis son candidatos experimentales por método, no clasificaciones ni elementos favorables confirmados. Consulta confidence, reasons, conflicting_rules y methodology.limitations; no elijas un elemento útil solo por su escasez.",
        "both_present en ten_god_flow y element_flow indica coexistencia, no un efecto confirmado. Comprueba day_master_support, raíces, exposición y combination_screening antes de afirmar una transformación.",
        "annual_fortune corresponde al año de creación del original, no automáticamente al año de la conversación. En annual_forecasts consulta effective_year, natal_analysis y daiun_contexts del año solicitado. Usa solo años incluidos; no deduzcas ni calcules años ausentes.",
        "Los periodos anuales van de Lichun al siguiente Lichun. Los cambios de ciclo son aproximados según la edad inicial estimada. Para daiun_boundary_in_window respeta overlap_start_approx y overlap_end_approx; no afirmes una fecha exacta de cambio.",
        "Con hora desconocida o aproximada respeta birth_time.accuracy, time_sensitive_reference y time_basis. Prioriza los tres pilares fiables; no uses como evidencia cierta el pilar horario supuesto ni sus tallos ocultos, etapas, ramas vacías, estrellas o relaciones. Los recuentos antiguos de cuatro pilares son referencias.",
        "Distingue pilares natales, índice de ciclo, effective_year y participantes de cada relación. No fusiones datos iguales de contextos distintos. No inventes evidencia para un evidence_id sin resolver.",
        "Separa hechos calculados, interpretación, información real de la persona y consejos. Evita juicios uniformes de bueno o malo; explica límites, tendencias favorables y precauciones.",
    ],
    "de": [
        "Nutze das berechnete YAML als einzige Berechnungsgrundlage. Berechne Säulen oder Zyklen nicht aus Geburtsangaben neu, ändere keine Werte und erfinde keine fehlenden Bereiche.",
        "Lies Tagesmeister, Monatskommando, Säulen, verborgene Stämme, Zehn Götter, zwölf Stadien, Fünf Elemente und leere Zweige. Hilfssterne sind ergänzende Hinweise.",
        "Priorisiere normalized_data.structural_analysis: Verwurzelung, sichtbare Stämme und ten_god_strength vor einfachen Anzahlen. Der Tagesmeister selbst zählt nicht zur Stärke der Zehn Götter.",
        "pattern_analysis und useful_god_analysis sind experimentelle Kandidaten je Methode, keine gesicherten Muster oder günstigen Elemente. Beachte confidence, reasons, conflicting_rules und methodology.limitations; wähle kein nützliches Element allein wegen einer niedrigen Anzahl.",
        "both_present in ten_god_flow und element_flow bedeutet gemeinsames Vorkommen, keine bestätigte Wirkung. Prüfe day_master_support, Wurzeln, Sichtbarkeit und combination_screening, bevor du eine Umwandlung behauptest.",
        "annual_fortune gilt für das Jahr der ursprünglichen Erstellung, nicht automatisch für das Gesprächsjahr. Nutze in annual_forecasts effective_year, natal_analysis und daiun_contexts des angefragten Jahres. Deute nur enthaltene Jahre; erfinde oder berechne keine fehlenden Jahre.",
        "Jahresperioden laufen von Lichun bis zum nächsten Lichun. Zykluswechsel beruhen auf einem ungefähren Startalter. Beachte bei daiun_boundary_in_window overlap_start_approx und overlap_end_approx; nenne keinen exakten Wechselzeitpunkt.",
        "Bei unbekannter oder ungefährer Geburtszeit beachte birth_time.accuracy, time_sensitive_reference und time_basis. Priorisiere die drei verlässlichen Säulen; nutze eine angenommene Stundensäule samt verborgenen Stämmen, Stadien, leeren Zweigen, Hilfssternen und Beziehungen nicht als gesicherte Grundlage. Alte Vier-Säulen-Zählungen sind Richtwerte.",
        "Trenne Geburtssäulen, Zyklusindex, effective_year und Beteiligte jeder Beziehung. Fasse gleiche Daten aus verschiedenen Kontexten nicht zusammen. Erfinde keine Belege für unauflösbare evidence_id.",
        "Trenne berechnete Fakten, Deutung, reale Angaben der Person und Ratschläge. Vermeide pauschale Gut-Schlecht-Urteile; erläutere Grenzen, günstige Tendenzen und Vorsichtspunkte.",
    ],
}


def localized_shichusuimei_rules(lang: str) -> str:
    return "\n".join("- " + rule for rule in _RULES[lang])
