"""Unit tests for subframe grid geometry."""

from __future__ import annotations

import numpy as np

from valiant.autonomy.cv.subframe_grid import (
    convert_to_cropped_coords,
    crop_to_grid,
    get_spiral_order,
    grid_crop_bounds,
    to_full_frame,
)


def test_crop_to_grid_centers_720p():
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    cropped, top, left = crop_to_grid(frame, 294)
    assert cropped.shape == (588, 1176, 3)
    assert top == 66
    assert left == 52


def test_coord_remap_round_trip():
    size = 294
    top_off, left_off = 66, 52
    tile_bbox = [40.0, 50.0, 120.0, 180.0]
    r, c = 1, 2
    cropped_bbox = convert_to_cropped_coords(tile_bbox, r, c, size)
    assert cropped_bbox == [40 + 2 * size, 50 + size, 120 + 2 * size, 180 + size]
    full_bbox = to_full_frame(cropped_bbox, top_off, left_off)
    assert full_bbox == [b + (left_off if i % 2 == 0 else top_off) for i, b in enumerate(cropped_bbox)]


def test_grid_crop_bounds_matches_crop_to_grid():
    w, h = 1280, 720
    left, top, right, bottom = grid_crop_bounds(w, h, 294)
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    _, t, l = crop_to_grid(frame, 294)
    assert (left, top) == (l, t)
    assert right - left == (w // 294) * 294
    assert bottom - top == (h // 294) * 294


def test_spiral_order_starts_near_center():
    order = get_spiral_order(3, 4)
    assert order[0] == (1, 1) or order[0] == (1, 2)
