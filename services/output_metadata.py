"""Remove installation diagnostics at the customer export boundary only."""
from copy import deepcopy


EPHEMERIS_DIAGNOSTIC_KEYS = frozenset({
    "ephe_dir", "ephe_dir_exists", "ephe_files", "resolved_ephe_dir",
    "searched_ephe_dirs", "env_sweph_ephe_path",
})


def customer_output_doc(doc: dict) -> dict:
    """Copy without changing calculated values, engine IDs or source objects.

    Stored complete originals deliberately do not pass through this function.
    Unknown ephemeris metadata and has_se1 remain available for provenance.
    """
    output = deepcopy(doc)
    visited = set()

    def visit(value):
        if not isinstance(value, (dict, list)) or id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, dict):
            ephemeris = value.get("ephemeris")
            if isinstance(ephemeris, dict):
                for key in EPHEMERIS_DIAGNOSTIC_KEYS:
                    ephemeris.pop(key, None)
            for item in value.values():
                visit(item)
        else:
            for item in value:
                visit(item)

    visit(output)
    return output
