"""Library facts from docs/library-constraints.md. When that doc changes, update this file."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "output"

REQUEST_FORM_URL = "https://bama.atlassian.net/servicedesk/customer/portal/179"
PRINT_PAGE_URL = "https://www.lib.ua.edu/using-the-library/3d-print/"

# Section 1 (printers) and Section 3 (fees)
PRINTERS = {
    "Ultimaker S5": {
        "build_mm": (330, 240, 300),
        "materials": ["PLA", "ABS"],  # PLA used when the student has no preference
        "tiers": [(30, 3.00), (61, 6.00), (120, 11.00)],
        "per_gram": 0.09,
        "plate_fee": 0.00,
    },
    "Bambu X1C": {
        "build_mm": (256, 256, 256),
        "materials": ["PLA"],  # Q7 open: PLA-only at Rodgers is implied, not stated
        "tiers": [(30, 3.00), (61, 6.00), (120, 11.00)],
        "per_gram": 0.09,
        "plate_fee": 0.00,  # Q1 open: may be $8
    },
    "Stratasys F270": {
        "build_mm": (305, 254, 305),
        "materials": ["ABS"],
        "tiers": [(30, 5.00), (61, 10.00), (120, 20.00)],
        "per_gram": 0.16,
        "plate_fee": 8.00,
    },
}

# Section 2 (colors by library) and Section 6 (turnaround, contacts)
LIBRARIES = {
    "Bruno": {
        "printers": ["Ultimaker S5"],
        "turnaround": "up to 2 weeks in busy times",
        "contact": "3dbruno@ua.edu, (205) 348-1086",
        "colors": {
            "ABS": ["black", "blue", "grey", "red", "white"],
            "PLA": ["black", "blue", "green", "orange", "red", "tough matte black",
                    "translucent", "white", "yellow"],
        },
    },
    "Gorgas": {
        "printers": ["Ultimaker S5"],
        "turnaround": "up to 2 weeks in busy times",
        "contact": "3dlib@ua.edu, (205) 348-9748",
        "colors": {
            "ABS": ["black", "blue", "green", "grey", "red", "white"],
            "PLA": ["black", "blue", "green", "orange", "red", "translucent", "white", "yellow"],
        },
    },
    "Rodgers": {
        "printers": ["Bambu X1C", "Stratasys F270"],
        "turnaround": "up to 3 weeks in busy times",
        "contact": "3drodgers@ua.edu, (205) 348-2100",
        "colors": {
            "ABS": ["blue", "black", "red", "white", "ivory"],
            "PLA": ["grey", "white", "red", "green"],
        },
    },
}

# Weight estimate assumptions: placeholders until staff answer Q4
DENSITY_G_PER_CM3 = {"PLA": 1.24, "ABS": 1.04}  # typical filament densities
WALL_MM = 1.2         # roughly 3 perimeters at a 0.4 mm nozzle
INFILL = 0.20         # 20% infill
WEIGHT_MARGIN = 0.20  # price range covers the estimate +/- 20%
