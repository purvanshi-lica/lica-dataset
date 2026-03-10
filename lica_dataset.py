"""
LICA Dataset — Python helpers for loading and filtering layout data.

Usage:
    from lica_dataset import LicaDataset

    ds = LicaDataset("lica-data")
    print(ds)                           # LicaDataset(n=10, ...)

    # Filtering — each method returns a new LicaDataset view
    presentations = ds.by_category("presentation")
    train_siblings = ds.by_split("train").by_source_type("sibling")
    template_group = ds.by_template("dd7fbc1e-dd42-40f0-b2eb-7e50afbaf40f")

    # Data access
    layout = ds.get_layout("7Kj9aANwaYqCftO5LwO1")
    annotation = ds.get_annotation("7Kj9aANwaYqCftO5LwO1")
    img_path = ds.get_image_path("7Kj9aANwaYqCftO5LwO1")

    # Iteration
    for item in ds:
        print(item["id"], item["metadata"]["sub_category"])
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pandas as pd


class LicaDataset:
    """
    Interface for the LICA layout dataset.

    Wraps ``metadata.csv`` and ``layout_annotation.json`` into a Pandas-backed
    object with chainable filter methods and lazy layout-JSON loading.

    Parameters
    ----------
    data_root:
        Path to the root data directory that contains ``metadata.csv``,
        ``layout_annotation.json``, ``layouts/``, and ``images/``.

    Examples
    --------
    >>> ds = LicaDataset("lica-data")
    >>> ds.by_category("presentation").by_split("train")
    LicaDataset(n=..., categories=['presentation'], splits=['train'])
    """

    def __init__(self, data_root: str | Path) -> None:
        self._root = Path(data_root)
        self._annotations: dict[str, dict] = self._load_annotations()
        self._meta: pd.DataFrame = self._load_metadata()

    # ------------------------------------------------------------------
    # Internal construction helpers
    # ------------------------------------------------------------------

    def _load_metadata(self) -> pd.DataFrame:
        csv_path = self._root / "metadata.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"metadata.csv not found at {csv_path}")
        df = pd.read_csv(csv_path, dtype=str)
        # Derive parent category from the first segment of sub_category.
        # e.g. "flyers-funny" → "flyers", "presentation-new" → "presentation",
        # "grade10" → "grade10" (no hyphen → use as-is).
        df["category"] = df["sub_category"].str.split("-").str[0]
        # Numeric columns
        for col in ("n_template_layouts", "template_layout_index", "width", "height"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.reset_index(drop=True)

    def _load_annotations(self) -> dict[str, dict]:
        ann_path = self._root / "layout_annotation.json"
        if not ann_path.exists():
            raise FileNotFoundError(
                f"layout_annotation.json not found at {ann_path}"
            )
        with ann_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @classmethod
    def _from_state(
        cls,
        root: Path,
        meta: pd.DataFrame,
        annotations: dict[str, dict],
    ) -> LicaDataset:
        """Create a new view without reloading files from disk."""
        obj = cls.__new__(cls)
        obj._root = root
        obj._meta = meta.reset_index(drop=True)
        obj._annotations = annotations
        return obj

    def _filter(self, mask: pd.Series) -> LicaDataset:
        return LicaDataset._from_state(self._root, self._meta[mask], self._annotations)

    # ------------------------------------------------------------------
    # Filtering — each method returns a new LicaDataset view
    # ------------------------------------------------------------------

    def by_category(self, category: str) -> LicaDataset:
        """
        Filter by derived parent category.

        The parent category is the prefix before the first ``-`` in
        ``sub_category`` (e.g. ``"flyers"`` matches ``"flyers-funny"`` and
        ``"flyers-picture"``).

        Parameters
        ----------
        category:
            Parent category string (case-sensitive).
        """
        return self._filter(self._meta["category"] == category)

    def by_sub_category(self, sub_category: str) -> LicaDataset:
        """
        Filter by exact ``sub_category`` value from ``metadata.csv``.

        Parameters
        ----------
        sub_category:
            E.g. ``"flyers-funny"``, ``"presentation-new"``.
        """
        return self._filter(self._meta["sub_category"] == sub_category)

    def by_template(self, template_id: str) -> LicaDataset:
        """
        Return all layouts that belong to the same template.

        Parameters
        ----------
        template_id:
            UUID string from the ``template_id`` column.
        """
        return self._filter(self._meta["template_id"] == template_id)

    def by_split(self, split: str) -> LicaDataset:
        """
        Filter by dataset split.

        Parameters
        ----------
        split:
            ``"train"`` or ``"test"``.
        """
        return self._filter(self._meta["split"] == split)

    def by_source_type(self, source_type: str) -> LicaDataset:
        """
        Filter by layout source type.

        Parameters
        ----------
        source_type:
            ``"sibling"`` — one of several layouts from the same template.
            ``"coverage"`` — the single representative layout for a template.
        """
        return self._filter(self._meta["source_type"] == source_type)

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

        Supported ratio strings
        -----------------------
        ``"landscape"``  — width > height (e.g. 1920×1080)
        ``"portrait"``   — height > width (e.g. 1080×1920)
        ``"square"``     — width == height (e.g. 1080×1080)

        Parameters
        ----------
        ratio:
            One of ``"landscape"``, ``"portrait"``, ``"square"``.
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

        The layout dict contains:
        - ``components`` — list of TEXT, IMAGE, or GROUP elements
        - ``background`` — CSS color string
        - ``width`` / ``height`` — canvas size with ``"px"`` suffix
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
        path = self._root / "layouts" / f"{layout_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Layout JSON not found: {path}")
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)

    def get_annotation(self, layout_id: str) -> dict:
        """
        Return the annotation dict for a given layout ID.

        The annotation dict contains:
        - ``description`` — visual description of the layout
        - ``aesthetics`` — notes on design style
        - ``tags`` — comma-separated tag string
        - ``user_intent`` — inferred purpose of the design

        Parameters
        ----------
        layout_id:
            The layout ID.

        Raises
        ------
        KeyError
            If the ID has no entry in ``layout_annotation.json``.
        """
        if layout_id not in self._annotations:
            raise KeyError(f"No annotation found for ID: {layout_id!r}")
        return self._annotations[layout_id]

    def get_image_path(self, layout_id: str) -> Path:
        """
        Return the ``Path`` to the PNG image for a given layout ID.

        Note: the image file may not exist if the images folder has not been
        populated yet.

        Parameters
        ----------
        layout_id:
            The layout ID.
        """
        return self._root / "images" / f"{layout_id}.png"

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
        row = self._meta[self._meta["id"] == layout_id]
        if row.empty:
            raise KeyError(
                f"ID {layout_id!r} not found in current view. "
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
        Return a fully-loaded item dict for the layout at integer index ``idx``.

        The returned dict contains:
        - ``id`` — layout ID string
        - ``metadata`` — dict of all CSV fields plus derived ``category``
        - ``layout`` — layout JSON dict loaded from disk
        - ``annotation`` — annotation dict (or ``None`` if missing)
        - ``image_path`` — ``Path`` to the PNG (may not exist yet)
        """
        if idx < 0 or idx >= len(self._meta):
            raise IndexError(
                f"Index {idx} out of range for dataset of size {len(self._meta)}."
            )
        row = self._meta.iloc[idx]
        layout_id: str = row["id"]
        return {
            "id": layout_id,
            "metadata": row.to_dict(),
            "layout": self.get_layout(layout_id),
            "annotation": self._annotations.get(layout_id),
            "image_path": self.get_image_path(layout_id),
        }

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def ids(self) -> list[str]:
        """List of layout IDs in the current view."""
        return self._meta["id"].tolist()

    @property
    def metadata(self) -> pd.DataFrame:
        """
        A copy of the (filtered) metadata DataFrame.

        Columns: ``id``, ``sub_category``, ``category``, ``template_id``,
        ``source_type``, ``n_template_layouts``, ``template_layout_index``,
        ``width``, ``height``, ``split``, ``n_video_slides``.
        """
        return self._meta.copy()

    @property
    def categories(self) -> list[str]:
        """Sorted list of unique parent categories in the current view."""
        return sorted(self._meta["category"].dropna().unique().tolist())

    @property
    def sub_categories(self) -> list[str]:
        """Sorted list of unique sub_categories in the current view."""
        return sorted(self._meta["sub_category"].dropna().unique().tolist())

    @property
    def templates(self) -> list[str]:
        """List of unique template IDs in the current view."""
        return self._meta["template_id"].dropna().unique().tolist()

    @property
    def splits(self) -> list[str]:
        """List of unique splits present in the current view."""
        return self._meta["split"].dropna().unique().tolist()

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"LicaDataset("
            f"n={len(self)}, "
            f"categories={self.categories}, "
            f"splits={self.splits}"
            f")"
        )

    def summary(self) -> pd.DataFrame:
        """
        Return a summary DataFrame grouped by category and sub_category.

        Columns: ``category``, ``sub_category``, ``count``,
        ``source_types``, ``splits``.
        """
        grouped = (
            self._meta.groupby(["category", "sub_category"], sort=True)
            .agg(
                count=("id", "count"),
                source_types=("source_type", lambda x: sorted(x.unique().tolist())),
                splits=("split", lambda x: sorted(x.unique().tolist())),
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

    This is a convenience wrapper around ``LicaDataset(data_root)``.

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
    Load all layout JSON dicts that share a given template ID.

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
    return [ds.get_layout(lid) for lid in ordered["id"]]


def load_layouts_by_category(
    data_root: str | Path,
    category: str,
) -> list[dict]:
    """
    Load all layout JSON dicts for a given parent category.

    Parameters
    ----------
    data_root:
        Path to the root data directory.
    category:
        Parent category string (e.g. ``"flyers"``, ``"presentation"``).

    Returns
    -------
    list[dict]
        List of layout dicts for the given category.
    """
    ds = LicaDataset(data_root).by_category(category)
    return [ds.get_layout(lid) for lid in ds.ids]


def load_annotations_by_category(
    data_root: str | Path,
    category: str,
) -> list[dict]:
    """
    Load all annotation dicts for a given parent category.

    Parameters
    ----------
    data_root:
        Path to the root data directory.
    category:
        Parent category string.

    Returns
    -------
    list[dict]
        List of annotation dicts, each including the ``id`` field.
    """
    ds = LicaDataset(data_root).by_category(category)
    return [
        {"id": lid, **ds.get_annotation(lid)}
        for lid in ds.ids
        if lid in ds._annotations
    ]


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
            group._annotations,
        )
