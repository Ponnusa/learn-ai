"""
Domain templates: bad-visual red-flag list, concept-type requirements,
and domain-level style guidance used by the prompt builder.
"""

# ── Bad visuals — injected into EVERY prompt ──────────────────────────────────
BAD_VISUALS: list[str] = [
    "temperature field lines",
    "heat particles",
    "energy clouds",
    "magic arrows with no labels",
    "decorative equations floating in space",
    "unlabeled graphs or axes",
    "fake or invented units",
    "energy stored as glowing balls",
    "work as a visible substance or fluid",
    "force as invisible wind or smoke",
    "photons as solid colored dots",
    "pressure shown as color gradients without labels",
    "electrons as solid spheres without labels",
    "chemical bonds as glowing beams",
    "DNA as a simple twisted rope with no base labels",
]

# ── Per concept-type requirements ─────────────────────────────────────────────
CONCEPT_TYPE_REQUIREMENTS: dict[str, dict] = {
    "force_diagram": {
        "required_elements": [
            "force vectors as arrows from center of mass",
            "arrow labels with force name and unit (N)",
            "object drawn as simple rectangle or circle",
            "coordinate axes if inclined plane",
        ],
        "style_notes": "free-body diagram style, white background, vectors clearly separated",
        "avoid": ["decorative backgrounds", "motion blur", "perspective distortion", "3D shading"],
    },
    "energy_transfer": {
        "required_elements": [
            "system boundary drawn as dashed rectangle",
            "labeled energy flow arrows (direction + type)",
            "source object and sink object both labeled",
            "energy type labeled on each arrow (heat/work/radiation)",
        ],
        "style_notes": "block diagram style, arrow thickness proportional to energy amount",
        "avoid": ["energy clouds", "heat particles", "glow effects", "unlabeled arrows"],
    },
    "cycle": {
        "required_elements": [
            "circular or loop arrow showing flow direction",
            "each stage labeled with name and brief description",
            "input/output labeled at appropriate points",
        ],
        "style_notes": "circular layout with equal spacing between stages, clockwise direction",
        "avoid": ["3D perspective", "decorative textures", "ambiguous arrow paths"],
    },
    "chemical_reaction": {
        "required_elements": [
            "reactant molecules on left side",
            "product molecules on right side",
            "reaction arrow in center with conditions above/below",
            "state labels (s), (l), (g), (aq) for each species",
            "coefficients shown",
        ],
        "style_notes": "left-to-right flow, structural formulas preferred over names alone",
        "avoid": ["3D molecular orbitals", "color gradients for bonds", "unlabeled atoms"],
    },
    "graph": {
        "required_elements": [
            "x-axis with label and unit",
            "y-axis with label and unit",
            "axis tick marks with values",
            "curve or data points clearly drawn",
            "legend if more than one series",
            "graph title",
        ],
        "style_notes": "clean axes, minimal gridlines, high-contrast curve on white background",
        "avoid": ["3D bar charts", "chart junk", "decorative backgrounds", "missing axis labels"],
    },
    "anatomy": {
        "required_elements": [
            "labeled structures with leader lines",
            "clear boundaries between regions",
            "scale bar or magnification if relevant",
            "directional labels (anterior/posterior or North/South if geographic)",
        ],
        "style_notes": "cross-section view preferred, neutral distinct colors per region",
        "avoid": ["photorealistic rendering", "decorative backgrounds", "unlabeled structures"],
    },
    "process_flow": {
        "required_elements": [
            "numbered or sequenced steps in order",
            "directional arrows between steps",
            "each step labeled with a short action phrase",
            "start and end points marked",
        ],
        "style_notes": "top-to-bottom or left-to-right, boxes for stages, clear arrow direction",
        "avoid": ["circular layout for linear processes", "ambiguous arrow direction", "missing step labels"],
    },
    "comparison": {
        "required_elements": [
            "two or more clearly labeled columns or sections",
            "dividing line between sections",
            "same properties compared in aligned rows",
            "headers for each column",
        ],
        "style_notes": "side-by-side table or split layout, aligned rows for easy reading",
        "avoid": ["mixing unrelated properties", "unequal column widths without reason"],
    },
    "circuit": {
        "required_elements": [
            "standard circuit symbols (IEC or ANSI)",
            "all components labeled with values",
            "current direction arrows",
            "voltage source polarity marked",
            "wire paths at right angles",
        ],
        "style_notes": "clean orthogonal wire paths, standard symbols only",
        "avoid": ["artistic curved wires", "unlabeled components", "non-standard symbols"],
    },
    "wave": {
        "required_elements": [
            "wavelength marked with double-headed arrow and λ label",
            "amplitude marked with double-headed arrow and A label",
            "x-axis (distance or time) labeled with unit",
            "at least one full cycle shown",
        ],
        "style_notes": "sinusoidal curve on clean axes, all measurements annotated",
        "avoid": ["3D wave unless comparing transverse vs longitudinal", "missing axis labels"],
    },
    "hierarchy": {
        "required_elements": [
            "root node at top level",
            "all nodes labeled",
            "branching lines connecting parent to children",
            "level labels if relevant (Kingdom/Phylum etc)",
        ],
        "style_notes": "top-down tree layout, equal horizontal spacing at each level",
        "avoid": ["circular hierarchy", "nodes without labels"],
    },
    "timeline": {
        "required_elements": [
            "horizontal or vertical time axis",
            "labeled events at correct relative positions",
            "time scale shown (years, seconds, etc)",
            "direction of time indicated",
        ],
        "style_notes": "linear axis, events above/below the line alternating to prevent overlap",
        "avoid": ["circular timeline for linear history", "missing time units"],
    },
}

# ── Domain-level style guidance ───────────────────────────────────────────────
DOMAIN_STYLES: dict[str, str] = {
    "physics": (
        "clean textbook physics diagram, black outlines on white background, "
        "precise vector arrows with clear arrowheads, all quantities labeled with SI units, "
        "no decorative shading or 3D effects"
    ),
    "chemistry": (
        "chemistry textbook style, accurate molecular geometry, "
        "standard element color convention (O=red, H=white, C=gray, N=blue, S=yellow), "
        "reaction arrows with conditions labeled above/below"
    ),
    "mathematics": (
        "precise geometric diagram, exact angles labeled in degrees, "
        "coordinate grid if relevant, clean sans-serif labels, "
        "no decorative art — pure mathematical clarity"
    ),
    "biology": (
        "biology textbook illustration style, labeled anatomical structures with leader lines, "
        "clear cell or tissue boundaries, process arrows for metabolic flows, "
        "neutral scientific color palette"
    ),
    "geography": (
        "clear map-style or cross-section diagram, compass direction indicator if relevant, "
        "legend included, scale reference, neutral topographic color convention"
    ),
    "general": (
        "clear educational infographic, logical left-to-right or top-to-bottom flow, "
        "high-contrast labels, minimal decoration, white background"
    ),
}
