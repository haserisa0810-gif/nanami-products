"""Localized AI instructions for add-on YAML products."""

from __future__ import annotations


def build_addon_prompt(product_type: str, lang: str, *, stored_prompt: str = "") -> str:
    if lang == "ja":
        from services.shichusuimei_years_addon import YEARS_ADDON_PROMPT, YEARS_ADDON_TYPES
        if product_type in YEARS_ADDON_TYPES:
            return YEARS_ADDON_PROMPT.strip() + "\n"
        if product_type.startswith("shichu_"):
            from services.yaml_exporter import SHICHU_FORTUNE_CYCLES_ADDON_PROMPT
            return SHICHU_FORTUNE_CYCLES_ADDON_PROMPT.strip() + "\n"
        return stored_prompt
    kind = (
        "asteroids" if "asteroid" in product_type
        else "four_pillars" if product_type.startswith("shichu_")
        else "long_transit" if "long_term" in product_type
        else "transit"
    )
    intros = {
        "en": {
            "asteroids": "The following YAML contains pre-calculated asteroid data to add to a base natal chart.",
            "transit": "The following YAML contains pre-calculated transit data to combine with a base natal chart.",
            "long_transit": "The following YAML contains pre-calculated long-term transit data to combine with a base natal chart.",
            "four_pillars": "The following YAML contains pre-calculated major luck-cycle and annual data to add to a base Four Pillars chart.",
        },
        "es": {
            "asteroids": "El siguiente YAML contiene datos de asteroides ya calculados para añadirlos a una carta natal base.",
            "transit": "El siguiente YAML contiene tránsitos ya calculados para combinarlos con una carta natal base.",
            "long_transit": "El siguiente YAML contiene tránsitos a largo plazo ya calculados para combinarlos con una carta natal base.",
            "four_pillars": "El siguiente YAML contiene ciclos de suerte y datos anuales ya calculados para añadirlos a una carta base de Cuatro Pilares.",
        },
        "de": {
            "asteroids": "Die folgende YAML-Datei enthält bereits berechnete Asteroidendaten als Ergänzung zu einem Basisradix.",
            "transit": "Die folgende YAML-Datei enthält bereits berechnete Transitdaten zur Verbindung mit einem Basisradix.",
            "long_transit": "Die folgende YAML-Datei enthält bereits berechnete Langzeittransite zur Verbindung mit einem Basisradix.",
            "four_pillars": "Die folgende YAML-Datei enthält bereits berechnete große Glückszyklen und Jahresdaten als Ergänzung zu einem Vier-Säulen-Basishoroskop.",
        },
    }
    rules = {
        "en": "Do not recalculate or alter any value. Read this add-on together with the buyer's base YAML. If the base YAML is missing, ask for it before interpreting. Clearly separate natal information from transit, asteroid, or luck-cycle information.",
        "es": "No recalcules ni modifiques ningún valor. Interpreta este complemento junto con el YAML base de la persona. Si falta el YAML base, solicítalo antes de interpretar. Separa claramente la información natal de los tránsitos, asteroides o ciclos de suerte.",
        "de": "Berechne oder verändere keinen Wert. Deute dieses Add-on zusammen mit der Basis-YAML der Person. Falls die Basis-YAML fehlt, bitte vor der Deutung darum. Trenne Radixangaben klar von Transiten, Asteroiden oder Glückszyklen.",
    }
    closing = {
        "en": "Use the calculated YAML below as the source and provide a structured, practical interpretation.",
        "es": "Utiliza el YAML calculado que aparece a continuación como fuente y ofrece una interpretación estructurada y práctica.",
        "de": "Verwende die folgende berechnete YAML-Datei als Quelle und gib eine strukturierte, praktische Deutung.",
    }
    safe_lang = lang if lang in intros else "en"
    if kind == "four_pillars":
        from services.shichusuimei_prompt_rules import localized_shichusuimei_rules
        rules = {
            "en": "Read this add-on together with the base Four Pillars YAML; request the base YAML if it is missing. Keep natal information, major luck cycles and included annual periods distinct.",
            "es": "Lee este complemento junto con el YAML base de Cuatro Pilares; solicita el YAML base si falta. Distingue información natal, ciclos de suerte y periodos anuales incluidos.",
            "de": "Lies dieses Add-on zusammen mit der Vier-Säulen-Basis-YAML; bitte darum, falls sie fehlt. Trenne Geburtssäulen, große Glückszyklen und enthaltene Jahresperioden.",
        }
        return f"{intros[safe_lang][kind]}\n\n{rules[safe_lang]}\n\n{localized_shichusuimei_rules(safe_lang)}\n\n{closing[safe_lang]}\n"
    return f"{intros[safe_lang][kind]}\n\n{rules[safe_lang]}\n\n{closing[safe_lang]}\n"
