#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse, json
from xml.sax.saxutils import escape as xml_escape

def load_geojson(path):
    with open(path, 'r', encoding='utf-8') as f:
        gj = json.load(f)
    if gj.get('type') == 'FeatureCollection':
        return gj.get('features', [])
    if gj.get('type') == 'Feature':
        return [gj]
    return [{'type':'Feature','properties':{},'geometry':gj}]

def iter_polygons(geometry):
    gt = geometry.get('type'); cs = geometry.get('coordinates', [])
    if gt == 'Polygon':
        yield (cs[0] if cs else []), (cs[1:] if len(cs) > 1 else [])
    elif gt == 'MultiPolygon':
        for poly in cs:
            if poly:
                yield poly[0], (poly[1:] if len(poly) > 1 else [])

def close_ring(r):
    if not r: return r
    return r if r[0] == r[-1] else r + [r[0]]

def ring_is_ccw(ring):
    a = 0.0
    for i in range(len(ring)-1):
        x1,y1 = ring[i]; x2,y2 = ring[i+1]
        a += (x2 - x1) * (y2 - y1)
    return a < 0

def parse_kv(s):
    if '=' in s:
        k,v = s.split('=',1); return k.strip(), v.strip()
    return s.strip(), 'yes'

def convert(geojson_path, osm_path, add_index_tags, no_default, duplicate_outer):
    feats = load_geojson(geojson_path)

    nid = 0; wid = 0; rid = 0
    nodes = []      # (id, lon, lat)
    ways = []       # {'id': wid, 'nds': [...], 'tags': {..}}
    rels = []       # {'id': rid, 'members': [(type,ref,role)], 'tags': {...}}
    node_cache = {} # (lon,lat) -> nid

    def add_node(lon, lat):
        nonlocal nid
        key = (round(float(lon), 7), round(float(lat), 7))
        if key in node_cache: return node_cache[key]
        nid += 1
        nodes.append((nid, key[0], key[1]))
        node_cache[key] = nid
        return nid

    def add_way(ring, tags=None):
        nonlocal wid
        wid += 1
        nds = [add_node(lon, lat) for lon, lat in ring]
        return {'id': wid, 'nds': nds, 'tags': (tags or {})}

    # index tags
    extra_tags = [] if no_default else ['landuse=meadow']
    if add_index_tags:
        extra_tags.extend(add_index_tags)

    for feat in feats:
        geom = feat.get('geometry') or {}
        if geom.get('type') not in ('Polygon','MultiPolygon'):
            continue

        props = (feat.get('properties') or {})
        name = props.get('name') or props.get('NAME') or props.get('Name')

        members = []
        for outer, inners in iter_polygons(geom):
            outer = close_ring(outer)
            if outer and not ring_is_ccw(outer):
                outer = close_ring(list(reversed(outer)))

            way_tags = {}
            if duplicate_outer:
                # way_tags['squadratinhos'] = 'yes'
                for kv in extra_tags:
                    k,v = parse_kv(kv)
                    if k: way_tags[k] = v
                if name: way_tags['name'] = str(name)

            w_out = add_way(outer, way_tags); ways.append(w_out)
            members.append(('way', w_out['id'], 'outer'))

            for inner in inners:
                inner = close_ring(inner)
                if inner and ring_is_ccw(inner):
                    inner = close_ring(list(reversed(inner)))
                w_in = add_way(inner); ways.append(w_in)
                members.append(('way', w_in['id'], 'inner'))

        if not members: continue

        rid += 1
        tags = {'type':'multipolygon'}
        if name: tags['name'] = str(name)
        for kv in extra_tags:
            k,v = parse_kv(kv)
            if k and k not in tags:
                tags[k] = v
        rels.append({'id': rid, 'members': members, 'tags': tags})

    with open(osm_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<osm version="0.6" generator="geojson2osm">\n')
        for nid_, lon, lat in nodes:
            f.write(f'  <node id="{nid_}" lon="{lon:.7f}" lat="{lat:.7f}" />\n')
        for w in ways:
            f.write(f'  <way id="{w["id"]}">\n')
            for nd in w['nds']:
                f.write(f'    <nd ref="{nd}" />\n')
            if w.get('tags'):
                for k,v in w['tags'].items():
                    f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(str(v))}" />\n')
            f.write('  </way>\n')
        for r in rels:
            f.write(f'  <relation id="{r["id"]}">\n')
            for typ, ref, role in r['members']:
                f.write(f'    <member type="{typ}" ref="{ref}" role="{xml_escape(role)}" />\n')
            for k,v in r['tags'].items():
                f.write(f'    <tag k="{xml_escape(k)}" v="{xml_escape(str(v))}" />\n')
            f.write('  </relation>\n')
        f.write('</osm>\n')
    print(f"Wrote {osm_path}: nodes={len(nodes)} ways={len(ways)} relations={len(rels)}")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--in',  dest='inp',  required=True, help='Input GeoJSON (WGS84)')
    ap.add_argument('--out', dest='out', required=True, help='Output OSM XML')
    ap.add_argument('--add-index-tag', action='append',
                    help='Extra index tag(s), e.g. --add-index-tag landuse=squadratinhos (can repeat)')
    ap.add_argument('--no-default-index-tag', action='store_true',
                    help='Do not add the default landuse=meadow tag')
    ap.add_argument('--duplicate-outer-tags', action='store_true',
                    help='Duplicate tags (squadratinhos, name, index-tags) onto outer way(s)')
    args = ap.parse_args()
    convert(args.inp, args.out, args.add_index_tag, args.no_default_index_tag, args.duplicate_outer_tags)
