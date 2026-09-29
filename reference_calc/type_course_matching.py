"""Category fit of each traveller type C1~C10 with every eligible city-tour course.

Each type is scored as if it were the only result type: its 5-category profile is the preference
vector u and the course score is the category fit 100 × cosine(u, course shares) × coverage used by
recommend_reference.py. Interest, night and pace bonuses depend on individual answers and are left out.
Python 3.10+, standard library only. Run from the repository root:
    python reference_calc/type_course_matching.py
Writes type_course_matching.csv (all types × courses), type_course_top5.csv (one course per region)
and type_T_cluster_fit.csv (mean fit per T cluster) next to this script.
"""
from pathlib import Path
import csv, json, math, sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from recommend_reference import CFG, normalize

NAMES = {c: t['name'] for c, t in json.loads((ROOT.parent / 'survey/implementation/survey_config.json').read_text(encoding='utf-8'))['types'].items()}
CATS = CFG['categories']

def main():
    with (ROOT / 'eligible_courses.csv').open(encoding='utf-8-sig', newline='') as f:
        courses = list(csv.DictReader(f))
    rows, top5, by_t = [], [], []
    for code, profile in CFG['profiles'].items():
        u = normalize(profile); nu = math.sqrt(sum(x * x for x in u)); scored = []
        for c in courses:
            p = [float(c['analysis_share_' + k]) for k in CATS]; cov = float(c['analysis_category_coverage'])
            cos = sum(x * y for x, y in zip(u, p)) / (nu * math.sqrt(sum(x * x for x in p)))
            scored.append({'type': code, 'type_name': NAMES[code], 'course_id': c['analysis_course_id'], 'region': c['analysis_region'],
                           'name': c['analysis_name'], 'T_cluster': c['analysis_T_cluster'], 'cosine_similarity': round(cos, 6),
                           'coverage': round(cov, 6), 'category_fit_score': round(100 * cos * cov, 6)})
        # Same order as recommend_reference: score, cosine, coverage, course_id
        scored.sort(key=lambda r: (-r['category_fit_score'], -r['cosine_similarity'], -r['coverage'], r['course_id']))
        seen = set()
        for rank, r in enumerate(scored, 1):
            r['rank'] = rank; rows.append(r)
            if r['region'] not in seen and len(seen) < 5:
                seen.add(r['region']); top5.append({'type': code, 'type_name': NAMES[code], 'region_rank': len(seen), 'rank': rank,
                    'region': r['region'], 'name': r['name'], 'category_fit_score': r['category_fit_score'], 'T_cluster': r['T_cluster']})
        clusters = sorted({r['T_cluster'] for r in scored})
        for t in clusters:
            v = [r['category_fit_score'] for r in scored if r['T_cluster'] == t]
            by_t.append({'type': code, 'type_name': NAMES[code], 'T_cluster': t, 'courses': len(v), 'mean_category_fit': round(sum(v) / len(v), 3)})
    for name, data in [('type_course_matching', rows), ('type_course_top5', top5), ('type_T_cluster_fit', by_t)]:
        with (ROOT / f'{name}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator='\n'); w.writeheader(); w.writerows(data)
    print(len(rows), 'type-course rows;', len(top5), 'top-5 rows;', len(by_t), 'type-cluster rows')

if __name__ == '__main__':
    main()
