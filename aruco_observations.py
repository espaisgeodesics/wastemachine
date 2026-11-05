"""Convert OpenCV ArUco output to observations, without triggering card actions."""
from math import atan2, tau
from numbers import Integral
from marker_tracking import MarkerObservation, ObservationFrame


def observation_frame(corners, ids, image_size, source_id, sequence, captured_at):
    width, height = image_size
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError('Expected original image width and height')
    if ids is None:
        if corners is not None and len(corners):
            raise ValueError('Marker corners without IDs')
        return ObservationFrame(source_id, sequence, captured_at)
    raw_ids = tuple(ids.flatten())
    if len(raw_ids) != len(corners):
        raise ValueError('ArUco ID/corner count mismatch')
    observations = []
    for points, raw in zip(corners, raw_ids):
        if isinstance(raw, bool) or not isinstance(raw, Integral) or raw < 0:
            raise ValueError('Invalid detector ID')
        marker = int(raw)
        if marker >= 16:
            continue  # Same supported subset as Wasteland; dictionary has 50 IDs.
        p = points[0]
        if len(p) != 4 or any(len(point) != 2 for point in p):
            raise ValueError('Invalid marker corner geometry')
        normalized = tuple((float(point[0])/width, float(point[1])/height) for point in p)
        center = (float(p[:, 0].mean()/width), float(p[:, 1].mean()/height))
        dx = p[1]-p[0]
        angle = (atan2(float(dx[1]), float(dx[0])) % tau)/tau
        observations.append(MarkerObservation(marker, center, angle, normalized))
    return ObservationFrame(source_id, sequence, captured_at, tuple(observations))
