class Component extends DCLogic {
  state = { splash: true, slide: 0, view: null, ans: {}, step: 0, recOpen: false, result: null, saved: null, meOpen: false, plans: [] };

  VIEWS = {
    rescene: { src: 'RESCENE Route.dc.html', title: 'RESCENE Route' },
    warden:  { src: 'Kings Warden Route.dc.html', title: '왕과 사는 남자 · 영월' },
    kdh:     { src: 'KPop Demon Hunters Route.dc.html', title: '케이팝 데몬 헌터스 · 서울' },
    jeju:    { src: 'Jeju K-Drama Route.dc.html', title: '제주 K-Drama' },
    busan:   { src: 'Busan Cinema Route.dc.html', title: '부산 영화 기행' },
    planner: { src: 'Tour Planner.dc.html', title: '투어 플래너' }
  };

  // 테마 추천 알고리즘 (repo: 테마 추천 알고리즘/docs/01_고도화_전략.md, data/derived/calc2.json)
  // 점수 열 순서: C1…C10. Q1~Q9 군집 판정, Q10~Q14 코스 필터
  QS = [
    { t: '연령대를 알려주세요', p: '군집 판정', req: true, o: ['10대','20대','30대','40대','50대','60대','70대 이상'],
      s: [[1,0,0,0,0,0,2,0,0,0],[2,3,0,0,0,0,1,0,0,0],[0,2,0,0,1,0,0,0,0,0],[0,0,2,0,0,0,0,0,0,0],[0,0,0,1,0,0,0,0,0,1],[0,0,0,2,0,0,0,0,0,1],[0,0,0,3,0,0,0,0,0,1]] },
    { t: '누구와 떠나시나요?', p: '군집 판정', req: true, o: ['혼자','친구와','연인과','배우자와','아이와 가족','부모님 모시고','친목 모임'],
      s: [[1,0,0,0,3,0,1,1,0,0],[3,0,0,0,0,1,0,0,0,0],[0,3,0,0,0,0,0,0,0,1],[0,1,0,2,0,0,0,0,0,1],[0,0,3,0,0,0,0,0,1,0],[0,0,1,2,0,1,0,0,0,1],[0,0,0,3,0,1,0,0,0,0]] },
    { t: '어떤 속도로 여행하고 싶으세요?', p: '군집 판정', req: true, o: ['빡빡하게, 많이 보고 싶어요','적당히, 보고 쉬고 반반','천천히, 걷고 쉬며 여유롭게'],
      s: [[2,0,0,0,0,0,2,0,0,0],[0,1,1,0,0,1,0,1,0,0],[0,0,0,2,3,0,0,0,0,0]] },
    { t: '끌리는 것을 골라주세요', p: '군집 판정 + 테마 가산점', multi: 2, o: ['드라마·K팝 촬영지','공연·콘서트','역사·유적','자연·숲길','바다','맛집·시장','체험·액티비티','야경','쇼핑·뷰티·스파'],
      s: [[2,1,0,0,0,0,3,0,0,0],[1,1,0,0,0,0,3,0,0,0],[0,0,1,3,0,0,0,0,0,3],[0,0,0,2,3,0,0,0,2,1],[0,2,2,0,0,0,0,0,2,0],[1,0,0,0,0,3,0,0,0,0],[1,0,3,0,0,0,0,0,0,2],[2,2,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,3,0,0]],
      cat: [null,null,0,1,4,3,2,'night',null] },
    { t: '어떤 분위기가 좋으세요?', p: '군집 판정', o: ['요즘 뜨는 핫플','누구나 아는 대표 명소','사람 적은 한적한 곳'],
      s: [[3,0,0,0,0,0,1,0,0,0],[0,0,1,1,0,0,1,1,0,0],[0,0,0,1,3,1,0,0,0,0]] },
    { t: '어디에서 오셨나요?', p: '외래객 구분', o: ['국내 거주','해외에서 방문'] },
    { t: '1인 경비는 어느 정도인가요?', p: '군집 판정 + 가격대', o: ['7만 원 미만','7만~15만 원','15만~25만 원','25만 원 이상'],
      oF: ['1일 $100 이하','1일 $100~300','1일 $300~500','1일 $500 초과'],
      s: [[2,0,0,0,1,0,0,0,0,0],[0,1,1,1,0,1,0,0,0,0],[0,1,0,0,0,2,0,0,0,0],[0,0,0,0,0,0,0,0,0,0]],
      sF: [[0,0,0,0,0,0,0,0,0,1],[0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,0,0,0],[0,0,0,0,0,0,0,2,0,0]] },
    { t: '주로 언제 움직이세요?', p: '군집 판정 + 일정 시간대', o: ['아침 일찍부터','낮 시간 위주','저녁·밤까지'],
      s: [[0,0,0,2,1,0,0,0,0,0],[0,0,2,1,0,0,0,1,0,0],[2,2,0,0,0,0,1,0,0,0]] },
    { t: '여행 정보는 주로 어디서 얻으세요?', p: '군집 판정', o: ['가 본 경험','지인 추천','인터넷·앱','SNS·유튜브','정보 없이'],
      s: [[0,0,0,0,0,0,0,1,0,0],[0,0,0,0,0,0,0,0,0,0],[1,1,0,0,0,0,0,0,0,0],[1,1,0,0,0,0,1,0,1,0],[0,0,0,0,0,0,0,0,0,0]] },
    { t: '언제 떠나세요?', p: '코스 필터 · 계절·축제', o: ['이번 주말','이번 달','다음 달 이후'] },
    { t: '여행 기간은요?', p: '코스 필터', o: ['당일','1박 2일','2박 3일 이상'] },
    { t: '주로 무엇으로 이동하세요?', p: '코스 필터', o: ['자가용','대중교통','비행기','단체버스'] },
    { t: '하루에 얼마나 걸을 수 있나요?', p: '코스 필터 · 동선 길이', o: ['1시간 이내','1~3시간','3시간 이상'] },
    { t: '해당하는 조건이 있나요?', p: '코스 필터', multi: 3, o: ['반려동물 동반','무장애 (휠체어·유모차)','비 오는 날 실내 위주'] }
  ];
  CL = [
    ['C1','MZ 트렌드 탐색형','핫플·야경·새로운 곳을 빠르게 도는 20대 친구 여행',[.1,.1,.3,.3,.2]],
    ['C2','커플 감성형','바다·야경·분위기 좋은 곳을 찾는 연인·부부',[.1,.2,.1,.3,.3]],
    ['C3','키즈 가족형','체험과 안전, 짧은 이동이 중요한 아이 동반 가족',[.1,.1,.5,.1,.2]],
    ['C4','액티브 시니어형','역사·걷기 중심, 무리 없는 일정을 원하는 50~60대',[.5,.3,.05,.15,0]],
    ['C5','나홀로 힐링형','한적한 자연 속에서 천천히 쉬는 1인 여행',[.1,.6,0,.1,.2]],
    ['C6','미식 로컬형','시장·노포·지역 음식이 여행의 목적',[.2,.05,.05,.7,0]],
    ['C7','외래객 K-컬처형','K팝·공연·촬영지를 찾는 해외 방문객',[.21,.03,.35,.27,.14]],
    ['C8','외래객 웰니스형','뷰티·스파·미식 중심의 해외 방문객',[.08,.26,0,.44,.23]],
    ['C9','외래객 자연·지방형','자연경관과 지방 여행을 즐기는 해외 방문객',[.02,.33,.07,.21,.36]],
    ['C10','외래객 역사·전통문화형','고궁·박물관·전통문화를 찾는 해외 방문객',[.31,.19,.19,.13,.18]]
  ];
  // pr: 장소 재분류 후 구성비 (역사·힐링·액티비티·먹거리·해양), night: 야경 태그 비중
  // rl: 연령대별 테마 지역 방문 lift (10대…70대+), fr: 외래객 군집별 지역 보정 (C7~C10)
  TH = [
    { k: 'warden', name: '왕과 사는 남자', region: '영월', img: 'uploads/images (17).jpg', pr: [.4,.311,.233,.056,0], night: .056, rl: [.88,1.03,1.03,1.02,1.01,.99,.85] },
    { k: 'kdh', name: '케이팝 데몬 헌터스', region: '서울', img: 'uploads/images (19).jpg', pr: [.293,.228,.216,.253,.009], night: .128, rl: [2.91,1.76,1.04,.82,.73,.6,.62] },
    { k: 'rescene', name: 'RESCENE Route', region: '경주·거제', img: 'uploads/images (18).jpg', pr: [.328,.165,.13,.193,.184], night: .058, rl: [.77,.84,.92,1.03,1.07,1.16,1.06] },
    { k: 'jeju', name: '제주 K-Drama', region: '제주', img: 'uploads/images (20).jpg', pr: [.165,.437,.084,.052,.262], night: .037, rl: [.68,.82,1.11,.98,1.11,1.14,.7] },
    { k: 'busan', name: '부산 영화 기행', region: '부산', img: 'assets/busan-tile.jpg', pr: [.141,.245,.152,.265,.197], night: .141, rl: [1.17,1.47,1.19,1,.89,.66,.6] }
  ];
  optsOf = i => { const q = this.QS[i]; return q.oF && (this.state.ans || {})[5] === 1 ? q.oF : q.o; };

  freshAns = () => {
    const a = {};
    const lang = (navigator.language || 'ko').toLowerCase();
    if (!lang.startsWith('ko')) a[5] = 1;
    return a;
  };
  openRec = e => { if (e && e.preventDefault) e.preventDefault(); this.setState({ recOpen: true, step: 0, ans: this.freshAns(), result: null }); };
  openRecResult = () => this.setState({ recOpen: true, result: this.state.saved });
  closeRec = () => this.setState({ recOpen: false });
  restartRec = () => this.setState({ step: 0, ans: this.freshAns(), result: null });
  answered = i => { const v = (this.state.ans || {})[i]; return Array.isArray(v) ? v.length > 0 : v !== undefined; };
  pick = (i, j) => () => {
    const q = this.QS[i];
    this.setState(s => {
      const ans = { ...s.ans };
      if (q.multi) {
        const cur = ans[i] || [];
        ans[i] = cur.includes(j) ? cur.filter(x => x !== j) : (cur.length >= q.multi ? [...cur.slice(1), j] : [...cur, j]);
      } else ans[i] = j;
      return { ans };
    });
    if (!q.multi) { clearTimeout(this.adv); this.adv = setTimeout(() => this.advance(), 220); }
  };
  advance = () => {
    const i = this.state.step;
    if (i >= this.QS.length - 1) this.finish(); else this.setState({ step: i + 1 });
  };
  nextQ = () => { if (this.answered(this.state.step)) this.advance(); };
  skipQ = () => { const ans = { ...this.state.ans }; delete ans[this.state.step]; this.setState({ ans }, this.advance); };
  prevQ = () => { if (this.state.step > 0) this.setState(s => ({ step: s.step - 1 })); };

  finish = () => {
    const a = this.state.ans, tot = Array(10).fill(0), foreign = a[5] === 1, domestic = a[5] === 0;
    const add = row => row.forEach((v, c) => { tot[c] += v; });
    [0,1,2,4,7,8].forEach(i => { if (a[i] !== undefined) add(this.QS[i].s[a[i]]); });
    (a[3] || []).forEach(j => add(this.QS[3].s[j]));
    if (a[6] !== undefined) add((foreign ? this.QS[6].sF : this.QS[6].s)[a[6]]);
    if (foreign) {
      [6,7,8,9].forEach(c => { tot[c] += 2; });
      const lang = (navigator.language || 'ko').toLowerCase();
      if (lang.startsWith('zh')) { tot[6] += 1; tot[8] += 1; }
      else if (lang.startsWith('ja')) tot[7] += 1;
      else if (lang.startsWith('en') || lang.startsWith('es')) tot[9] += 2;
    }
    const cand = tot.map((v, c) => c).filter(c => !(domestic && c >= 6));
    const w = {}; let W = 0;
    cand.forEach(c => { w[c] = Math.pow(2, tot[c] / 2); W += w[c]; });
    const prob = c => w[c] / W;
    const q2 = a[1] !== undefined ? this.QS[1].s[a[1]] : tot.map(() => 0);
    const order = cand.slice().sort((x, y) => tot[y] - tot[x] || q2[y] - q2[x]);
    const p = order[0], s2 = order[1], mix = prob(p) < 0.5;
    const cats = (a[3] || []).map(j => this.QS[3].cat[j]).filter(c => c !== null);
    const age = a[0];
    const regOf = (t, c) => c >= 6 ? t.fr[c - 6] : (age !== undefined ? Math.max(-.05, Math.min(.05, .1 * (t.rl[age] - 1))) : 0);
    const fitOf = (t, c) => t.pr.reduce((sum, v, k) => sum + v * this.CL[c][3][k], 0);
    const picks = this.TH.map(t => {
      const fit = mix ? (prob(p) * fitOf(t, p) + prob(s2) * fitOf(t, s2)) / (prob(p) + prob(s2)) : fitOf(t, p);
      const bonus = 0.5 * cats.reduce((sum, k) => sum + (k === 'night' ? t.night : t.pr[k]), 0);
      const reg = mix ? (prob(p) * regOf(t, p) + prob(s2) * regOf(t, s2)) / (prob(p) + prob(s2)) : regOf(t, p);
      return { k: t.k, fit, bonus, reg, score: fit + bonus + reg };
    }).sort((x, y) => y.score - x.score).slice(0, 3);
    const filters = [];
    [9,10,11,12].forEach(i => { if (a[i] !== undefined) filters.push(this.QS[i].o[a[i]]); });
    (a[13] || []).forEach(j => filters.push(this.QS[13].o[j]));
    const result = { p, s2, pts: tot[p], pts2: tot[s2], pr: Math.round(prob(p) * 100), pr2: Math.round(prob(s2) * 100), mix, picks, filters, cats };
    try { localStorage.setItem('tn_theme_rec_v3', JSON.stringify(result)); } catch (e) {}
    this.setState({ result, saved: result });
  };


}
