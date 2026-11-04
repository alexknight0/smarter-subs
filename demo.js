// Interactive copy of the extension's subtitle overlay for the hero section.
// Words: [text, lemma, part of speech, meaning] or plain strings for particles/endings.
// kind 'name' = shown blue, not counted (as in the extension).

const LINES = [
  {
    ko: [['오늘', '오늘', 'noun', 'today'], ' ', ['날씨', '날씨', 'noun', 'weather'], '가 ', ['정말', '정말', 'adverb', 'really, truly'], ' ', ['좋네요', '좋다', 'adjective', 'good, nice']],
    en: 'The weather is really nice today.',
  },
  {
    ko: [['지민', '지민', 'name', '', 'name'], ' ', ['씨', '씨', 'bound noun', 'Mr, Ms (polite title after a name)'], ', ', ['같이', '같이', 'adverb', 'together'], ' ', ['가요', '가다', 'verb', 'to go'], '!'],
    en: "Jimin, let's go together!",
  },
  {
    ko: [['우리', '우리', 'pronoun', 'we, us'], ' ', ['어디', '어디', 'pronoun', 'where, somewhere'], '서 ', ['만난', '만나다', 'verb', 'to meet'], ' ', ['적', '적', 'bound noun', 'time, experience: the time when something happened', null, '-ㄴ 적이 있다: says that something has happened before'], ' ', ['있지', '있다', 'adjective', 'to exist, to have'], ' ', ['않아요', '않다', 'auxiliary', 'not (makes the verb before it negative)'], '?'],
    en: "Haven't we met somewhere before?",
  },
  {
    ko: [['이', '이', 'determiner', 'this'], ' ', ['약속', '약속', 'noun', 'promise, appointment'], '은 ', ['꼭', '꼭', 'adverb', 'surely, without fail'], ' ', ['지킬게요', '지키다', 'verb', 'to keep (a promise), to protect']],
    en: "I'll be sure to keep this promise.",
  },
  {
    ko: [['괜찮아', '괜찮다', 'adjective', 'okay, all right'], ', ', ['천천히', '천천히', 'adverb', 'slowly, unhurriedly'], ' ', ['해', '하다', 'verb', 'to do']],
    en: "It's okay, take your time.",
  },
];

const LINE_MS = 3800;
const GAP_MS = 900;
const SLOT = LINE_MS + GAP_MS;
const TOTAL = SLOT * LINES.length;

// unknown -> learning -> known -> unknown, like a left click in the extension.
const NEXT = { unknown: 'learning', learning: 'known', known: 'unknown' };
const marks = new Map(
  ['오늘', '정말', '좋다', '씨', '같이', '가다', '우리', '어디', '만나다', '있다', '않다', '이', '꼭', '괜찮다', '하다'].map((w) => [w, 'known']),
);
const stateOf = (lemma) => marks.get(lemma) || 'unknown';

const subs = document.getElementById('subs');
const progress = document.getElementById('progress');
const screen = document.querySelector('#demo .screen');
const pausedBadge = document.querySelector('#demo .paused-badge');
const playBtn = document.getElementById('play');

let t = 0; // demo time in ms
let last = performance.now();
let playing = true;
let pausedByHover = false;
let revealed = -1; // line index whose hidden English was revealed with E
let shown = null; // render key, to skip unchanged frames
let popupWord = null;
let tapOpened = false; // a touch tap that opened the popup shouldn't also mark the word

const lineAt = (ms) => {
  const i = Math.floor(ms / SLOT);
  return ms - i * SLOT < LINE_MS ? i : -1;
};

const words = (line) => line.ko.filter((p) => Array.isArray(p) && p[4] !== 'name');
const knowsLine = (line) => words(line).every((w) => stateOf(w[1]) !== 'unknown');

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
}

function render() {
  const i = lineAt(t);
  const key = i < 0 ? 'gap' : `${i}|${LINES[i].ko.map((p) => (Array.isArray(p) ? stateOf(p[1]) : '')).join()}|${revealed === i}|${popupWord}`;
  if (key === shown) return;
  shown = key;
  subs.replaceChildren();
  if (i < 0) return;
  const line = LINES[i];
  const known = knowsLine(line);

  const ko = el('div', 'line ko');
  for (const part of line.ko) {
    if (!Array.isArray(part)) {
      ko.append(part);
      continue;
    }
    const [text, lemma, , , kind] = part;
    const span = el('span', kind === 'name' ? 'w w-name' : `w w-${stateOf(lemma)}`, text);
    span.dataset.idx = line.ko.indexOf(part);
    if (popupWord === span.dataset.idx) span.classList.add('hl');
    ko.append(span);
  }

  const en = el('div', 'line en', line.en);
  if (known && revealed !== i) en.classList.add('blurred');

  // As in the extension: English on top while the sentence has unknown words.
  if (known) {
    en.classList.add('bottom');
    subs.append(ko, en);
  } else {
    ko.classList.add('bottom');
    subs.append(en, ko);
  }

  if (popupWord !== null) {
    const [text, lemma, pos, meaning, kind, grammar] = line.ko[popupWord];
    const pop = el('div', 'pop');
    const head = el('div', 'pop-head');
    head.append(el('b', '', lemma));
    if (kind === 'name') head.append(' ', el('span', 'w-name', 'name'));
    else head.append(' ', el('span', `w-${stateOf(lemma)}`, stateOf(lemma)));
    pop.append(head);
    if (grammar) {
      const g = el('div', 'pop-grammar');
      g.append(el('span', 'tag', 'grammar'), ' ', grammar);
      pop.append(g);
    }
    if (kind === 'name') {
      pop.append(el('div', 'pop-sense muted', 'Names are shown in blue and not counted.'));
    } else {
      const s = el('div', 'pop-sense');
      s.append(el('b', '', lemma), ' ', el('span', 'muted', pos));
      if (text !== lemma) s.append(el('span', 'muted', ` (from ${text})`));
      s.append(el('br'), meaning);
      pop.append(s);
      pop.append(el('div', 'pop-foot muted', 'click: unknown → learning → known'));
    }
    subs.append(pop);
  }
}

function setPlaying(p) {
  playing = p;
  screen.classList.toggle('paused', !p);
  playBtn.textContent = p ? 'Pause' : 'Play';
  pausedBadge.hidden = !(pausedByHover && !p);
}

function step(dir) {
  const cur = lineAt(t);
  const slot = Math.floor(t / SLOT);
  let target;
  if (dir < 0) target = cur >= 0 && t - slot * SLOT > 1200 ? slot : slot - 1;
  else target = slot + 1;
  if (cur < 0 && dir < 0) target = slot; // in a gap, A replays the line just heard
  target = (target + LINES.length) % LINES.length;
  t = target * SLOT;
  popupWord = null;
  revealed = -1;
  render();
}

function frame(now) {
  if (playing) {
    t = (t + now - last) % TOTAL;
    if (lineAt(t) !== revealed) revealed = -1;
  }
  last = now;
  progress.style.width = `${(t / TOTAL) * 100}%`;
  render();
  requestAnimationFrame(frame);
}

subs.addEventListener('mouseover', (e) => {
  const w = e.target.closest('.w');
  if (!w || popupWord === w.dataset.idx) return;
  popupWord = w.dataset.idx;
  if (playing) {
    pausedByHover = true;
    setPlaying(false);
  }
  render();
});

subs.addEventListener('mouseleave', () => {
  popupWord = null;
  if (pausedByHover) {
    pausedByHover = false;
    setPlaying(true);
  }
  render();
});

subs.addEventListener('click', (e) => {
  const w = e.target.closest('.w');
  const i = lineAt(t);
  if (tapOpened) {
    tapOpened = false;
    return;
  }
  if (!w || i < 0) return;
  const part = LINES[i].ko[w.dataset.idx];
  if (part[4] === 'name') return;
  marks.set(part[1], NEXT[stateOf(part[1])]);
  render();
});

// Touch screens have no hover: a tap opens the popup first, a second tap marks.
subs.addEventListener('pointerdown', (e) => {
  if (e.pointerType !== 'touch') return;
  const w = e.target.closest('.w');
  if (w && popupWord !== w.dataset.idx) {
    tapOpened = true;
    popupWord = w.dataset.idx;
    pausedByHover = playing;
    setPlaying(false);
    render();
  }
});

// A tap anywhere else closes it and resumes (touch has no mouseleave).
document.addEventListener('pointerdown', (e) => {
  if (e.pointerType !== 'touch' || popupWord === null || subs.contains(e.target)) return;
  popupWord = null;
  if (pausedByHover) {
    pausedByHover = false;
    setPlaying(true);
  }
  render();
});

document.querySelectorAll('[data-step]').forEach((b) => b.addEventListener('click', () => step(Number(b.dataset.step))));
playBtn.addEventListener('click', () => {
  pausedByHover = false;
  setPlaying(!playing);
});

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (k === 'a') step(-1);
  else if (k === 'd') step(1);
  else if (k === 'e') {
    const i = lineAt(t);
    revealed = revealed === i ? -1 : i;
    render();
  } else if (k === 'escape') {
    popupWord = null;
    render();
  } else if (k === ' ' && document.activeElement === screen) {
    e.preventDefault();
    setPlaying(!playing);
  } else return;
});

if (matchMedia('(prefers-reduced-motion: reduce)').matches) screen.classList.add('still');
requestAnimationFrame(frame);
