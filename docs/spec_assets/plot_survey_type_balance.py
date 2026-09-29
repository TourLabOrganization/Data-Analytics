"""README figure: survey 6.2 vs 6.3 type shares and interest-course match.

Reads verification/release_validation.json (every survey path, options equally likely; not a user distribution).
Run from the repository root: python docs/spec_assets/plot_survey_type_balance.py
"""
import json
from pathlib import Path
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
R = str(Path(__file__).resolve().parents[2]) + '/'
# Same Korean font order as the analysis notebook; figures still render (with broken glyphs) if none is installed.
installed = {f.name for f in font_manager.fontManager.ttflist}
font = next((f for f in ['Malgun Gothic', 'AppleGothic', 'Noto Sans CJK KR', 'NanumGothic'] if f in installed), None)
plt.rcParams.update({'font.family': font or 'sans-serif', 'axes.unicode_minus': False})
rv = json.load(open(R + 'verification/release_validation.json', encoding='utf-8'))['survey_6_3_recommendation_6_4_revision']
before, after = rv['before'], rv['after']
names = {c: v['name'] for c, v in json.load(open(R + 'survey/implementation/survey_config.json', encoding='utf-8'))['types'].items()}
order = sorted(names, key=lambda c: -before['type_share'][c])
fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={'width_ratios': [1.35, 1]})
y = range(len(order)); h = 0.38
a1.barh([i - h / 2 for i in y], [100 * before['type_share'][c] for c in order], h, color='#b9b9b9', label='6.2 원점수 합산')
a1.barh([i + h / 2 for i in y], [100 * after['type_share'][c] for c in order], h, color='#2f6f8f', label='6.3 유형별 100점 환산')
a1.set_yticks(list(y)); a1.set_yticklabels([f'{names[c]} ({c})' for c in order]); a1.invert_yaxis()
a1.axvline(10, color='#999', lw=0.8, ls='--'); a1.text(10.2, len(order) - 0.4, '균등 10%', color='#777', fontsize=8)
a1.set_xlabel('결과 유형 비중 (%)'); a1.set_title('유형 결과 비중: 최대/최소 6.4배 → 2.5배', fontsize=11)
a1.legend(frameon=False, loc='lower right', fontsize=9)
labels = {'C': '역사', 'D': '자연', 'G': '체험', 'F': '음식', 'E': '바다'}
old = {'C': 0.906, 'D': 0.673, 'E': 0.523, 'F': 0.597, 'G': 0.547}  # published 6.3 reference after the course review
keys = list(labels); x = range(len(keys)); w = 0.38
a2.bar([i - w / 2 for i in x], [old[k] for k in keys], w, color='#b9b9b9', label='6.2')
a2.bar([i + w / 2 for i in x], [after['interest_top1'][k] for k in keys], w, color='#2f6f8f', label='6.3')
for i, k in enumerate(keys):
    a2.text(i + w / 2, after['interest_top1'][k] + 0.015, f"{after['interest_top1'][k]:.2f}", ha='center', fontsize=8)
    a2.text(i - w / 2, old[k] + 0.015, f'{old[k]:.2f}', ha='center', fontsize=8, color='#666')
a2.set_xticks(list(x)); a2.set_xticklabels([labels[k] for k in keys]); a2.set_ylim(0, 1.08)
a2.set_ylabel('일치율'); a2.set_title('고른 관심사와 1위 코스의 주 범주가 같은 비율', fontsize=11)
a2.legend(frameon=False, loc='upper right', fontsize=9)
for a in (a1, a2): a.spines[['top', 'right']].set_visible(False)
fig.text(0.01, 0.01, '모든 설문 경로를 같은 빈도로 본 구조 점검이며 실제 응답자 분포가 아님', fontsize=8, color='#777')
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(R + 'docs/spec_assets/survey_type_balance.png', dpi=150)
print('saved')
