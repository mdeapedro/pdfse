def point_to_segment_squared_distance(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float]
) -> float:
    ab_x = b[0] - a[0]
    ab_y = b[1] - a[1]
    ap_x = p[0] - a[0]
    ap_y = p[1] - a[1]
    ab_dot_ab = ab_x**2 + ab_y**2
    if ab_dot_ab == 0:
        return ap_x**2 + ap_y**2
    proj = (ab_x * ap_x + ab_y * ap_y) / ab_dot_ab
    if proj < 0:
        closest_x = a[0]
        closest_y = a[1]
    elif proj > 1:
        closest_x = b[0]
        closest_y = b[1]
    else:
        closest_x = a[0] + proj * ab_x
        closest_y = a[1] + proj * ab_y
    dx = p[0] - closest_x
    dy = p[1] - closest_y
    return dx**2 + dy**2


def point_to_bbox_squared_distance(
    p: tuple[float, float],
    bbox: tuple[float, float, float, float]
) -> float:
    min_x, min_y, max_x, max_y = bbox
    x, y = p
    if min_x <= x <= max_x and min_y <= y <= max_y:
        return 0.0
    left_a = (min_x, min_y)
    left_b = (min_x, max_y)
    right_a = (max_x, min_y)
    right_b = (max_x, max_y)
    bottom_a = (min_x, min_y)
    bottom_b = (max_x, min_y)
    top_a = (min_x, max_y)
    top_b = (max_x, max_y)
    dist_sq_left = point_to_segment_squared_distance(p, left_a, left_b)
    dist_sq_right = point_to_segment_squared_distance(p, right_a, right_b)
    dist_sq_bottom = point_to_segment_squared_distance(p, bottom_a, bottom_b)
    dist_sq_top = point_to_segment_squared_distance(p, top_a, top_b)
    min_dist_sq = min(dist_sq_left, dist_sq_right, dist_sq_bottom, dist_sq_top)
    return min_dist_sq
