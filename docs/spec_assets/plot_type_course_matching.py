"""Heatmap: mean category fit of each traveller type C1~C10 with each course cluster T.

Run from the repository root after reference_calc/type_course_matching.py:
    python docs/spec_assets/plot_type_course_matching.py
Cluster labels are derived from reference_calc/eligible_courses.csv (dominant category, night or long course),
so they follow the current snapshot.
"""
import csv, collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

R = 'reference_calc/'
KO = {'herit': '역사', 'heal': '자연', 'activity': '체험', 'food': '음식', 'sea': '바다'}
# single-hue sequential ramp, light -> dark (blue 100 ... 700)
RAMP = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']

def cluster_labels():
    acc = collections.defaultdict(lambda: collections.defaultdict(float)); n = collections.Counter()
    for r in csv.DictReader(open(R + 'eligible_courses.csv', encoding='utf-8-sig')):
        t = r['analysis_T_cluster']; n[t] += 1
        for k in KO: acc[t][k] += float(r['analysis_share_' + k])
        acc[t]['night'] += int(r['analysis_night_flag']); acc[t]['visits'] += int(r['analysis_visit_candidate_count'])
    out = {}
    for t in sorted(n):
        m = {k: v / n[t] for k, v in acc[t].items()}
        if m['night'] > 0.5: lab = '야경'
        elif m['visits'] > 7: lab = '긴 혼합'
        else: lab = KO[max(KO, key=lambda k: m[k])]
        out[t] = f'{t}\n{lab}\n({n[t]}코스)'
    return out

def main():
    installed = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in ['Malgun Gothic', 'AppleGothic', 'Noto Sans CJK KR', 'NanumGothic'] if f in installed), None)
    plt.rcParams.update({'font.family': font or 'sans-serif', 'axes.unicode_minus': False})
    rows = list(csv.DictReader(open(R + 'type_T_cluster_fit.csv', encoding='utf-8-sig')))
    types = list(dict.fromkeys(r['type'] for r in rows)); names = {r['type']: r['type_name'] for r in rows}
    clusters = sorted({r['T_cluster'] for r in rows}); val = {(r['type'], r['T_cluster']): float(r['mean_category_fit']) for r in rows}
    labels = cluster_labels()
    grid = [[val[(c, t)] for t in clusters] for c in types]
    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    im = ax.imshow(grid, cmap=LinearSegmentedColormap.from_list('seq', RAMP), vmin=0, vmax=100, aspect='auto')
    for i, c in enumerate(types):
        best = max(range(len(clusters)), key=lambda j: grid[i][j])
        ax.add_patch(Rectangle((best - .47, i - .47), .94, .94, fill=False, edgecolor='#f2a93b', linewidth=2.2))
        for j in range(len(clusters)):
            v = grid[i][j]
            ax.text(j, i, f'{v:.0f}', ha='center', va='center', fontsize=9.5,
                    color='white' if v >= 55 else '#1f1f1f')
    ax.set_xticks(range(len(clusters)), [labels[t] for t in clusters], fontsize=8.5)
    ax.set_yticks(range(len(types)), [f'{c} {names[c]}' for c in types], fontsize=9)
    ax.tick_params(length=0); [s.set_visible(False) for s in ax.spines.values()]
    ax.set_xticks([x - .5 for x in range(1, len(clusters))], minor=True); ax.set_yticks([y - .5 for y in range(1, len(types))], minor=True)
    ax.grid(which='minor', color='white', linewidth=2); ax.tick_params(which='minor', length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02); cb.set_label('평균 범주 적합 (0~100)', fontsize=9); cb.outline.set_visible(False)
    ax.set_title('여행자 유형별 코스 군집 T 평균 범주 적합', fontsize=12, loc='left')
    fig.text(0.01, 0.01, '범주 적합 = 100 × cosine(유형 프로필, 코스 범주 비중) × 분류 커버리지. 주황 테두리는 유형별 최고 군집. 관심사·야경·속도 가산 제외.',
             fontsize=7.5, color='#666666')
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig('docs/spec_assets/type_course_matching.png', dpi=150)
    print('saved docs/spec_assets/type_course_matching.png')

if __name__ == '__main__':
    main()
