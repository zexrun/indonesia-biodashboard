"""Utilitas GADM: konversi poligon → koordinat line trace."""


def gadm_to_latlons(gdf, simplify_tol=None):
    """
    GeoDataFrame poligon → (lats, lons) untuk trace Scattermap mode='lines'.

    Antar ring dipisah dengan None agar garis tidak menyambung.
    simplify_tol (derajat) dipakai untuk level detail tinggi (mis. Kab/Kota).
    """
    if simplify_tol:
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.simplify(simplify_tol, preserve_topology=True)

    lats, lons = [], []
    for geom in gdf.geometry:
        if geom is None:
            continue
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            xs, ys = poly.exterior.xy
            lons.extend(list(xs) + [None])
            lats.extend(list(ys) + [None])
    return lats, lons
