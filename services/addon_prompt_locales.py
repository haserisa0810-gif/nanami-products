"""Localized AI instructions for add-on YAML products."""

from __future__ import annotations


def build_addon_prompt(product_type: str, lang: str, *, stored_prompt: str = "") -> str:
    if lang == "ja":
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
    return f"{intros[safe_lang][kind]}\n\n{rules[safe_lang]}\n\n{closing[safe_lang]}\n"
