"""
bruno_chess.py  —  Standalone Chess vs Bruno Engine
=====================================================
Install:  pip install flask chess
Run:      python bruno_chess.py
          Browser opens automatically at http://localhost:5000

Engine:   bruno_v5.py  (must be in the same directory)
          Swap for any other engine file that exposes get_bruno_move(board, depth).
"""

import chess
import time
import threading
import webbrowser
from flask import Flask, jsonify, request, Response

# ─────────────────────────────────────────────────────────────────────────────
#  Import the Bruno engine from an external file.
#  The only requirement is that the engine module exposes:
#      get_bruno_move(board: chess.Board, depth: int) -> chess.Move
# ─────────────────────────────────────────────────────────────────────────────
try:
    from bruno_v5 import get_bruno_move
    ENGINE_NAME = "Bruno v5"
except ImportError as e:
    raise SystemExit(
        f"\n[ERROR] Could not import engine from bruno_v5.py:\n  {e}\n"
        "Make sure bruno_v5.py is in the same directory as bruno_chess.py."
    )

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Board helpers
# ─────────────────────────────────────────────────────────────────────────────

_PT = {chess.PAWN:'p', chess.KNIGHT:'n', chess.BISHOP:'b',
       chess.ROOK:'r', chess.QUEEN:'q', chess.KING:'k'}


def board_dict(board):
    return {chess.square_name(sq): {'color': 'w' if p.color else 'b', 'type': _PT[p.piece_type]}
            for sq in chess.SQUARES if (p := board.piece_at(sq))}


def legal_list(board):
    return [{'from': chess.square_name(m.from_square),
             'to':   chess.square_name(m.to_square),
             'uci':  m.uci(),
             'promotion': m.promotion is not None}
            for m in board.legal_moves]


def check_sq(board):
    if board.is_check():
        k = board.king(board.turn)
        return chess.square_name(k) if k is not None else None
    return None


def state(board, history, captured, last_move=None):
    over = board.is_game_over()
    return {'board': board_dict(board), 'fen': board.fen(),
            'turn': 'white' if board.turn == chess.WHITE else 'black',
            'history': history, 'legal_moves': legal_list(board),
            'last_move': last_move, 'captured': captured,
            'check_square': check_sq(board),
            'is_checkmate': board.is_checkmate(),
            'game_over': over, 'result': board.result() if over else None}


def record_capture(board, move, captured):
    p = board.piece_at(move.to_square)
    if p:
        captured['black' if p.color == chess.BLACK else 'white'].append(_PT[p.piece_type])
    if board.is_en_passant(move):
        ep = chess.square(move.to_square % 8, chess.square_rank(move.from_square))
        ep_p = board.piece_at(ep)
        if ep_p:
            captured['black' if ep_p.color == chess.BLACK else 'white'].append('p')


# ─────────────────────────────────────────────────────────────────────────────
#  Flask API
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/api/new_game', methods=['POST'])
def api_new_game():
    return jsonify(state(chess.Board(), [], {'white': [], 'black': []}))


@app.route('/api/move', methods=['POST'])
def api_move():
    d        = request.get_json()
    board    = chess.Board(d['fen'])
    history  = d.get('history', [])
    captured = d.get('captured', {'white': [], 'black': []})
    depth    = int(d.get('depth', 4))

    try:
        pm = chess.Move.from_uci(d['move_uci'])
        if pm not in board.legal_moves:
            return jsonify({'error': 'Illegal move'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    record_capture(board, pm, captured)
    history.append(board.san(pm))
    p_from = chess.square_name(pm.from_square)
    p_to   = chess.square_name(pm.to_square)
    board.push(pm)

    if board.is_game_over():
        return jsonify(state(board, history, captured, {'from': p_from, 'to': p_to}))

    t0 = time.time()
    bm = get_bruno_move(board, depth)
    print(f"  Bruno ▶ {board.san(bm)}  ({time.time()-t0:.2f}s)")

    record_capture(board, bm, captured)
    history.append(board.san(bm))
    b_from = chess.square_name(bm.from_square)
    b_to   = chess.square_name(bm.to_square)
    board.push(bm)

    return jsonify(state(board, history, captured, {'from': b_from, 'to': b_to}))


@app.route('/api/undo', methods=['POST'])
def api_undo():
    """
    Undo fix: the client maintains a fenHistory[] stack and sends the FEN
    from 2 moves ago as prev_fen. We reconstruct state directly from that
    FEN — no board.pop() is needed (chess.Board(fen) has no move stack).
    """
    d        = request.get_json()
    fen      = d.get('prev_fen', chess.STARTING_FEN)
    history  = d.get('history', [])
    captured = d.get('captured', {'white': [], 'black': []})
    board    = chess.Board(fen)
    return jsonify(state(board, history, captured, None))


# ─────────────────────────────────────────────────────────────────────────────
#  Embedded HTML
# ─────────────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bruno Chess</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:         #2b2b2b;
  --surface:    #232323;
  --surface2:   #2e2e2e;
  --border:     #3a3a3a;
  --border2:    #444;
  --light-sq:   #eeeed2;
  --dark-sq:    #769656;
  --text:       #dedede;
  --text-dim:   #888;
  --text-muted: #555;
  --accent:     #81b64c;
  --accent-dim: #55792f;
  --gold:       #c9a84c;
  --danger:     #c0392b;
  --thinking:   #b58863;
  --sq:         88px;
}

html, body { height: 100%; background: var(--bg); color: var(--text);
  font-family: 'IBM Plex Sans', sans-serif; font-weight: 300; }

/* subtle grain */
body::after {
  content:''; position:fixed; inset:0; pointer-events:none; z-index:0;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.035'/%3E%3C/svg%3E");
  opacity:.5;
}

.app {
  position:relative; z-index:1; min-height:100vh;
  display:flex; flex-direction:column; align-items:center;
  padding:28px 24px 48px; gap:24px;
}

/* ── Header ── */
header {
  width:100%; max-width:1120px;
  display:flex; align-items:flex-end; justify-content:space-between;
  border-bottom:1px solid var(--border); padding-bottom:14px;
}
.hd-title {
  font-family:'Playfair Display', serif;
  font-size:2.5rem; font-weight:700; color:#fff; line-height:1;
}
.hd-title em { color:var(--accent); font-style:italic; }
.hd-sub {
  font-family:'IBM Plex Mono', monospace; font-size:0.6rem;
  color:var(--text-muted); letter-spacing:.13em; text-transform:uppercase; margin-top:5px;
}
.hd-right {
  font-family:'IBM Plex Mono', monospace; font-size:0.6rem;
  color:var(--text-muted); text-align:right; line-height:1.9; letter-spacing:.05em;
}
.hd-right strong { color:var(--text-dim); font-weight:500; }

/* ── Main ── */
.main { display:flex; gap:28px; align-items:flex-start; width:100%; max-width:1120px; }

/* ── Player bars ── */
.player-bar {
  display:flex; align-items:center; gap:10px; padding:9px 14px;
  background:var(--surface); border:1px solid var(--border);
  width:calc(var(--sq) * 8 + 26px);
}
.player-bar.top { border-bottom:none; border-radius:8px 8px 0 0; }
.player-bar.bot { border-top:none;    border-radius:0 0 8px 8px; }
.pdot {
  width:9px; height:9px; border-radius:50%; flex-shrink:0;
}
.white-bar .pdot { background:#f0efe8; box-shadow:0 0 0 2px #777; }
.black-bar .pdot { background:#1c1c1c; box-shadow:0 0 0 2px #555; }
.pinfo { flex:1; }
.pname { font-family:'Playfair Display',serif; font-size:.9rem; font-weight:700; color:#ccc; }
.psub  { font-family:'IBM Plex Mono',monospace; font-size:.58rem;
         color:var(--text-muted); letter-spacing:.1em; text-transform:uppercase; }
.ppip  {
  width:7px; height:7px; border-radius:50%; background:var(--accent);
  opacity:0; transition:opacity .2s; box-shadow:0 0 7px var(--accent);
}
.player-bar.active .ppip { opacity:1; }
.pcap {
  display:flex; flex-wrap:wrap; align-items:center;
  gap:0; overflow:hidden;
  max-height:22px;       /* single row — never grows taller */
  min-width:0; flex:1;
  justify-content:flex-end;
}

/* ── Board ── */
.board-frame { border-left:1px solid var(--border); border-right:1px solid var(--border); display:flex; }
.rank-labels {
  display:flex; flex-direction:column; width:26px;
  background:var(--surface); border-right:1px solid var(--border);
}
.rank-labels span {
  height:var(--sq); display:flex; align-items:center; justify-content:center;
  font-family:'IBM Plex Mono',monospace; font-size:.58rem; color:var(--text-muted); user-select:none;
}
.board-wrap { display:flex; flex-direction:column; }
#board {
  display:grid;
  grid-template-columns:repeat(8,var(--sq));
  grid-template-rows:repeat(8,var(--sq));
  cursor:pointer;
}
.file-labels {
  display:flex; background:var(--surface); border-top:1px solid var(--border);
}
.file-labels span {
  width:var(--sq); height:24px; display:flex; align-items:center; justify-content:center;
  font-family:'IBM Plex Mono',monospace; font-size:.58rem; color:var(--text-muted); user-select:none;
}

/* ── Squares ── */
.sq {
  width:var(--sq); height:var(--sq);
  display:flex; align-items:center; justify-content:center;
  position:relative; user-select:none;
}
.sq.light { background:var(--light-sq); }
.sq.dark  { background:var(--dark-sq);  }
.sq.sel   { background:#f6f669 !important; }
.sq.lm-light { background:color-mix(in srgb,#f6f669 38%,var(--light-sq) 62%) !important; }
.sq.lm-dark  { background:color-mix(in srgb,#f6f669 38%,var(--dark-sq)  62%) !important; }

/* check: flash red once then fade back to square colour */
@keyframes chk { 0%,55%{background:rgba(192,57,43,.82)!important} 100%{background:inherit} }
.sq.check-flash { animation:chk 1.5s ease-out forwards; }
/* checkmate: stays red */
.sq.checkmate { background:rgba(192,57,43,.78) !important; }

.sq.legal::after {
  content:''; position:absolute; width:27px; height:27px; border-radius:50%;
  background:rgba(0,0,0,.17); pointer-events:none; z-index:1;
}
.sq.lcap::after {
  content:''; position:absolute; inset:0; border-radius:50%;
  border:8px solid rgba(0,0,0,.18); pointer-events:none; z-index:1;
}

/* ── Pieces ── */
.piece { font-size:62px; line-height:1; z-index:2; pointer-events:none; display:block; }
.wp { color:#fff; text-shadow:0 0 2px #000,0 0 5px #111,1px 2px 4px rgba(0,0,0,.9);
      filter:drop-shadow(0 2px 3px rgba(0,0,0,.65)); }
.bp { color:#111; text-shadow:0 1px 3px rgba(0,0,0,.3); }

/* ── Sidebar ── */
.sidebar { flex:1; display:flex; flex-direction:column; gap:14px; min-width:272px; max-width:310px; }

.card { background:var(--surface); border:1px solid var(--border); border-radius:8px; overflow:hidden; }
.card-hd {
  padding:9px 15px; border-bottom:1px solid var(--border);
  display:flex; align-items:center; justify-content:space-between;
}
.clabel {
  font-family:'IBM Plex Mono',monospace; font-size:.58rem; font-weight:500;
  letter-spacing:.16em; text-transform:uppercase; color:var(--text-muted);
}
.cbody { padding:13px 15px; }

/* status */
#status {
  font-size:.8rem; line-height:1.6; min-height:38px;
  display:flex; align-items:center; gap:8px;
}
#status.thinking { color:var(--thinking); }
#status.error    { color:var(--danger);   }
#status.gameover { font-family:'Playfair Display',serif; font-size:.95rem; color:var(--gold); }
.spin {
  width:11px; height:11px; border:2px solid var(--thinking);
  border-top-color:transparent; border-radius:50%;
  animation:spin .65s linear infinite; flex-shrink:0;
}
@keyframes spin { to { transform:rotate(360deg); } }

/* depth */
.depth-row { display:flex; align-items:center; gap:12px; }
.depth-row label { font-family:'IBM Plex Mono',monospace; font-size:.68rem; color:var(--text-dim); white-space:nowrap; }
#depth-val { font-family:'Playfair Display',serif; font-size:1.35rem; font-weight:700; color:var(--accent); width:26px; text-align:center; }
input[type=range] { flex:1; accent-color:var(--accent); cursor:pointer; }

/* buttons */
.btn-row { display:flex; gap:8px; }
.btn {
  flex:1; padding:9px 6px;
  border:1px solid transparent; border-radius:5px;
  font-family:'IBM Plex Mono',monospace; font-size:.65rem; font-weight:500;
  letter-spacing:.08em; text-transform:uppercase; cursor:pointer; transition:all .14s;
}
.btn:hover:not(:disabled){ filter:brightness(1.2); transform:translateY(-1px); }
.btn:disabled { opacity:.28; cursor:default; }
.btn.primary   { background:var(--accent); color:#0e0e0e; border-color:var(--accent); }
.btn.secondary { background:transparent;   color:var(--text-dim); border-color:var(--border2); }
.btn.secondary:hover:not(:disabled){ border-color:var(--accent); color:var(--accent); }

/* history */
.hist-nav { display:flex; gap:5px; }
.nav-btn {
  width:22px; height:22px; background:transparent;
  border:1px solid var(--border2); border-radius:4px;
  color:var(--text-dim); font-size:.75rem; cursor:pointer;
  display:flex; align-items:center; justify-content:center;
  transition:all .12s; padding:0; line-height:1;
}
.nav-btn:hover:not(:disabled){ border-color:var(--accent); color:var(--accent); }
.nav-btn:disabled{ opacity:.18; cursor:default; }

#log {
  font-family:'IBM Plex Mono',monospace; font-size:.7rem;
  max-height:230px; overflow-y:auto; padding:2px 0;
}
#log::-webkit-scrollbar { width:3px; }
#log::-webkit-scrollbar-thumb { background:var(--border2); border-radius:99px; }

.mp {
  display:grid; grid-template-columns:26px 1fr 1fr;
  gap:2px; padding:2px 0; border-radius:3px; transition:background .1s;
}
.mp:hover { background:var(--surface2); }
.mn { color:var(--text-muted); padding-left:4px; line-height:1.9; font-size:.65rem; }
.mc {
  padding:2px 6px; border-radius:3px; cursor:pointer;
  color:#999; transition:background .1s,color .1s; line-height:1.9;
}
.mc:hover  { background:var(--surface2); color:var(--text); }
.mc.active { background:var(--accent-dim); color:#fff; }

/* promo */
#promo {
  display:none; position:fixed; inset:0;
  background:rgba(0,0,0,.88); z-index:999;
  align-items:center; justify-content:center; backdrop-filter:blur(4px);
}
#promo.open { display:flex; }
.promo-box {
  background:var(--surface); border:1px solid var(--border2);
  border-radius:12px; padding:32px; text-align:center;
}
.promo-box h3 { font-family:'Playfair Display',serif; font-size:1.15rem; margin-bottom:20px; }
.promo-row { display:flex; gap:12px; }
.pb {
  width:72px; height:72px; font-size:50px;
  background:var(--surface2); border:1px solid var(--border2); border-radius:8px;
  cursor:pointer; display:flex; align-items:center; justify-content:center;
  color:#fff; text-shadow:0 0 3px #000; transition:border-color .12s,transform .12s;
}
.pb:hover { border-color:var(--accent); transform:scale(1.07); }

footer {
  font-family:'IBM Plex Mono',monospace; font-size:.56rem;
  color:var(--text-muted); letter-spacing:.12em; text-transform:uppercase; margin-top:4px;
}
</style>
</head>
<body>
<div class="app">

<!-- Header -->
<header>
  <div>
    <div class="hd-title">Chess with <em>Bruno</em></div>
    <div class="hd-sub">Minimax &middot; Alpha-Beta &middot; SEE &middot; Quiescence &middot; Iterative Deepening</div>
  </div>
  <div class="hd-right">
    <div>A simple brute force engine to play chess.</div>
    <div>Created by <strong>Shankhadeep Saha</strong></div>
    <div style="margin-top:2px;color:var(--text-muted)">Bruno v5 &nbsp;&middot;&nbsp; localhost:5000</div>
  </div>
</header>

<!-- Main -->
<div class="main">

  <!-- Board column -->
  <div style="display:flex;flex-direction:column;gap:0;flex-shrink:0">

    <!-- Bruno (Black) -->
    <div class="player-bar black-bar top" id="tag-b">
      <div class="pdot"></div>
      <div class="pinfo">
        <div class="pname">Bruno</div>
        <div class="psub">Engine &middot; Black</div>
      </div>
      <div class="pcap bp" id="cap-b"></div>
      <div class="ppip"></div>
    </div>

    <div class="board-frame">
      <div class="rank-labels" id="rl"></div>
      <div class="board-wrap">
        <div id="board"></div>
        <div class="file-labels" id="fl"></div>
      </div>
    </div>

    <!-- You (White) -->
    <div class="player-bar white-bar bot active" id="tag-w">
      <div class="pdot"></div>
      <div class="pinfo">
        <div class="pname">You</div>
        <div class="psub">Human &middot; White</div>
      </div>
      <div class="pcap wp" id="cap-w"></div>
      <div class="ppip"></div>
    </div>

  </div>

  <!-- Sidebar -->
  <div class="sidebar">

    <div class="card">
      <div class="card-hd"><span class="clabel">Status</span></div>
      <div class="cbody"><div id="status">Your turn. Click a piece to move.</div></div>
    </div>

    <div class="card">
      <div class="card-hd"><span class="clabel">Search Depth</span></div>
      <div class="cbody">
        <div class="depth-row">
          <label>Depth</label>
          <input type="range" id="ds" min="1" max="6" value="4">
          <div id="depth-val">4</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-hd"><span class="clabel">Controls</span></div>
      <div class="cbody">
        <div class="btn-row">
          <button class="btn primary"   id="btn-new">New Game</button>
          <button class="btn secondary" id="btn-undo">Undo <span id="undo-count" style="opacity:.55;font-size:.6rem"></span></button>
          <button class="btn secondary" id="btn-flip">Flip</button>
        </div>
      </div>
    </div>

    <div class="card" style="flex:1">
      <div class="card-hd">
        <span class="clabel">Move History</span>
        <div class="hist-nav">
          <button class="nav-btn" id="nav-first" title="First">&#171;</button>
          <button class="nav-btn" id="nav-prev"  title="Previous (&#8592;)">&#8249;</button>
          <button class="nav-btn" id="nav-next"  title="Next (&#8594;)">&#8250;</button>
          <button class="nav-btn" id="nav-last"  title="Latest">&#187;</button>
        </div>
      </div>
      <div class="cbody">
        <div id="log"><span style="color:var(--text-muted)">—</span></div>
      </div>
    </div>

  </div>
</div>

<footer>Bruno Chess Engine &nbsp;&middot;&nbsp; Python / Flask &nbsp;&middot;&nbsp; python-chess</footer>

</div><!-- /app -->

<!-- Promotion modal -->
<div id="promo">
  <div class="promo-box">
    <h3>Promote Pawn</h3>
    <div class="promo-row" id="pr"></div>
  </div>
</div>

<script>
const G={wK:'♔',wQ:'♕',wR:'♖',wB:'♗',wN:'♘',wP:'♙',bK:'♚',bQ:'♛',bR:'♜',bB:'♝',bN:'♞',bP:'♟'};

let gs=null, sel=null, legals=[], lastMove=null, flipped=false, busy=false, pendingPromo=null;
let undoCount=0;

// fenHistory[i] = FEN of the position BEFORE move i was played.
// fenHistory[0] = starting FEN.
// After move i is made, fenHistory[i+1] = resulting FEN.
let fenHistory=[], viewIdx=-1;  // viewIdx=-1 means live position

// ── Board setup ────────────────────────────────────────────────────────────
function sqn(r,f){ return 'abcdefgh'[f]+(r+1); }

function mkSquares(){
  const b=document.getElementById('board'); b.innerHTML='';
  for(let r=7;r>=0;r--) for(let f=0;f<8;f++){
    const d=document.createElement('div');
    d.dataset.r=r; d.dataset.f=f;
    d.addEventListener('click',onClick);
    b.appendChild(d);
  }
}

function mkLabels(){
  const rl=document.getElementById('rl'), fl=document.getElementById('fl');
  rl.innerHTML=fl.innerHTML='';
  (flipped?[1,2,3,4,5,6,7,8]:[8,7,6,5,4,3,2,1]).forEach(n=>{
    const s=document.createElement('span'); s.textContent=n; rl.appendChild(s);
  });
  (flipped?['h','g','f','e','d','c','b','a']:['a','b','c','d','e','f','g','h']).forEach(c=>{
    const s=document.createElement('span'); s.textContent=c; fl.appendChild(s);
  });
}

// ── Render ─────────────────────────────────────────────────────────────────
function render(boardData, checkSq, isMate, lm){
  const bd  = boardData!==undefined ? boardData  : (gs?gs.board:{});
  const csq = checkSq  !==undefined ? checkSq   : (gs?gs.check_square:null);
  const mate= isMate   !==undefined ? isMate    : (gs?gs.is_checkmate:false);
  const lmv = lm       !==undefined ? lm        : lastMove;

  document.querySelectorAll('#board > div').forEach((el,i)=>{
    const row=Math.floor(i/8), col=i%8;
    const rank=flipped?row:7-row, file=flipped?7-col:col;
    el.dataset.r=rank; el.dataset.f=file;
    const name=sqn(rank,file);
    const isLight=(rank+file)%2!==0;

    el.className='sq '+(isLight?'light':'dark');

    if(lmv&&(name===lmv.from||name===lmv.to))
      el.classList.add(isLight?'lm-light':'lm-dark');

    if(viewIdx===-1){
      if(name===sel) el.classList.add('sel');
      const lg=legals.find(m=>m.to===name);
      if(lg) el.classList.add(bd[name]?'lcap':'legal');
    }

    if(csq&&name===csq){
      if(mate){
        el.classList.add('checkmate');
      } else {
        // Remove any existing flash class first so animation restarts cleanly
        el.classList.remove('check-flash');
        void el.offsetWidth; // reflow to restart animation
        el.classList.add('check-flash');
        setTimeout(()=>el.classList.remove('check-flash'), 1520);
      }
    }

    el.innerHTML='';
    const p=bd[name];
    if(p){
      const s=document.createElement('span');
      s.className='piece '+(p.color==='w'?'wp':'bp');
      s.textContent=G[p.color+p.type.toUpperCase()]||'?';
      el.appendChild(s);
    }
  });
}

function renderLog(){
  const h=gs?(gs.history||[]):[], log=document.getElementById('log');
  if(!h.length){ log.innerHTML='<span style="color:var(--text-muted)">—</span>'; updateNav(); return; }
  let html='';
  for(let i=0;i<h.length;i+=2){
    const wa=viewIdx===i, ba=viewIdx===i+1;
    html+=`<div class="mp">
      <span class="mn">${Math.floor(i/2)+1}.</span>
      <span class="mc${wa?' active':''}" data-idx="${i}">${h[i]||''}</span>
      <span class="mc${ba?' active':''}" data-idx="${i+1}">${h[i+1]||''}</span>
    </div>`;
  }
  log.innerHTML=html;
  log.querySelectorAll('.mc').forEach(el=>{
    el.addEventListener('click',()=>{
      const idx=+el.dataset.idx;
      if(el.textContent.trim()&&idx<h.length) jumpTo(idx);
    });
  });
  if(viewIdx===-1) log.scrollTop=log.scrollHeight;
  updateNav();
}

function renderCap(){
  const cap=gs?(gs.captured||{white:[],black:[]}):{white:[],black:[]};
  // White's captures = black pieces taken by white; Bruno's captures = white pieces taken by Bruno
  document.getElementById('cap-w').innerHTML=
    (cap.black||[]).map(t=>`<span class="piece bp" style="font-size:18px;line-height:1">${G['b'+t.toUpperCase()]||t}</span>`).join('');
  document.getElementById('cap-b').innerHTML=
    (cap.white||[]).map(t=>`<span class="piece wp" style="font-size:18px;line-height:1">${G['w'+t.toUpperCase()]||t}</span>`).join('');
}

function renderUndoCount(){
  const el=document.getElementById('undo-count');
  el.textContent = undoCount > 0 ? `×${undoCount}` : '';
}

function setTags(){
  document.getElementById('tag-w').classList.toggle('active',gs&&gs.turn==='white'&&!gs.game_over&&viewIdx===-1);
  document.getElementById('tag-b').classList.toggle('active',gs&&gs.turn==='black'&&!gs.game_over&&viewIdx===-1);
}

function status(msg,cls='',spin=false){
  const el=document.getElementById('status');
  el.className=cls;
  el.innerHTML=(spin?'<div class="spin"></div>':'')+msg;
}

// ── History nav ────────────────────────────────────────────────────────────
function jumpTo(idx){
  const h=gs?(gs.history||[]):[];
  if(idx<0||idx>=h.length) return;
  viewIdx=idx;
  const fen=fenHistory[idx+1];
  if(!fen){ jumpToLive(); return; }
  render(parseFen(fen), null, false, null);
  renderLog(); setTags();
}

function jumpToLive(){
  viewIdx=-1;
  lastMove=gs?(gs.last_move||null):null;
  render(); renderLog(); setTags();
}

function updateNav(){
  const h=(gs?gs.history||[]:[]), len=h.length, live=viewIdx===-1;
  document.getElementById('nav-first').disabled = len===0||(viewIdx===0);
  document.getElementById('nav-prev').disabled  = len===0||(viewIdx===0);
  document.getElementById('nav-next').disabled  = live;
  document.getElementById('nav-last').disabled  = live;
}

// Minimal FEN → board dict
function parseFen(fen){
  const bd={}, rows=fen.split(' ')[0].split('/');
  for(let r=0;r<8;r++){
    const rank=7-r; let file=0;
    for(const ch of rows[r]){
      if(ch>='1'&&ch<='8'){ file+=+ch; }
      else {
        bd[sqn(rank,file)]={color:ch===ch.toUpperCase()?'w':'b',type:ch.toLowerCase()};
        file++;
      }
    }
  }
  return bd;
}

// ── API ────────────────────────────────────────────────────────────────────
async function api(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

// ── New game ───────────────────────────────────────────────────────────────
async function newGame(){
  if(busy) return;
  sel=null; legals=[]; lastMove=null; pendingPromo=null; fenHistory=[]; viewIdx=-1; undoCount=0; busy=true;
  try{
    gs=await api('/api/new_game',{});
    fenHistory=[gs.fen];
    render(); renderLog(); renderCap(); setTags(); renderUndoCount();
    status('Your turn. Click a piece to move.');
  } catch(e){ status('Server error: '+e.message,'error'); }
  busy=false;
}

// ── Local preview ──────────────────────────────────────────────────────────
function applyLocal(uci){
  const from=uci.slice(0,2),to=uci.slice(2,4),promo=uci[4]||null;
  const piece=gs.board[from]; if(!piece) return;
  if(piece.type==='p'&&from[0]!==to[0]&&!gs.board[to]) delete gs.board[to[0]+from[1]];
  if(piece.type==='k'){
    if(from==='e1'&&to==='g1'){gs.board['f1']=gs.board['h1'];delete gs.board['h1'];}
    if(from==='e1'&&to==='c1'){gs.board['d1']=gs.board['a1'];delete gs.board['a1'];}
    if(from==='e8'&&to==='g8'){gs.board['f8']=gs.board['h8'];delete gs.board['h8'];}
    if(from==='e8'&&to==='c8'){gs.board['d8']=gs.board['a8'];delete gs.board['a8'];}
  }
  delete gs.board[from];
  gs.board[to]=promo?{color:piece.color,type:promo}:piece;
  lastMove={from,to}; sel=null; legals=[];
}

// ── Do move ────────────────────────────────────────────────────────────────
async function doMove(uci){
  busy=true; viewIdx=-1;
  const fenBefore=gs.fen;
  applyLocal(uci);
  gs.turn='black'; gs.check_square=null; gs.legal_moves=[];
  render(); renderLog(); renderCap(); setTags();
  status('Bruno is thinking\u2026','thinking',true);

  try{
    const depth=+document.getElementById('ds').value;
    const prev=gs;
    gs=await api('/api/move',{fen:fenBefore,move_uci:uci,depth,history:prev.history||[],captured:prev.captured||{white:[],black:[]}});

    // Sync fenHistory with actual move count
    // history grows by 2 (player + Bruno), so push 2 FEN snapshots
    // We only have fenBefore (pre-player) and gs.fen (post-Bruno).
    // Push them to match history indices:
    //   fenHistory[n]   = FEN before player's move   (index of player's history entry)
    //   fenHistory[n+1] = FEN after Bruno's move      (index of Bruno's history entry)
    // This means browsing to the player's move shows the board before that move — acceptable.
    const hlen=(gs.history||[]).length;
    while(fenHistory.length<=hlen){
      fenHistory.push(gs.fen);
    }
    // Overwrite the second-to-last with fenBefore so player's move shows correct pre-move board
    if(fenHistory.length>=2) fenHistory[fenHistory.length-2]=fenBefore;

    lastMove=gs.last_move||null;
    render(); renderLog(); renderCap(); setTags();
    if(gs.game_over) status(endMsg(gs.result),'gameover');
    else status('Your turn.');
  } catch(e){ status('Error: '+e.message,'error'); }
  busy=false;
}

// ── Undo ───────────────────────────────────────────────────────────────────
async function undo(){
  if(!gs||busy) return;
  const h=gs.history||[];
  if(h.length<2) return;
  sel=null; legals=[]; viewIdx=-1; busy=true;

  const newHistory=h.slice(0,-2);
  const newFenHistory=fenHistory.slice(0,-2);
  const prevFen=newFenHistory[newFenHistory.length-1]||fenHistory[0];

  try{
    gs=await api('/api/undo',{
      prev_fen:prevFen,
      history:newHistory,
      captured:gs.captured   // minor: captured list isn't decremented, cosmetic only
    });
    fenHistory=newFenHistory;
    lastMove=null;
    undoCount++;
    render(); renderLog(); renderCap(); setTags(); renderUndoCount();
    status('Move undone. Your turn.');
  } catch(e){ status('Undo failed: '+e.message,'error'); }
  busy=false;
}

// ── Click ──────────────────────────────────────────────────────────────────
function onClick(e){
  if(!gs||busy||gs.game_over||gs.turn!=='white'||viewIdx!==-1) return;
  const r=+e.currentTarget.dataset.r, f=+e.currentTarget.dataset.f, name=sqn(r,f);
  if(sel){
    const lg=legals.find(m=>m.to===name);
    if(lg){ lg.promotion?showPromo(lg):doMove(lg.uci); return; }
    const p=gs.board[name];
    if(p&&p.color==='w'){ sel=name; legals=gs.legal_moves.filter(m=>m.from===name); render(); return; }
    sel=null; legals=[]; render(); return;
  }
  const p=gs.board[name];
  if(p&&p.color==='w'){ sel=name; legals=gs.legal_moves.filter(m=>m.from===name); render(); }
}

// ── Promotion ──────────────────────────────────────────────────────────────
function showPromo(lg){
  pendingPromo=lg;
  const row=document.getElementById('pr'); row.innerHTML='';
  [['q','♕'],['r','♖'],['b','♗'],['n','♘']].forEach(([p,sym])=>{
    const btn=document.createElement('button');
    btn.className='pb'; btn.textContent=sym;
    btn.onclick=()=>{ document.getElementById('promo').classList.remove('open'); doMove(lg.uci.slice(0,4)+p); };
    row.appendChild(btn);
  });
  document.getElementById('promo').classList.add('open');
}

function endMsg(r){
  return r==='1-0'?'🏆 You win! Checkmate.':r==='0-1'?'🤖 Bruno wins!':'🤝 Draw!';
}

// ── Boot ───────────────────────────────────────────────────────────────────
window.onload=()=>{
  mkSquares(); mkLabels(); newGame();
  document.getElementById('btn-new').onclick  = newGame;
  document.getElementById('btn-undo').onclick = undo;
  document.getElementById('btn-flip').onclick = ()=>{ flipped=!flipped; mkLabels(); render(); };
  document.getElementById('ds').oninput = e=>{ document.getElementById('depth-val').textContent=e.target.value; };

  document.getElementById('nav-first').onclick=()=>{ const h=gs?gs.history||[]:[];if(h.length)jumpTo(0); };
  document.getElementById('nav-prev').onclick=()=>{
    const h=gs?gs.history||[]:[];
    if(!h.length) return;
    if(viewIdx===-1) jumpTo(h.length-1);
    else if(viewIdx>0) jumpTo(viewIdx-1);
  };
  document.getElementById('nav-next').onclick=()=>{
    if(viewIdx===-1) return;
    const h=gs?gs.history||[]:[];
    if(viewIdx<h.length-1) jumpTo(viewIdx+1); else jumpToLive();
  };
  document.getElementById('nav-last').onclick=()=>jumpToLive();

  document.addEventListener('keydown',e=>{
    if(e.target.tagName==='INPUT') return;
    if(e.key==='ArrowLeft')  document.getElementById('nav-prev').click();
    if(e.key==='ArrowRight') document.getElementById('nav-next').click();
  });
};
</script>
</body>
</html>"""


@app.route('/')
def index():
    return Response(HTML, mimetype='text/html')


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def open_browser():
    time.sleep(1.2)
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    print()
    print("=" * 52)
    print(f"   ♟  Bruno Chess Engine — {ENGINE_NAME}  ♟")
    print("=" * 52)
    print("   Opening browser at http://localhost:5000")
    print("   Press Ctrl+C to quit.")
    print("=" * 52)
    print()
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
