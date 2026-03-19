# LICA Dataset

The **LICA dataset** ([paper link](https://arxiv.org/pdf/2603.16098v1)) is a collection of graphic design layouts, released to 
promote research in the field of AI for Design. Each layout captures the complete rendering specification of a design — component positions, typography, images, and background — alongside rich natural-language annotations at both the layout and template level.

Layouts are organized by **template**: a template is a design theme that can produce multiple layout variations (slides). Each template folder contains all of its layouts, rendered images, and per-layout annotations.

<p align="center">
<img width="800" height="500" alt="Screenshot 2026-03-18 at 8 50 08 PM" src="https://github.com/user-attachments/assets/edee2b55-9ec9-49ac-bf3c-4bde21214f18" />
</p>

## Getting started

1. Download the `lica-data` [folder](https://storage.googleapis.com/lica-assets/websites/blog/lica-data.zip) and place it in the root of this repository so the structure looks like:

```
lica-dataset/
├── lica-data/          # <-- place here
├── lica_dataset.py
├── requirements.txt
└── README.md
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

Python 3.9 or later is required.

## Dataset structure

```
lica-data/
├── metadata.csv                              # per-layout metadata
├── layouts/
│   └── <template_id>/
│       └── <layout_id>.json                  # component-level layout spec
├── images/
│   └── <template_id>/
│       └── <layout_id>.png                   # rendered layout image
└── annotations/
    ├── template_annotations.json             # template-level annotations
    └── <template_id>/
        └── <layout_id>.json                  # per-layout annotation
```

### `metadata.csv`

| Column | Type | Description |
|---|---|---|
| `layout_id` | string | Unique layout ID (matches filenames in `layouts/`, `images/`, `annotations/`) |
| `category` | string | Design category (e.g. `"Presentations"`, `"Videos"`, `"Education"`, `"Flyers"`) |
| `template_id` | string | UUID of the template this layout belongs to (matches folder names) |
| `n_template_layouts` | int | Total number of layouts in the template group |
| `template_layout_index` | int | Zero-based position of this layout within its template group |
| `width` | int | Canvas width in pixels |
| `height` | int | Canvas height in pixels |

### Layout JSON (`layouts/<template_id>/<layout_id>.json`)

Each layout file is a flat JSON object with the canvas specification and a list of components:

```json
{
  "components": [ ... ],
  "background": "rgb(252, 252, 252)",
  "width": "1920px",
  "height": "1080px",
  "duration": 3
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `components` | array | yes | Ordered list of rendering components (see below) |
| `width` | string | yes | Canvas width with `"px"` suffix |
| `height` | string | yes | Canvas height with `"px"` suffix |
| `background` | string | no | CSS color for the canvas background |
| `duration` | number | no | Slide duration in seconds |

#### Component types

Each component has a `type` field and CSS-like positioning/visual properties directly on the object.

**`TEXT`** — positioned text element

```json
{
  "type": "TEXT",
  "text": "Hello World",
  "left": "108px", "top": "200px", "width": "400px", "height": "50px",
  "color": "rgb(255, 255, 255)",
  "fontSize": "48px",
  "fontFamily": "League Spartan--400",
  "fontWeight": "400",
  "textAlign": "center",
  "lineHeight": "52px",
  "letterSpacing": "0em",
  "textTransform": "none",
  "fontStyle": "normal",
  "transform": "none"
}
```

**`IMAGE`** — positioned image

```json
{
  "type": "IMAGE",
  "src": "https://storage.googleapis.com/lica-video/<uuid>.png",
  "left": "0px", "top": "0px", "width": "1920px", "height": "1080px",
  "transform": "none",
  "opacity": 1,
  "overflow": "hidden"
}
```

**`GROUP`** — container/shape element with optional clip path

```json
{
  "type": "GROUP",
  "left": "108px", "top": "463px", "width": "555px", "height": "508px",
  "background": "rgb(255, 255, 255)",
  "backgroundColor": "rgb(255, 255, 255)",
  "clipPath": "path(\"M0,0 ...\")",
  "transform": "none"
}
```

### Annotations

**Per-layout** (`annotations/<template_id>/<layout_id>.json`):

```json
{
  "description": "Visual description of the specific layout",
  "aesthetics": "Notes on design style, composition, visual hierarchy",
  "tags": "comma, separated, keyword, tags",
  "user_intent": "Inferred purpose or goal of the design",
  "raw": "Concatenation of all fields above"
}
```

**Template-level** (`annotations/template_annotations.json`):

A JSON object keyed by template UUID. Each entry has the same fields (`description`, `aesthetics`, `tags`, `user_intent`, `raw`) but describes the overall design theme shared by all layouts in the template.

---

## Quick start

```python
from lica_dataset import LicaDataset

ds = LicaDataset("lica-data")
print(ds)
# LicaDataset(n=1183, categories=['Business Cards', 'Cards & Invitations', ...])
```

### Inspect categories and metadata

```python
print(ds.categories)
# ['Business Cards', 'Cards & Invitations', 'Education', 'Flyers', ...]

print(ds.templates)
# ['3b919d2e-...', '831589c4-...', ...]

# Full metadata as a Pandas DataFrame
print(ds.metadata.head())

# Per-category summary
print(ds.summary())
```

### Filter layouts

Filtering methods return a new `LicaDataset` view and are chainable.

```python
# All presentation layouts
presentations = ds.by_category("Presentations")
print(len(presentations))

# All layouts from a specific template
template_layouts = ds.by_template("3b919d2e-539f-4b2c-8d86-7709ef65b496")
print(template_layouts.metadata[["layout_id", "template_layout_index"]])

# Filter by canvas dimensions
widescreen = ds.by_dimensions(1920, 1080)

# Filter by aspect ratio
portrait = ds.by_aspect_ratio("portrait")    # height > width
landscape = ds.by_aspect_ratio("landscape")  # width > height
square = ds.by_aspect_ratio("square")        # width == height
```

### Access individual records

```python
layout_id = "gsessHF2ev5r4ZgwPUh5"

# Load the layout JSON
layout = ds.get_layout(layout_id)
print(layout.get("background"))            # "rgb(252, 252, 252)" or None
print(len(layout["components"]))           # number of components

# Per-layout annotation
annotation = ds.get_annotation(layout_id)
print(annotation["tags"])

# Template-level annotation
tmpl_ann = ds.get_template_annotation("3b919d2e-539f-4b2c-8d86-7709ef65b496")
print(tmpl_ann["description"])

# Path to the rendered image
img_path = ds.get_image_path(layout_id)
print(img_path)
# lica-data/images/3b919d2e-.../gsessHF2ev5r4ZgwPUh5.png

# Single metadata row as a dict
meta = ds.get_metadata(layout_id)
print(meta["category"])  # "Presentations"
```

### Iterate over all items

`__getitem__` returns a fully-loaded dict for each layout:

```python
for item in ds:
    layout_id        = item["layout_id"]
    template_id      = item["template_id"]
    metadata         = item["metadata"]             # dict of CSV fields
    layout           = item["layout"]               # layout JSON (or None if not on disk)
    annotation       = item["annotation"]           # per-layout annotation (or None)
    template_ann     = item["template_annotation"]  # template-level annotation (or None)
    image_path       = item["image_path"]           # Path object
```

### Module-level convenience functions

```python
from lica_dataset import (
    load_dataset,
    load_layouts_by_template,
    load_layouts_by_category,
    iter_template_groups,
)

# Load the dataset (shorthand)
ds = load_dataset("lica-data")

# All layout JSONs for a template, sorted by template_layout_index
layouts = load_layouts_by_template("lica-data", "3b919d2e-539f-4b2c-8d86-7709ef65b496")

# All layout JSONs for a category (only those on disk)
presentation_layouts = load_layouts_by_category("lica-data", "Presentations")

# Iterate over template groups
for template_id, group in iter_template_groups("lica-data"):
    print(template_id, len(group))
```

---

## API reference

### `LicaDataset`

#### Constructor

| Signature | Description |
|---|---|
| `LicaDataset(data_root)` | Load the dataset from *data_root* |

#### Filtering methods (return a new `LicaDataset` view)

| Method | Description |
|---|---|
| `.by_category(category)` | Filter by design category (e.g. `"Presentations"`) |
| `.by_template(template_id)` | All layouts sharing a template UUID |
| `.by_dimensions(width, height)` | Filter by exact canvas dimensions (px) |
| `.by_aspect_ratio(ratio)` | Filter by `"landscape"`, `"portrait"`, or `"square"` |

#### Data access methods

| Method | Returns | Description |
|---|---|---|
| `.get_layout(layout_id)` | `dict` | Layout JSON from `layouts/<template_id>/<layout_id>.json` |
| `.get_annotation(layout_id)` | `dict` | Per-layout annotation from `annotations/<template_id>/<layout_id>.json` |
| `.get_template_annotation(template_id)` | `dict` | Template-level annotation from `template_annotations.json` |
| `.get_image_path(layout_id)` | `Path` | Path to `images/<template_id>/<layout_id>.png` |
| `.get_metadata(layout_id)` | `dict` | One metadata row as a dict |

#### Properties

| Property | Type | Description |
|---|---|---|
| `.ids` | `list[str]` | Layout IDs in the current view |
| `.metadata` | `pd.DataFrame` | Copy of the filtered metadata DataFrame |
| `.categories` | `list[str]` | Sorted unique categories |
| `.templates` | `list[str]` | Unique template IDs |

#### Other

| Method | Returns | Description |
|---|---|---|
| `len(ds)` | `int` | Number of layouts in the current view |
| `ds[idx]` | `dict` | Fully-loaded item at integer index |
| `iter(ds)` | iterator | Iterate over all items in the view |
| `.summary()` | `pd.DataFrame` | Grouped summary by category |

### Module-level functions

| Function | Description |
|---|---|
| `load_dataset(data_root)` | Shorthand for `LicaDataset(data_root)` |
| `load_layouts_by_template(data_root, template_id)` | List of layout dicts for a template, sorted by index |
| `load_layouts_by_category(data_root, category)` | List of layout dicts for a category (on-disk only) |
| `iter_template_groups(data_root)` | Yields `(template_id, LicaDataset)` for each template |

## License

This project is licensed under the Creative Commons Attribution 4.0 International License.

[![CC BY 4.0](https://licensebuttons.net/l/by/4.0/88x31.png)](https://creativecommons.org/licenses/by/4.0/)