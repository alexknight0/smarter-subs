// Feature cards drive the clip below them. Hovering a card (with a mouse) plays its clip
// on a loop; otherwise each card's clip plays once through, then the next card's, left to
// right. The active card's bottom bar shows how far through its clip it is. Tapping or
// focusing a card jumps to it.

const REMOTE_MS = 7000; // the remote is a drawing, not a clip, so it gets a fixed time

const cards = [...document.querySelectorAll('.hcard[data-clip]')];
const stage = document.querySelector('.stage');
const panes = new Map([...stage.querySelectorAll('[data-pane]')].map((p) => [p.dataset.pane, p]));

let current = -1;
let hovered = -1; // index of the card under the mouse, or -1
let paneStart = 0; // performance.now() when a pane without a video was shown

const paneOf = (i) => panes.get(cards[i].dataset.clip);
const isVideo = (p) => p instanceof HTMLVideoElement;

function show(i) {
  if (current >= 0) {
    cards[current].classList.remove('active');
    cards[current].style.setProperty('--progress', 0);
    const old = paneOf(current);
    old.classList.remove('on');
    if (isVideo(old)) old.pause();
  }
  current = i;
  cards[i].classList.add('active');
  restart();
}

function restart() {
  const p = paneOf(current);
  p.classList.add('on');
  if (isVideo(p)) {
    p.currentTime = 0;
    p.play().catch(() => {});
  } else {
    paneStart = performance.now();
  }
}

// Called when the current clip reaches its end.
function finished() {
  if (hovered === current) restart();
  else show((current + 1) % cards.length);
}

function progress() {
  const p = paneOf(current);
  if (isVideo(p)) return p.duration ? p.currentTime / p.duration : 0;
  return (performance.now() - paneStart) / REMOTE_MS;
}

function tick() {
  const f = progress();
  const card = cards[current];
  card.style.setProperty('--progress', Math.min(f, 1));
  card.classList.toggle('held', hovered === current);
  if (!isVideo(paneOf(current)) && f >= 1) finished();
  requestAnimationFrame(tick);
}

for (const p of panes.values()) {
  if (isVideo(p)) p.addEventListener('ended', () => p === paneOf(current) && finished());
}

cards.forEach((card, i) => {
  // pointerType check: on touch screens a tap also fires pointerenter, and would then hold
  // the card forever because no pointerleave follows until the next tap elsewhere.
  card.addEventListener('pointerenter', (e) => {
    if (e.pointerType !== 'mouse') return;
    hovered = i;
    if (i !== current) show(i);
  });
  card.addEventListener('pointerleave', () => {
    if (hovered === i) hovered = -1;
  });
  card.addEventListener('click', () => i !== current && show(i));
  card.addEventListener('focus', () => i !== current && show(i));
});

// Scale the drawn phone to the stage height (its contents are sized in px).
new ResizeObserver(() => {
  stage.style.setProperty('--phone-scale', Math.min(1, (stage.clientHeight * 0.9) / 560));
}).observe(stage);

show(0);
requestAnimationFrame(tick);
