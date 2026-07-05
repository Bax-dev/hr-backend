import math

EARTH_RADIUS_METERS = 6_371_000


def haversine_distance_meters(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = (float(lat1), float(lng1), float(lat2), float(lng2))
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(h))


def format_distance_meters(meters):
    if meters < 1000:
        return f'{round(meters)} m'
    return f'{meters / 1000:.1f} km'
