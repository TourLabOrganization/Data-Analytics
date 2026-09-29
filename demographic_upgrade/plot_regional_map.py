"""Map of the regional demographic clusters R01/R02 on 2013 KOSTAT municipality boundaries.

Run from this folder after analyze_demographics.py: python plot_regional_map.py
The boundary GeoJSON (southkorea/southkorea-maps, KOSTAT census boundaries 2013) is not stored in
this repository. It is downloaded once from a pinned commit into data/boundaries/ and checked by SHA-256.
Boundaries are drawn only for orientation; region names are matched by the rules below, not by
official administrative codes.
"""
from pathlib import Path
import csv, hashlib, json, urllib.request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch, Polygon
from matplotlib.collections import PatchCollection

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'data/boundaries'
COMMIT = 'fe65e05e549d04083e52f380a7e9166a8ea0a01e'
BASE = f'https://raw.githubusercontent.com/southkorea/southkorea-maps/{COMMIT}/kostat/2013/json/'
FILES = {'skorea_municipalities_geo_simple.json': 'e0cf2030dc893f40b6e97dfa7183d47c2197ea74551b041eabfd7bc318a74285',
         'skorea_provinces_geo_simple.json': '2875acb67d32d3a5646c8d039b133e5f1be0bfae8f67e447159a5505430f9ad8'}
# Current province names -> 2013 names; per-region moves after 2013
SIDO_ALIAS = {'강원특별자치도': ['강원도'], '전북특별자치도': ['전라북도'], '전남광주통합특별시': ['전라남도', '광주광역시']}
REGION_ALIAS = {'대구광역시|군위군': ('경상북도', '군위군')}  # moved from 경상북도 to 대구광역시 in 2023
COLORS = {'R01': '#d98c3f', 'R02': '#2f6f8f'}

def load(name):
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(BASE + name, path)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != FILES[name]:
        raise SystemExit(f'{path} does not match the pinned SHA-256; delete it and rerun.')
    return json.loads(data)

def rings(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return [p[0] for p in polys]  # outer rings; the simplified file has no meaningful holes at this scale

def main():
    muni = load('skorea_municipalities_geo_simple.json')['features']
    prov = load('skorea_provinces_geo_simple.json')['features']
    sido = {f['properties']['code']: f['properties']['name'] for f in prov}
    rows = list(csv.DictReader((ROOT / 'results/regional_cluster_assignments.csv').open(encoding='utf-8-sig')))
    colour, matches = {}, []
    for r in rows:
        want_sido, want = REGION_ALIAS.get(r['source_region'], (None, r['sigungu']))
        sidos = [want_sido] if want_sido else SIDO_ALIAS.get(r['sido'], [r['sido']])
        cand = [f for f in muni if sido[f['properties']['code'][:2]] in sidos]
        hit, rule = [f for f in cand if f['properties']['name'] == want], 'exact_name'
        if not hit:  # cities split into districts in 2013, e.g. 안산시 -> 안산시상록구, 안산시단원구
            hit, rule = [f for f in cand if f['properties']['name'].startswith(want)], 'city_districts'
        if r['source_region'] in REGION_ALIAS: rule = 'moved_after_2013'
        if not hit: raise SystemExit('No boundary for ' + r['source_region'])
        for f in hit: colour[f['properties']['code']] = COLORS[r['regional_cluster']]
        matches.append({'source_region': r['source_region'], 'regional_cluster': r['regional_cluster'], 'match_rule': rule,
                        'boundary_codes_2013': ';'.join(sorted(f['properties']['code'] for f in hit)),
                        'boundary_names_2013': ';'.join(sorted(f['properties']['name'] for f in hit))})
    with (ROOT / 'results/regional_map_matches.csv').open('w', encoding='utf-8-sig', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(matches[0])); w.writeheader(); w.writerows(matches)

    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ['Malgun Gothic', 'AppleGothic', 'Noto Sans CJK KR', 'NanumGothic'] if f in installed), None)
    plt.rcParams.update({'font.family': font or 'sans-serif', 'axes.unicode_minus': False})
    fig, ax = plt.subplots(figsize=(7.2, 8.6))
    patches, faces = [], []
    for f in muni:
        for ring in rings(f['geometry']):
            patches.append(Polygon(ring, closed=True)); faces.append(colour.get(f['properties']['code'], '#eeeeee'))
    ax.add_collection(PatchCollection(patches, facecolor=faces, edgecolor='white', linewidth=0.3))
    outline = [Polygon(ring, closed=True) for f in prov for ring in rings(f['geometry'])]
    ax.add_collection(PatchCollection(outline, facecolor='none', edgecolor='#555555', linewidth=0.6))
    n = {k: sum(r['regional_cluster'] == k for r in rows) for k in COLORS}
    ax.legend(handles=[Patch(color=COLORS['R01'], label=f"R01 ({n['R01']}지역): 50·60대 비중이 높음"),
                       Patch(color=COLORS['R02'], label=f"R02 ({n['R02']}지역): 20·30대 비중이 높음"),
                       Patch(facecolor='#eeeeee', edgecolor='#bbbbbb', label='상세 연령·성별표 없음 (분석 제외)')],
              loc='lower right', frameon=False, fontsize=9)
    ax.set_xlim(124.6, 130.0); ax.set_ylim(33.1, 38.65); ax.set_aspect(1.25); ax.axis('off')
    ax.set_title('지역별 방문자 연령·성별 구성 군집 R (90개 시군구)', fontsize=12)
    fig.text(0.02, 0.015, '경계: 통계청 센서스용 행정구역경계 2013 (southkorea-maps). 울릉군은 표시 범위 밖.\n'
             '2013년 이후 바뀐 이름은 결과 폴더 regional_map_matches.csv의 규칙으로 대응', fontsize=7, color='#777')
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(ROOT / 'plots/04_regional_cluster_map.png', dpi=150)
    print('saved plots/04_regional_cluster_map.png;', {k: sum(m['match_rule'] == k for m in matches) for k in ('exact_name', 'city_districts', 'moved_after_2013')})

if __name__ == '__main__':
    main()
