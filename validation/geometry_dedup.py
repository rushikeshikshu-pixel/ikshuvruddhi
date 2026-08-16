"""
validation/geometry_dedup.py
Cadastral Geometry Deduplication & Shared Land Unit Clustering
Identifies exact duplicate and near-identical cadastral parcel polygons.
"""

from typing import List, Dict, Any, Tuple
from shapely.geometry import Polygon

def find_duplicate_and_overlapping_polygons(
    parcels: List[Dict[str, Any]],
    iou_exact_threshold: float = 0.98
) -> Dict[str, Any]:
    """
    Groups parcels that share identical or near-identical physical geometries.
    
    Parameters:
      parcels: List of dicts with keys 'plot_no', 'polygon' (Shapely Polygon), etc.
      iou_exact_threshold: IoU threshold above which two parcels are marked as duplicate geometries.
      
    Returns:
      Dict with:
        - duplicate_groups: List of lists of plot numbers sharing geometries.
        - plot_to_group_id: Mapping of plot_no -> group_id
        - duplicate_plots_count: Total number of duplicate entries
        - unique_physical_plots_count: Total physical land units
    """
    n = len(parcels)
    parent = list(range(n))

    def find(i):
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    # Compute pairwise IoU
    for i in range(n):
        poly_i = parcels[i].get("polygon")
        if poly_i is None or not poly_i.is_valid or poly_i.is_empty:
            continue
        for j in range(i + 1, n):
            poly_j = parcels[j].get("polygon")
            if poly_j is None or not poly_j.is_valid or poly_j.is_empty:
                continue

            # Quick bounding box reject
            if not poly_i.envelope.intersects(poly_j.envelope):
                continue

            inter_area = poly_i.intersection(poly_j).area
            union_area = poly_i.union(poly_j).area
            if union_area > 0:
                iou = inter_area / union_area
                if iou >= iou_exact_threshold:
                    union(i, j)

    # Group by roots
    groups: Dict[int, List[int]] = {}
    for i in range(n):
        r = find(i)
        if r not in groups:
            groups[r] = []
        groups[r].append(i)

    duplicate_groups = []
    plot_to_group_id = {}
    
    for g_id, member_indices in enumerate(groups.values()):
        member_plots = [parcels[idx]["plot_no"] for idx in member_indices]
        for p_no in member_plots:
            plot_to_group_id[p_no] = g_id
        if len(member_plots) > 1:
            duplicate_groups.append(member_plots)

    return {
        "duplicate_groups": duplicate_groups,
        "plot_to_group_id": plot_to_group_id,
        "duplicate_plots_count": sum(len(g) - 1 for g in duplicate_groups),
        "unique_physical_plots_count": len(groups),
        "total_records_count": n
    }