"""
LICA Dataset — Python helpers for loading and filtering layout data.

Usage:
    from lica_dataset import LicaDataset

    ds = LicaDataset("lica-data")
    print(ds)

    # Filtering — each method returns a new LicaDataset view
    presentations = ds.by_category("Presentations")
    template_group = ds.by_template("3b919d2e-539f-4b2c-8d86-7709ef65b496")

    # Data access
    layout = ds.get_layout("gsessHF2ev5r4ZgwPUh5")
    annotation = ds.get_annotation("gsessHF2ev5r4ZgwPUh5")
    img_path = ds.get_image_path("gsessHF2ev5r4ZgwPUh5")

    # Iteration
    for item in ds:
        print(item["layout_id"], item["metadata"]["category"])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pandas as pd


class LicaDataset:
    """
    Interface for the LICA layout dataset.

    Wraps ``metadata.csv`` and the template-organized ``layouts/``,
    ``images/``, and ``annotations/`` folders into a Pandas-backed object
    with chainable filter methods and lazy file loading.

    Parameters
    ----------
    data_root:
        Path to the root data directory containing ``metadata.csv``,
        ``layouts/``, ``images/``, and ``annotations/``.
    """

    def __init__(self, data_root: str | Path) -> None:
        self._root = Path(data_root)
        self._meta: pd.DataFrame = self._load_metadata()
        self._template_annotations: dict[str, dict] = self._load_template_annotations()

    # ------------------------------------------------------------------
    # Internal construction helpers
    # ------------------------------------------------------------------

    def _load_metadata(self) -> pd.DataFrame:
        csv_path = self._root / "metadata.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"metadata.csv not found at {csv_path}")
        df = pd.read_csv(csv_path, dtype=str)
        for col in ("n_template_layouts", "template_layout_index", "width", "height"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.reset_index(drop=True)

    def _load_template_annotations(self) -> dict[str, dict]:
        ann_path = self._root / "annotations" / "template_annotations.json"
        if not ann_path.exists():
            return {}
        with ann_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @classmethod
    def _from_state(
        cls,
        root: Path,
        meta: pd.DataFrame,
        template_annotations: dict[str, dict],
    ) -> LicaDataset:
        """Create a new view without reloading files from disk."""
        obj = cls.__new__(cls)
        obj._root = root
        obj._meta = meta.reset_index(drop=True)
        obj._template_annotations = template_annotations
        return obj

    def _filter(self, mask: pd.Series) -> LicaDataset:
        return LicaDataset._from_state(
            self._root, self._meta[mask], self._template_annotations
        )

    def _resolve_template_id(self, layout_id: str) -> str:
        """Look up the template_id for a layout_id from the metadata."""
        row = self._meta[self._meta["layout_id"] == layout_id]
        if row.empty:
            raise KeyError(
                f"layout_id {layout_id!r} not found in current view. "
                "Use the full dataset if filtering has excluded it."
            )
        return row.iloc[0]["template_id"]

    # ------------------------------------------------------------------
    # Filtering — each method returns a new LicaDataset view
    # ------------------------------------------------------------------

    def by_category(self, category: str) -> LicaDataset:
        """
        Filter by design category.

        Parameters
        ----------
        category:
            Category string (case-sensitive), e.g. ``"Presentations"``,
            ``"Videos"``, ``"Education"``, ``"Flyers"``.
        """
        return self._filter(self._meta["category"] == category)

    def by_template(self, template_id: str) -> LicaDataset:
        """
        Return all layouts that belong to the same template.

        Parameters
        ----------
        template_id:
            UUID string from the ``template_id`` column.
        """
        return self._filter(self._meta["template_id"] == template_id)

    def by_dimensions(self, width: int, height: int) -> LicaDataset:
        """
        Filter layouts that exactly match the given canvas dimensions.

        Parameters
        ----------
        width:
            Canvas width in pixels.
        height:
            Canvas height in pixels.
        """
        mask = (self._meta["width"] == width) & (self._meta["height"] == height)
        return self._filter(mask)

    def by_aspect_ratio(self, ratio: str) -> LicaDataset:
        """
        Filter layouts by a named aspect ratio.

        Parameters
        ----------
        ratio:
            One of ``"landscape"`` (width > height), ``"portrait"``
            (height > width), or ``"square"`` (width == height).
        """
        w = self._meta["width"]
        h = self._meta["height"]
        if ratio == "landscape":
            return self._filter(w > h)
        if ratio == "portrait":
            return self._filter(h > w)
        if ratio == "square":
            return self._filter(w == h)
        raise ValueError(
            f"Unknown ratio '{ratio}'. Choose from 'landscape', 'portrait', 'square'."
        )

    # ------------------------------------------------------------------
    # Data access — load individual records by ID
    # ------------------------------------------------------------------

    def get_layout(self, layout_id: str) -> dict:
        """
        Load and return the layout JSON for a given ID.

        The returned dict always contains:
        - ``components`` — flat list of TEXT, IMAGE, or GROUP elements
        - ``width`` / ``height`` — canvas size (e.g. ``"1920px"``)

        Optional keys (present in most layouts):
        - ``background`` — CSS color string
        - ``duration`` — slide duration in seconds

        Parameters
        ----------
        layout_id:
            The layout ID (filename without ``.json``).

        Raises
        ------
        FileNotFoundError
            If the layout JSON file does not exist on disk.
        """
        template_id = self._resolve_template_id(layout_id)
        path = self._root / "layouts" / template_id / f"{layout_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Layout JSON not found: {path}")
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def get_annotation(self, layout_id: str) -> dict:
        """
        Load and return the per-layout annotation dict.

        The annotation dict contains:
        ``description``, ``aesthetics``, ``tags``, ``user_intent``, ``raw``.

        Parameters
        ----------
        layout_id:
            The layout ID.

        Raises
        ------
        FileNotFoundError
            If the annotation file does not exist on disk.
        """
        template_id = self._resolve_template_id(layout_id)
        path = self._root / "annotations" / template_id / f"{layout_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Annotation not found: {path}")
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def get_template_annotation(self, template_id: str) -> dict:
        """
        Return the template-level annotation dict.

        Template annotations describe the overall design theme shared by all
        layouts in a template group. Fields: ``description``, ``aesthetics``,
        ``tags``, ``user_intent``, ``raw``.

        Parameters
        ----------
        template_id:
            The template UUID.

        Raises
        ------
        KeyError
            If the template has no entry in ``template_annotations.json``.
        """
        if template_id not in self._template_annotations:
            raise KeyError(
                f"No template annotation found for: {template_id!r}"
            )
        return self._template_annotations[template_id]

    def get_render_path(self, layout_id: str) -> Path:
        """
        Return the ``Path`` to the rendered file (PNG or MP4) for a layout.

        Checks for ``.png`` first, then ``.mp4``. Returns whichever exists.
        If neither exists, returns the ``.png`` path as a default.

        Parameters
        ----------
        layout_id:
            The layout ID.
        """
        template_id = self._resolve_template_id(layout_id)
        base = self._root / "images" / template_id / layout_id
        png = base.with_suffix(".png")
        if png.exists():
            return png
        mp4 = base.with_suffix(".mp4")
        if mp4.exists():
            return mp4
        return png

    def get_image_path(self, layout_id: str) -> Path:
        """
        Alias for :meth:`get_render_path` (kept for backward compatibility).
        """
        return self.get_render_path(layout_id)

    def get_metadata(self, layout_id: str) -> dict:
        """
        Return a single metadata row as a plain dict.

        Parameters
        ----------
        layout_id:
            The layout ID to look up within the current view.

        Raises
        ------
        KeyError
            If the ID is not present in the current view.
        """
        row = self._meta[self._meta["layout_id"] == layout_id]
        if row.empty:
            raise KeyError(
                f"layout_id {layout_id!r} not found in current view. "
                "Use the full dataset if filtering has excluded it."
            )
        return row.iloc[0].to_dict()

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._meta)

    def __iter__(self) -> Iterator[dict]:
        for idx in range(len(self)):
            yield self[idx]

    def __getitem__(self, idx: int) -> dict:
        """
        Return a fully-loaded item dict for the layout at integer index.

        The returned dict contains:
        - ``layout_id`` — layout ID string
        - ``template_id`` — template UUID
        - ``metadata`` — dict of all CSV fields
        - ``layout`` — full layout JSON dict loaded from disk
        - ``annotation`` — per-layout annotation dict (or ``None``)
        - ``template_annotation`` — template-level annotation (or ``None``)
        - ``render_path`` — ``Path`` to the render (PNG or MP4)
        - ``image_path`` — alias for ``render_path``
        """
        if idx < 0 or idx >= len(self._meta):
            raise IndexError(
                f"Index {idx} out of range for dataset of size {len(self._meta)}."
            )
        row = self._meta.iloc[idx]
        layout_id: str = row["layout_id"]
        template_id: str = row["template_id"]

        # Lazily load layout — only if the file exists on disk
        layout_path = self._root / "layouts" / template_id / f"{layout_id}.json"
        layout = None
        if layout_path.exists():
            with layout_path.open(encoding="utf-8") as fh:
                layout = json.load(fh)

        # Lazily load annotation
        ann_path = self._root / "annotations" / template_id / f"{layout_id}.json"
        annotation = None
        if ann_path.exists():
            with ann_path.open(encoding="utf-8") as fh:
                annotation = json.load(fh)

        # Resolve render path (PNG or MP4)
        base = self._root / "images" / template_id / layout_id
        render = base.with_suffix(".png")
        if not render.exists():
            mp4 = base.with_suffix(".mp4")
            if mp4.exists():
                render = mp4

        return {
            "layout_id": layout_id,
            "template_id": template_id,
            "metadata": row.to_dict(),
            "layout": layout,
            "annotation": annotation,
            "template_annotation": self._template_annotations.get(template_id),
            "render_path": render,
            "image_path": render,
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def ids(self) -> list[str]:
        """List of layout IDs in the current view."""
        return self._meta["layout_id"].tolist()

    @property
    def metadata(self) -> pd.DataFrame:
        """
        A copy of the (filtered) metadata DataFrame.

        Columns: ``layout_id``, ``category``, ``template_id``,
        ``n_template_layouts``, ``template_layout_index``, ``width``,
        ``height``.
        """
        return self._meta.copy()

    @property
    def categories(self) -> list[str]:
        """Sorted list of unique categories in the current view."""
        return sorted(self._meta["category"].dropna().unique().tolist())

    @property
    def templates(self) -> list[str]:
        """List of unique template IDs in the current view."""
        return self._meta["template_id"].dropna().unique().tolist()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"LicaDataset("
            f"n={len(self)}, "
            f"categories={self.categories}"
            f")"
        )

    def summary(self) -> pd.DataFrame:
        """
        Return a summary DataFrame grouped by category.

        Columns: ``category``, ``n_layouts``, ``n_templates``,
        ``dimensions``.
        """
        grouped = (
            self._meta.groupby("category", sort=True)
            .agg(
                n_layouts=("layout_id", "count"),
                n_templates=("template_id", "nunique"),
                dimensions=(
                    "width",
                    lambda x: sorted(
                        set(
                            zip(
                                x.values,
                                self._meta.loc[x.index, "height"].values,
                            )
                        )
                    ),
                ),
            )
            .reset_index()
        )
        return grouped


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def load_dataset(data_root: str | Path = "lica-data") -> LicaDataset:
    """
    Load the LICA dataset from *data_root* and return a :class:`LicaDataset`.

    Parameters
    ----------
    data_root:
        Path to the root data directory. Defaults to ``"lica-data"``.
    """
    return LicaDataset(data_root)


def load_layouts_by_template(
    data_root: str | Path,
    template_id: str,
) -> list[dict]:
    """
    Load all layout JSON dicts that share a given template ID,
    sorted by ``template_layout_index``.

    Parameters
    ----------
    data_root:
        Path to the root data directory.
    template_id:
        The template UUID to filter by.

    Returns
    -------
    list[dict]
        List of layout dicts, ordered by ``template_layout_index``.
    """
    ds = LicaDataset(data_root).by_template(template_id)
    ordered = ds.metadata.sort_values("template_layout_index")
    return [ds.get_layout(lid) for lid in ordered["layout_id"]]


def load_layouts_by_category(
    data_root: str | Path,
    category: str,
) -> list[dict]:
    """
    Load all layout JSON dicts for a given category.

    Only loads layouts whose JSON files exist on disk.

    Parameters
    ----------
    data_root:
        Path to the root data directory.
    category:
        Category string (e.g. ``"Presentations"``).

    Returns
    -------
    list[dict]
        List of layout dicts for the given category.
    """
    ds = LicaDataset(data_root).by_category(category)
    layouts = []
    for lid in ds.ids:
        try:
            layouts.append(ds.get_layout(lid))
        except FileNotFoundError:
            continue
    return layouts


def iter_template_groups(
    data_root: str | Path,
) -> Iterator[tuple[str, LicaDataset]]:
    """
    Iterate over all template groups in the dataset.

    Yields ``(template_id, view)`` tuples where *view* is a
    :class:`LicaDataset` containing only the layouts for that template,
    sorted by ``template_layout_index``.

    Parameters
    ----------
    data_root:
        Path to the root data directory.
    """
    ds = LicaDataset(data_root)
    for tid in ds.templates:
        group = ds.by_template(tid)
        sorted_meta = group.metadata.sort_values("template_layout_index")
        yield tid, LicaDataset._from_state(
            group._root,
            sorted_meta,
            group._template_annotations,
        )
