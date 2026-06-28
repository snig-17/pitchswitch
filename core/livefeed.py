"""Live feed: a self-contained HTML5 canvas that animates the broadcast.

`build_broadcast` renders the unified multi-match tracking broadcast (from
`metrica.build_unified_broadcast`) as one self-contained canvas that runs its
own 60fps requestAnimationFrame loop — both games, switching client-side per
the Director's schedule, with the live-danger panel, Granite narration, Coach,
and play-by-play captions. No Streamlit reruns during playback.

All embedded data (including LLM-generated narration and Coach text) goes
through `_safe_embed`, which neutralizes script-context breakout.
"""

from __future__ import annotations

import json


def _safe_embed(data) -> str:
    """JSON for embedding inside an HTML <script> block. json.dumps leaves
    '<' intact, so a "</script>" in any string (Granite narration, Coach text,
    captions) would break out of the script tag. Escaping '<' and '>' as \\u
    sequences keeps it valid JS while making script-context breakout impossible.
    (json.dumps defaults to ensure_ascii=True, so U+2028/U+2029 are already
    \\u-escaped — no separate guard needed.)"""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e")


_BROADCAST_TEMPLATE = """
<div style="background:#0d1f12;border-radius:8px;padding:6px;position:relative">
<canvas id="bc" width="900" height="560" style="width:100%;height:auto;display:block"></canvas>
<div id="unlock" onclick="unlock()" style="display:none;position:absolute;bottom:12px;
  right:12px;cursor:pointer;background:#ff3b3b;color:#fff;padding:6px 10px;
  border-radius:6px;font:bold 13px sans-serif">&#128266; Tap for commentary</div>
<audio id="au"></audio>
</div>
<script>
const D = __DATA__;
const cv = document.getElementById('bc'), ctx = cv.getContext('2d');
const au = document.getElementById('au'), ub = document.getElementById('unlock');
const W = cv.width, H = cv.height;
const SKIN = '#f0c8a0';        // per-team kit colours now live on each game
const SCHED = D.schedule;       // [[t, gi], ...]
let lastGi = -1, audioOk = false, pendingAudio = null, lastCoachKey = '';
function unlock(){ audioOk = true; ub.style.display='none'; if(pendingAudio) playClip(pendingAudio); }
function playClip(b64){ if(!b64) return; au.src='data:audio/mp3;base64,'+b64;
  au.play().then(()=>{audioOk=true;}).catch(()=>{audioOk=false; pendingAudio=b64; ub.style.display='block';}); }
const t0 = performance.now();
const G0 = D.games[0].frames, START = G0.length ? G0[0].t : 0;
const ENDt = G0.length ? G0[G0.length-1].t : 1;

function pitch(){
  ctx.fillStyle='#15311a'; ctx.fillRect(0,0,W,H);
  for(let s=0;s<6;s++){if(s%2){ctx.fillStyle='rgba(255,255,255,0.025)';ctx.fillRect(s*W/6,0,W/6,H);}}
  ctx.strokeStyle='#cfe8d0'; ctx.lineWidth=2; ctx.globalAlpha=0.9;
  ctx.strokeRect(6,6,W-12,H-12);
  ctx.beginPath(); ctx.moveTo(W/2,6); ctx.lineTo(W/2,H-6); ctx.stroke();
  ctx.beginPath(); ctx.arc(W/2,H/2,60,0,7); ctx.stroke();
  const y1=0.21*H,y2=0.79*H; ctx.strokeRect(6,y1,0.16*W,y2-y1); ctx.strokeRect(W-6-0.16*W,y1,0.16*W,y2-y1);
  ctx.globalAlpha=1;
}
function avatar(x,y,shirt,num,numCol){
  ctx.fillStyle='rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.ellipse(x,y+12,8,2.6,0,0,7); ctx.fill();
  // shirt (with short sleeves) + shorts
  ctx.fillStyle=shirt;
  ctx.beginPath();
  ctx.moveTo(x-8,y-1); ctx.lineTo(x-5,y-4);           // left sleeve
  ctx.lineTo(x-4,y-5); ctx.lineTo(x+4,y-5); ctx.lineTo(x+5,y-4);
  ctx.lineTo(x+8,y-1); ctx.lineTo(x+6,y+3);           // right sleeve
  ctx.lineTo(x+5,y+9); ctx.lineTo(x-5,y+9); ctx.lineTo(x-6,y+3);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle='#26324a'; ctx.fillRect(x-4,y+9,8,4); // shorts
  // head
  ctx.fillStyle=SKIN; ctx.beginPath(); ctx.arc(x,y-8,3.4,0,7); ctx.fill();
  // jersey number
  if(num){ ctx.fillStyle=numCol; ctx.font='bold 6px sans-serif'; ctx.textAlign='center';
    ctx.fillText(num, x, y+4); ctx.textAlign='left'; }
}
function lerp(a,b,f){return a+(b-a)*f;}
function onAir(at){ let gi=0,st=START; for(const s of SCHED){ if(s[0]<=at){gi=s[1];st=s[0];} else break; } return [gi,st]; }
function caption(game, at){ let c=''; for(const e of game.captions){ if(e[0]<=at) c=e[1]; else break; } return c; }
function dangerAt(game, at){ const A=game.danger; if(!A||!A.length) return 0;
  const Fr=game.frames; let j=0; while(j<Fr.length-1 && Fr[j+1].t<=at) j++;
  return A[Math.min(j,A.length-1)]||0; }

function draw(now){
  let at = START + (now-t0)/1000 * D.speed;
  if (at > ENDt){ at = START + ((at-START) % (ENDt-START || 1)); lastGi=-1; }   // loop
  const [gi, switchT] = onAir(at);
  const g = D.games[gi], F = g.frames;
  const reason = g.narration;
  if (gi !== lastGi){ lastGi = gi; if(audioOk) playClip(g.audio); else if(g.audio){pendingAudio=g.audio; ub.style.display='block';} }
  let i=0; while(i<F.length-1 && F[i+1].t<=at) i++;
  const a=F[i], b=F[Math.min(i+1,F.length-1)];
  const span=Math.max(b.t-a.t,0.001), f=Math.max(0,Math.min(1,(at-a.t)/span));

  pitch();
  if(a.b){ const bx=a.b[0]; if(bx>0.62||bx<0.38){
    // danger glow: a red gradient strongest at the threatened goal, fading to
    // nothing by midfield — reads as 'danger here', not a muddy wash over the third
    const right = bx>0.62;
    const g = right ? ctx.createLinearGradient(0.55*W,0,W,0) : ctx.createLinearGradient(0.45*W,0,0,0);
    g.addColorStop(0,'rgba(255,40,40,0)'); g.addColorStop(1,'rgba(255,40,40,0.42)');
    ctx.fillStyle=g;
    if(right) ctx.fillRect(0.55*W,6,0.45*W-6,H-12); else ctx.fillRect(6,6,0.45*W-6,H-12); } }
  const nh=Math.min(a.h.length,b.h.length);
  for(let k=0;k<nh;k++){ const pa=a.h[k],pb=b.h[k]; if(!pa||!pb) continue;
    avatar(lerp(pa[0],pb[0],f)*W, lerp(pa[1],pb[1],f)*H, g.hc, pa[2], g.hn); }
  const na=Math.min(a.a.length,b.a.length);
  for(let k=0;k<na;k++){ const pa=a.a[k],pb=b.a[k]; if(!pa||!pb) continue;
    avatar(lerp(pa[0],pb[0],f)*W, lerp(pa[1],pb[1],f)*H, g.ac, pa[2], g.an); }
  if(a.b&&b.b){ const bx=lerp(a.b[0],b.b[0],f)*W, by=lerp(a.b[1],b.b[1],f)*H;
    ctx.beginPath(); ctx.arc(bx,by,6,0,7); ctx.fillStyle='#fff'; ctx.fill(); ctx.strokeStyle='#000'; ctx.lineWidth=1.5; ctx.stroke(); }

  // overlay
  const mm=Math.floor(at/60), ss=Math.floor(at%60);
  ctx.fillStyle='#fff'; ctx.font='bold 16px sans-serif'; ctx.fillText(g.label+'  \\u25b6 LIVE', 16, 26);
  ctx.fillStyle='#bcd'; ctx.font='13px sans-serif'; ctx.fillText(mm+':'+(ss<10?'0':'')+ss, 16, 46);
  ctx.fillStyle=g.hc; ctx.fillText('\\u25cf '+g.home, 16, H-44);
  ctx.fillStyle=g.ac; ctx.fillText('\\u25cf '+g.away, 26+ctx.measureText('\\u25cf '+g.home).width+18, H-44);

  // Director danger comparison (top-right): one bar per match so the viewer
  // sees the matches competing for the cut in real time. This is the "why"
  // behind every switch, made visible.
  const NG=D.games.length, PANW=236, PANX=W-PANW-12, PANY=12, ROWH=27;
  ctx.fillStyle='rgba(8,20,12,0.82)'; ctx.fillRect(PANX,PANY,PANW,20+NG*ROWH);
  ctx.fillStyle='#9fdcae'; ctx.font='bold 10px sans-serif';
  ctx.fillText('DIRECTOR \\u2014 LIVE DANGER', PANX+8, PANY+13);
  for(let gj=0; gj<NG; gj++){
    const gg=D.games[gj], dv=dangerAt(gg,at), onair=(gj===gi), ry=PANY+20+gj*ROWH;
    ctx.fillStyle=onair?'#fff':'#9fb0c4'; ctx.font=(onair?'bold ':'')+'11px sans-serif';
    const lbl=gg.home+' v '+gg.away;
    ctx.fillText(lbl.length>22?lbl.slice(0,21)+'\\u2026':lbl, PANX+8, ry+8);
    if(onair){ ctx.fillStyle='#ffd400'; ctx.font='bold 9px sans-serif'; ctx.textAlign='right';
      ctx.fillText('\\u25b6 ON AIR', PANX+PANW-8, ry+8); ctx.textAlign='left'; }
    const barX=PANX+8, barY=ry+12, barW=PANW-16, barH=7;
    ctx.fillStyle='rgba(255,255,255,0.12)'; ctx.fillRect(barX,barY,barW,barH);
    ctx.fillStyle=dv>0.5?'#ff3b3b':(dv>0.3?'#ffcc00':'#4da6ff');
    ctx.fillRect(barX,barY,barW*Math.min(dv,1),barH);
  }

  // switch banner (brief, after a cut) — wraps long Granite narration, then
  // shows the danger differential that drove the Director's decision.
  if (at - switchT < 4.5 && reason){
    ctx.font='bold 15px sans-serif';
    const words=reason.split(' '); let lines=[], ln='';
    for(const w of words){ if(ctx.measureText(ln+' '+w).width>W-32){lines.push(ln);ln=w;} else ln=(ln?ln+' '+w:w);} if(ln)lines.push(ln);
    lines=lines.slice(0,2);
    const showWhy = switchT > START + 0.5;     // skip on kick-off
    let dOn=0, dOther=0;
    if(showWhy){ dOn=dangerAt(g,switchT);
      for(let gj=0;gj<NG;gj++){ if(gj!==gi) dOther=Math.max(dOther,dangerAt(D.games[gj],switchT)); } }
    const delta=Math.max(0,dOn-dOther);
    const bh=14+lines.length*20+(showWhy?20:0);
    ctx.fillStyle='rgba(255,59,59,0.88)'; ctx.fillRect(0,58,W,bh);
    ctx.fillStyle='#fff'; ctx.font='bold 15px sans-serif';
    lines.forEach((l,li)=>ctx.fillText((li?'   ':'\\u25b6 ')+l, 16, 78+li*20));
    if(showWhy){ ctx.fillStyle='#ffe08a'; ctx.font='bold 12px sans-serif';
      ctx.fillText('\\u25b2 WHY: danger '+dOn.toFixed(2)+'  (+'+delta.toFixed(2)+' vs the other match)',
                   16, 80+lines.length*20); }
  }

  // play-by-play caption (lower third)
  const cap = caption(g, at);
  if(cap){ ctx.fillStyle='rgba(0,0,0,0.6)'; ctx.fillRect(0,H-30,W,30);
    ctx.fillStyle='#fff'; ctx.font='14px sans-serif'; ctx.fillText(cap, 16, H-10); }

  // Coach: explain a rule event (penalty/foul/card/corner/goal) for ~7s
  const COACH = g.coach || [];
  let ce = null; for(const c of COACH){ if(c[0]<=at && at-c[0]<7) ce=c; else if(c[0]>at) break; }
  if(ce){
    const key = gi+':'+ce[0];
    if(key !== lastCoachKey){ lastCoachKey = key; if(ce[3]) playClip(ce[3]); }
    ctx.font='13px sans-serif';
    const words=('Coach: '+ce[2].replace(/^[A-Z][a-z]+: /,'')).split(' ');
    let lines=[], ln=''; for(const w of words){ if(ctx.measureText(ln+' '+w).width>W-150){lines.push(ln);ln=w;} else ln=(ln?ln+' '+w:w);} if(ln)lines.push(ln);
    lines=lines.slice(0,3);
    const ph=18+lines.length*18, py=H-40-ph;
    ctx.fillStyle='rgba(10,25,15,0.92)'; ctx.fillRect(0,py,W,ph);
    ctx.fillStyle='#ffd400'; ctx.fillRect(0,py,4,ph);
    ctx.fillStyle='#ffd400'; ctx.font='bold 12px sans-serif'; ctx.fillText('COACH', 14, py+15);
    ctx.fillStyle='#eef'; ctx.font='13px sans-serif';
    lines.forEach((l,li)=>ctx.fillText(l, 72, py+15+li*18));
  }
  requestAnimationFrame(draw);
}
if(D.games[0].frames.length) requestAnimationFrame(draw); else pitch();
</script>
"""


def build_broadcast(bdata, speed=1.4, home_color="#4da6ff", away_color="#ff8c42"):
    """Canvas that plays a multi-match tracking broadcast (from
    metrica.build_unified_broadcast): both games, switching client-side per the
    schedule, with the live-danger panel, Granite narration, Coach, and
    play-by-play captions. Self-contained — no Streamlit reruns during playback."""
    games = [{
        "label": gd["label"],
        "home": gd.get("home", "Home"), "away": gd.get("away", "Away"),
        "hc": gd.get("home_color", "#4da6ff"), "hn": gd.get("home_num", "#fff"),
        "ac": gd.get("away_color", "#ff8c42"), "an": gd.get("away_num", "#111"),
        "narration": gd.get("narration", ""), "audio": gd.get("audio"),
        "coach": gd.get("coach", []),
        "danger": [round(d, 3) for d in gd.get("danger", [])],
        "captions": gd.get("captions", []),
        "frames": [{"t": fr.t, "b": list(fr.ball) if fr.ball else None,
                    "h": [list(p) if p else None for p in fr.home],
                    "a": [list(p) if p else None for p in fr.away]}
                   for fr in gd["frames"]],
    } for gd in bdata["games"]]
    data = {"games": games, "schedule": bdata["schedule"], "speed": speed,
            "home_color": home_color, "away_color": away_color}
    return _BROADCAST_TEMPLATE.replace("__DATA__", _safe_embed(data))
