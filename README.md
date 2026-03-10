# LICA Dataset

The **LICA dataset** is a collection of graphic design layouts produced with the LICA platform. Each layout captures the complete rendering specification of a design — component positions, typography, images, and background — alongside rich natural-language annotations and structured metadata.

## Dataset structure

```
lica-data/
├── images/                    # <id>.png — rendered layout images
├── layouts/                   # <id>.json — component-level layout JSON
├── metadata.csv               # per-layout metadata (category, template, split, …)
└── layout_annotation.json     # per-layout text annotations
```

### `metadata.csv`

| Column | Type | Description |
|---|---|---|
| `id` | string | Unique layout ID (matches filename in `layouts/` and `images/`) |
| `sub_category` | string | Fine-grained design category (e.g. `"flyers-funny"`, `"presentation-new"`) |
| `template_id` | string | UUID of the template this layout was generated from |
| `source_type` | string | `"sibling"` — one of several layouts from a template · `"coverage"` — representative single layout |
| `n_template_layouts` | int | Total number of layouts in the template group |
| `template_layout_index` | int | Zero-based position of this layout within its template group |
| `width` | int | Canvas width in pixels |
| `height` | int | Canvas height in pixels |
| `split` | string | Dataset split: `"train"` or `"test"` |
| `n_video_slides` | int | Number of slides in the source video (if applicable) |

### `layout_annotation.json`

A JSON object keyed by layout ID. Each entry contains:

| Field | Description |
|---|---|
| `description` | Visual description of the layout (objects, text content, colors) |
| `aesthetics` | Notes on the design style, composition, and visual hierarchy |
| `tags` | Comma-separated keyword tags |
| `user_intent` | Inferred purpose or goal of the design |

### Layout JSON (`layouts/<id>.json`)

Each layout file describes a fully-specified canvas:

| Field | Type | Description |
|---|---|---|
| `background` | string | CSS color for the canvas background |
| `width` | string | Canvas width with `"px"` suffix |
| `height` | string | Canvas height with `"px"` suffix |
| `duration` | number | Slide duration in seconds |
| `components` | array | Ordered list of rendering components |

#### Component types

**`TEXT`**

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

**`IMAGE`**

```json
{
  "type": "IMAGE",
  "src": "https://storage.googleapis.com/lica-video/<uuid>.png",
  "alt": "Description of the image",
  "left": "0px", "top": "0px", "width": "1920px", "height": "1080px",
  "opacity": 1,
  "overflow": "hidden",
  "transform": "none"
}
```

**`GROUP`** — clipping container, often used to render shapes or borders via an SVG clip path

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

---

## Installation

```bash
pip install -r requirements.txt
```

Python 3.9 or later is required.

---

## Quick start

```python
from lica_dataset import LicaDataset

ds = LicaDataset("lica-data")
print(ds)
# LicaDataset(n=10, categories=['business', 'flyers', 'grade10', ...], splits=['train'])
```

### Inspect available categories and metadata

```python
# Parent categories derived from sub_category (prefix before the first "-")
print(ds.categories)
# ['business', 'flyers', 'grade10', 'InstgramPost', 'presentation']

print(ds.sub_categories)
# ['InstgramPost-corporate', 'business-cards-texture', 'flyers-funny', ...]

# Full metadata as a Pandas DataFrame
print(ds.metadata.head())

# Per-category summary
print(ds.summary())
```

### Filter layouts

Filtering methods return a new `LicaDataset` view — they are chainable.

```python
# All presentation layouts in the training split
train_presentations = ds.by_category("presentation").by_split("train")
print(len(train_presentations))

# All sibling layouts from a specific template
template_layouts = ds.by_template("dd7fbc1e-dd42-40f0-b2eb-7e50afbaf40f")
print(template_layouts.metadata[["id", "template_layout_index"]].sort_values("template_layout_index"))

# Layouts with a specific sub_category
funny_flyers = ds.by_sub_category("flyers-funny")

# Filter by canvas dimensions
widescreen = ds.by_dimensions(1920, 1080)

# Filter by aspect ratio
portrait_layouts = ds.by_aspect_ratio("portrait")   # height > width
landscape_layouts = ds.by_aspect_ratio("landscape")  # width > height
square_layouts = ds.by_aspect_ratio("square")        # width == height
```

### Access individual records

```python
layout_id = "7Kj9aANwaYqCftO5LwO1"

# Load the layout JSON
layout = ds.get_layout(layout_id)
print(layout["background"])           # "rgb(131, 141, 212)"
print(len(layout["components"]))      # number of components

# Load the annotation
annotation = ds.get_annotation(layout_id)
print(annotation["tags"])

# Path to the rendered image (may not exist if images are not yet downloaded)
img_path = ds.get_image_path(layout_id)
print(img_path)   # lica-data/images/7Kj9aANwaYqCftO5LwO1.png

# Single metadata row as a dict
meta = ds.get_metadata(layout_id)
print(meta["sub_category"])   # "InstgramPost-corporate"
```

### Iterate over all items

`__getitem__` returns a fully-loaded dict for each layout:

```python
for item in ds:
    layout_id   = item["id"]
    metadata    = item["metadata"]   # dict of CSV fields + derived "category"
    layout      = item["layout"]     # layout JSON dict
    annotation  = item["annotation"] # annotation dict (or None)
    image_path  = item["image_path"] # Path object
```

### Module-level convenience functions

```python
from lica_dataset import (
    load_dataset,
    load_layouts_by_template,
    load_layouts_by_category,
    load_annotations_by_category,
    iter_template_groups,
)

# Load the dataset (shorthand)
ds = load_dataset("lica-data")

# All layout JSONs for a template, sorted by template_layout_index
layouts = load_layouts_by_template("lica-data", "dd7fbc1e-dd42-40f0-b2eb-7e50afbaf40f")

# All layout JSONs for a category
flyer_layouts = load_layouts_by_category("lica-data", "flyers")

# All annotations for a category (each dict includes the "id" key)
flyer_annotations = load_annotations_by_category("lica-data", "flyers")

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
| `.by_category(category)` | Filter by derived parent category |
| `.by_sub_category(sub_category)` | Filter by exact `sub_category` value |
| `.by_template(template_id)` | All layouts sharing a template UUID |
| `.by_split(split)` | Filter by `"train"` / `"test"` split |
| `.by_source_type(source_type)` | Filter by `"sibling"` or `"coverage"` |
| `.by_dimensions(width, height)` | Filter by exact canvas dimensions (px) |
| `.by_aspect_ratio(ratio)` | Filter by `"landscape"`, `"portrait"`, or `"square"` |

#### Data access methods

| Method | Returns | Description |
|---|---|---|
| `.get_layout(id)` | `dict` | Layout JSON loaded from `layouts/<id>.json` |
| `.get_annotation(id)` | `dict` | Annotation dict from `layout_annotation.json` |
| `.get_image_path(id)` | `Path` | Path to `images/<id>.png` |
| `.get_metadata(id)` | `dict` | One metadata row as a dict |

#### Properties

| Property | Type | Description |
|---|---|---|
| `.ids` | `list[str]` | Layout IDs in the current view |
| `.metadata` | `pd.DataFrame` | Copy of the filtered metadata DataFrame |
| `.categories` | `list[str]` | Sorted unique parent categories |
| `.sub_categories` | `list[str]` | Sorted unique sub_categories |
| `.templates` | `list[str]` | Unique template IDs |
| `.splits` | `list[str]` | Unique split values |

#### Other

| Method | Returns | Description |
|---|---|---|
| `len(ds)` | `int` | Number of layouts in the current view |
| `ds[idx]` | `dict` | Fully-loaded item at integer index |
| `iter(ds)` | iterator | Iterate over all items in the view |
| `.summary()` | `pd.DataFrame` | Grouped summary by category and sub_category |

### Module-level functions

| Function | Description |
|---|---|
| `load_dataset(data_root)` | Shorthand for `LicaDataset(data_root)` |
| `load_layouts_by_template(data_root, template_id)` | List of layout dicts for a template, sorted by index |
| `load_layouts_by_category(data_root, category)` | List of layout dicts for a parent category |
| `load_annotations_by_category(data_root, category)` | List of annotation dicts (with `"id"` key) for a category |
| `iter_template_groups(data_root)` | Yields `(template_id, LicaDataset)` for each template |
