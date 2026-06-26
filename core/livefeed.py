"""Live feed: a client-side HTML5 canvas that animates a match smoothly.

The matplotlib pitch-cam redraws one frame per Streamlit rerun, so it looks
jumpy. This renders the same match data as a self-contained canvas that runs
its own 60fps requestAnimationFrame loop: the ball glides between real event
locations (interpolated, not teleporting) and the involved players are drawn
as team-coloured avatars, with the ball carrier highlighted.

StatsBomb open data only gives event locations (not full 22-player tracking),
so the avatars are the ball carrier plus recently-involved players, and the
ball is what moves continuously.
"""

from __future__ import annotations

import json

# StatsBomb pitch is 120 x 80
_TEMPLATE = """
<div style="background:#0d1f12;border-radius:8px;padding:6px">
<canvas id="cam" width="900" height="560" style="width:100%;height:auto;display:block"></canvas>
</div>
<script>
const D = __DATA__;
const cv = document.getElementById('cam'), ctx = cv.getContext('2d');
const W = cv.width, H = cv.height, PX = W/120, PY = H/80;
const HOME = D.home_color, AWAY = D.away_color, SKIN = '#f0c8a0';
const ev = D.events;            // [[t,x,y,team,isShot,isGoal], ...] sorted by t
const t0 = performance.now();

function pitch() {
  ctx.fillStyle = '#15311a'; ctx.fillRect(0,0,W,H);
  // mowing stripes
  for (let s=0; s<6; s++){ if(s%2){ctx.fillStyle='rgba(255,255,255,0.025)'; ctx.fillRect(s*W/6,0,W/6,H);} }
  ctx.strokeStyle = '#cfe8d0'; ctx.lineWidth = 2; ctx.globalAlpha = 0.9;
  ctx.strokeRect(6,6,W-12,H-12);
  ctx.beginPath(); ctx.moveTo(W/2,6); ctx.lineTo(W/2,H-6); ctx.stroke();
  ctx.beginPath(); ctx.arc(W/2,H/2,9.15*PX,0,7); ctx.stroke();
  // boxes
  const by1=(80-40.3)/2*PY, by2=(80+40.3)/2*PY;
  ctx.strokeRect(6,by1,18*PX,by2-by1);
  ctx.strokeRect(W-6-18*PX,by1,18*PX,by2-by1);
  ctx.globalAlpha = 1;
}

function avatar(x, y, color, scale, alpha, carrier) {
  ctx.globalAlpha = alpha;
  // shadow
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.beginPath(); ctx.ellipse(x, y+11*scale, 7*scale, 2.4*scale, 0,0,7); ctx.fill();
  // body (jersey)
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x-6*scale, y+9*scale);
  ctx.quadraticCurveTo(x-7*scale, y-2*scale, x-3.5*scale, y-3*scale);
  ctx.lineTo(x+3.5*scale, y-3*scale);
  ctx.quadraticCurveTo(x+7*scale, y-2*scale, x+6*scale, y+9*scale);
  ctx.closePath(); ctx.fill();
  // head
  ctx.fillStyle = SKIN;
  ctx.beginPath(); ctx.arc(x, y-7*scale, 3.6*scale, 0, 7); ctx.fill();
  if (carrier) {
    ctx.globalAlpha = alpha; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(x, y+1*scale, 14*scale, 0, 7); ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

function frame(now) {
  const at = D.start_t + (now - t0)/1000 * D.speed;
  // current segment: last event with t <= at
  let i = 0;
  while (i < ev.length-1 && ev[i+1][0] <= at) i++;
  const a = ev[i], b = ev[Math.min(i+1, ev.length-1)];
  const span = Math.max(b[0]-a[0], 0.001);
  const f = Math.max(0, Math.min(1, (at - a[0]) / span));
  const bx = (a[1] + (b[1]-a[1])*f) * PX;
  const by = (a[2] + (b[2]-a[2])*f) * PY;

  pitch();

  // danger glow in the attacking third
  if (D.danger > 0.3) {
    ctx.globalAlpha = Math.min(0.08 + D.danger*0.28, 0.40);
    const g = ctx.createLinearGradient(80*PX,0,W,0);
    g.addColorStop(0,'rgba(255,59,59,0)'); g.addColorStop(1,'rgba(255,59,59,1)');
    ctx.fillStyle = g; ctx.fillRect(80*PX,6,W-80*PX-6,H-12); ctx.globalAlpha = 1;
  }

  // ball trail (last few events up to the interpolated point)
  ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 2.5;
  ctx.beginPath();
  for (let j = Math.max(0,i-4); j <= i; j++) ctx.lineTo(ev[j][1]*PX, ev[j][2]*PY);
  ctx.lineTo(bx, by); ctx.stroke();

  // recently-involved players as avatars (older = fainter)
  for (let j = Math.max(0,i-6); j <= i; j++) {
    const age = (i - j);
    const col = ev[j][3] === 0 ? HOME : AWAY;
    avatar(ev[j][1]*PX, ev[j][2]*PY, col, 1.0, 0.25 + 0.65*(1 - age/7), j === i);
  }

  // shot/goal flash near the action
  if (a[5]) { ctx.fillStyle = '#ffd700'; ctx.font = 'bold 22px sans-serif';
              ctx.fillText('GOAL!', bx-26, by-18); }

  // the ball
  ctx.beginPath(); ctx.arc(bx, by, 6, 0, 7);
  ctx.fillStyle = '#fff'; ctx.fill(); ctx.strokeStyle='#000'; ctx.lineWidth=1.5; ctx.stroke();

  // scorebug + clock
  const mm = Math.floor(at/60);
  ctx.fillStyle = '#fff'; ctx.font = 'bold 15px sans-serif';
  ctx.fillText(D.label + "  " + D.score, 16, 26);
  ctx.fillStyle = '#bcd'; ctx.font = '13px sans-serif';
  ctx.fillText(mm + "'", 16, 46);
  ctx.fillStyle = D.danger>0.5?'#ff3b3b':(D.danger>0.3?'#ffcc00':'#8fbf8f');
  ctx.font = 'bold 15px sans-serif'; ctx.textAlign='right';
  ctx.fillText((D.danger>0.5?'HIGH ':'DANGER ') + D.danger.toFixed(2), W-16, 26);
  ctx.textAlign='left';
  // team key
  ctx.fillStyle = HOME; ctx.fillText('\\u25cf '+D.home, 16, H-16);
  ctx.fillStyle = AWAY; ctx.fillText('\\u25cf '+D.away, 120, H-16);
  if (D.is_fav){ ctx.fillStyle='#ffd700'; ctx.fillText('\\u2605 YOUR TEAM', W-150, H-16); }

  requestAnimationFrame(frame);
}
if (ev.length) requestAnimationFrame(frame);
else { pitch(); }
</script>
"""


_TRACK_TEMPLATE = """
<div style="background:#0d1f12;border-radius:8px;padding:6px">
<canvas id="trk" width="900" height="560" style="width:100%;height:auto;display:block"></canvas>
</div>
<script>
const D = __DATA__;
const cv = document.getElementById('trk'), ctx = cv.getContext('2d');
const W = cv.width, H = cv.height;
const HOME = D.home_color, AWAY = D.away_color, SKIN = '#f0c8a0';
const F = D.frames;             // [{t, b:[x,y]|null, h:[[x,y]...], a:[[x,y]...]}]
const t0 = performance.now(), T0 = F.length ? F[0].t : 0, TEND = F.length ? F[F.length-1].t : 1;

function pitch(){
  ctx.fillStyle='#15311a'; ctx.fillRect(0,0,W,H);
  for(let s=0;s<6;s++){if(s%2){ctx.fillStyle='rgba(255,255,255,0.025)';ctx.fillRect(s*W/6,0,W/6,H);}}
  ctx.strokeStyle='#cfe8d0'; ctx.lineWidth=2; ctx.globalAlpha=0.9;
  ctx.strokeRect(6,6,W-12,H-12);
  ctx.beginPath(); ctx.moveTo(W/2,6); ctx.lineTo(W/2,H-6); ctx.stroke();
  ctx.beginPath(); ctx.arc(W/2,H/2,60,0,7); ctx.stroke();
  const by1=0.21*H, by2=0.79*H;
  ctx.strokeRect(6,by1,0.16*W,by2-by1);
  ctx.strokeRect(W-6-0.16*W,by1,0.16*W,by2-by1);
  ctx.globalAlpha=1;
}
function avatar(x,y,color){
  ctx.fillStyle='rgba(0,0,0,0.35)';
  ctx.beginPath(); ctx.ellipse(x,y+11,7,2.4,0,0,7); ctx.fill();
  ctx.fillStyle=color;
  ctx.beginPath();
  ctx.moveTo(x-6,y+9); ctx.quadraticCurveTo(x-7,y-2,x-3.5,y-3);
  ctx.lineTo(x+3.5,y-3); ctx.quadraticCurveTo(x+7,y-2,x+6,y+9);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle=SKIN; ctx.beginPath(); ctx.arc(x,y-7,3.6,0,7); ctx.fill();
}
function lerp(a,b,f){return a+(b-a)*f;}
function frame(now){
  let at = T0 + (now-t0)/1000 * D.speed;
  if (at > TEND) { at = T0 + ((at - T0) % (TEND - T0 || 1)); }  // loop the window
  let i=0; while(i<F.length-1 && F[i+1].t<=at) i++;
  const a=F[i], b=F[Math.min(i+1,F.length-1)];
  const span=Math.max(b.t-a.t,0.001), f=Math.max(0,Math.min(1,(at-a.t)/span));
  pitch();
  // ball danger glow if near either goal third
  if (a.b){ const bx=a.b[0]; if(bx>0.66||bx<0.34){ctx.globalAlpha=0.18;ctx.fillStyle='rgba(255,59,59,1)';
    if(bx>0.66)ctx.fillRect(0.66*W,6,0.34*W-6,H-12); else ctx.fillRect(6,6,0.34*W-6,H-12); ctx.globalAlpha=1;} }
  // players (interpolated)
  const n=Math.min(a.h.length,b.h.length);
  for(let k=0;k<n;k++) avatar(lerp(a.h[k][0],b.h[k][0],f)*W, lerp(a.h[k][1],b.h[k][1],f)*H, HOME);
  const m=Math.min(a.a.length,b.a.length);
  for(let k=0;k<m;k++) avatar(lerp(a.a[k][0],b.a[k][0],f)*W, lerp(a.a[k][1],b.a[k][1],f)*H, AWAY);
  // ball
  if(a.b&&b.b){ const bx=lerp(a.b[0],b.b[0],f)*W, by=lerp(a.b[1],b.b[1],f)*H;
    ctx.beginPath(); ctx.arc(bx,by,6,0,7); ctx.fillStyle='#fff'; ctx.fill();
    ctx.strokeStyle='#000'; ctx.lineWidth=1.5; ctx.stroke(); }
  // overlay
  const mm=Math.floor(at/60), ss=Math.floor(at%60);
  ctx.fillStyle='#fff'; ctx.font='bold 15px sans-serif';
  ctx.fillText(D.label, 16, 26);
  ctx.fillStyle='#bcd'; ctx.font='13px sans-serif';
  ctx.fillText(mm+":"+(ss<10?'0':'')+ss, 16, 46);
  ctx.fillStyle=HOME; ctx.fillText('\\u25cf '+D.home, 16, H-16);
  ctx.fillStyle=AWAY; ctx.fillText('\\u25cf '+D.away, 120, H-16);
  if(D.caption){ ctx.fillStyle='rgba(0,0,0,0.55)'; ctx.fillRect(0,H-46,W,26);
    ctx.fillStyle='#fff'; ctx.font='14px sans-serif'; ctx.fillText(D.caption, 16, H-28); }
  requestAnimationFrame(frame);
}
if(F.length) requestAnimationFrame(frame); else pitch();
</script>
"""


_BROADCAST_TEMPLATE = """
<div style="background:#0d1f12;border-radius:8px;padding:6px;position:relative">
<canvas id="bc" width="900" height="560" style="width:100%;height:auto;display:block"></canvas>
<div id="unlock" onclick="unlock()" style="display:none;position:absolute;top:10px;
  right:10px;cursor:pointer;background:#ff3b3b;color:#fff;padding:6px 10px;
  border-radius:6px;font:bold 13px sans-serif">&#128266; Tap for commentary</div>
<audio id="au"></audio>
</div>
<script>
const D = __DATA__;
const cv = document.getElementById('bc'), ctx = cv.getContext('2d');
const au = document.getElementById('au'), ub = document.getElementById('unlock');
const W = cv.width, H = cv.height;
const HOME = D.home_color, AWAY = D.away_color, SKIN = '#f0c8a0';
const SCHED = D.schedule;       // [[t, gi], ...]
let lastGi = -1, audioOk = false, pendingAudio = null;
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
function avatar(x,y,color){
  ctx.fillStyle='rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.ellipse(x,y+11,7,2.4,0,0,7); ctx.fill();
  ctx.fillStyle=color; ctx.beginPath();
  ctx.moveTo(x-6,y+9); ctx.quadraticCurveTo(x-7,y-2,x-3.5,y-3);
  ctx.lineTo(x+3.5,y-3); ctx.quadraticCurveTo(x+7,y-2,x+6,y+9); ctx.closePath(); ctx.fill();
  ctx.fillStyle=SKIN; ctx.beginPath(); ctx.arc(x,y-7,3.6,0,7); ctx.fill();
}
function lerp(a,b,f){return a+(b-a)*f;}
function onAir(at){ let gi=0,st=START; for(const s of SCHED){ if(s[0]<=at){gi=s[1];st=s[0];} else break; } return [gi,st]; }
function caption(game, at){ let c=''; for(const e of game.captions){ if(e[0]<=at) c=e[1]; else break; } return c; }

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
  if(a.b){ const bx=a.b[0]; if(bx>0.62||bx<0.38){ctx.globalAlpha=0.18;ctx.fillStyle='rgba(255,59,59,1)';
    if(bx>0.62)ctx.fillRect(0.62*W,6,0.38*W-6,H-12); else ctx.fillRect(6,6,0.38*W-6,H-12); ctx.globalAlpha=1;} }
  const nh=Math.min(a.h.length,b.h.length);
  for(let k=0;k<nh;k++) avatar(lerp(a.h[k][0],b.h[k][0],f)*W, lerp(a.h[k][1],b.h[k][1],f)*H, HOME);
  const na=Math.min(a.a.length,b.a.length);
  for(let k=0;k<na;k++) avatar(lerp(a.a[k][0],b.a[k][0],f)*W, lerp(a.a[k][1],b.a[k][1],f)*H, AWAY);
  if(a.b&&b.b){ const bx=lerp(a.b[0],b.b[0],f)*W, by=lerp(a.b[1],b.b[1],f)*H;
    ctx.beginPath(); ctx.arc(bx,by,6,0,7); ctx.fillStyle='#fff'; ctx.fill(); ctx.strokeStyle='#000'; ctx.lineWidth=1.5; ctx.stroke(); }

  // overlay
  const mm=Math.floor(at/60), ss=Math.floor(at%60);
  ctx.fillStyle='#fff'; ctx.font='bold 16px sans-serif'; ctx.fillText(g.label+'  \\u25b6 LIVE', 16, 26);
  ctx.fillStyle='#bcd'; ctx.font='13px sans-serif'; ctx.fillText(mm+':'+(ss<10?'0':'')+ss, 16, 46);
  ctx.fillStyle=HOME; ctx.fillText('\\u25cf '+g.home, 16, H-44);
  ctx.fillStyle=AWAY; ctx.fillText('\\u25cf '+g.away, 26+ctx.measureText('\\u25cf '+g.home).width+18, H-44);

  // switch banner (brief, after a cut) — wraps long Granite narration
  if (at - switchT < 4.0 && reason){
    ctx.font='bold 15px sans-serif';
    const words=reason.split(' '); let lines=[], ln='';
    for(const w of words){ if(ctx.measureText(ln+' '+w).width>W-32){lines.push(ln);ln=w;} else ln=(ln?ln+' '+w:w);} if(ln)lines.push(ln);
    lines=lines.slice(0,2);
    ctx.fillStyle='rgba(255,59,59,0.88)'; ctx.fillRect(0,58,W,14+lines.length*20);
    ctx.fillStyle='#fff';
    lines.forEach((l,li)=>ctx.fillText((li?'   ':'\\u25b6 ')+l, 16, 78+li*20));
  }

  // play-by-play caption (lower third)
  const cap = caption(g, at);
  if(cap){ ctx.fillStyle='rgba(0,0,0,0.6)'; ctx.fillRect(0,H-30,W,30);
    ctx.fillStyle='#fff'; ctx.font='14px sans-serif'; ctx.fillText(cap, 16, H-10); }
  requestAnimationFrame(draw);
}
if(D.games[0].frames.length) requestAnimationFrame(draw); else pitch();
</script>
"""


_AUDIO_TEMPLATE = """
<div style="font-family:sans-serif">
<audio id="cm" autoplay playsinline>
  <source src="data:audio/mp3;base64,__B64__" type="audio/mpeg">
</audio>
<div id="ov" onclick="go()" style="display:none;cursor:pointer;background:#ff3b3b;
  color:#fff;padding:8px 12px;border-radius:6px;font-weight:bold;font-size:14px">
  \\U0001f50a Tap to enable commentary
</div>
<div id="ok" style="display:none;color:#8fbf8f;font-size:13px">\\U0001f50a Commentary on</div>
<script>
const a=document.getElementById('cm'), ov=document.getElementById('ov'), ok=document.getElementById('ok');
function go(){ a.muted=false; a.play().then(()=>{ov.style.display='none';ok.style.display='block';})
  .catch(()=>{ov.style.display='block';}); }
a.addEventListener('ended',()=>{ok.style.display='none';});
go();
</script>
</div>
"""


def build_audio_player(mp3_bytes: bytes) -> str:
    """HTML audio player that autoplays where allowed, with a one-tap fallback
    overlay for browsers that block autoplay (Safari)."""
    import base64
    b64 = base64.b64encode(mp3_bytes).decode("ascii")
    return _AUDIO_TEMPLATE.replace("__B64__", b64)


def build_broadcast(bdata, speed=1.4, home_color="#4da6ff", away_color="#ff8c42"):
    """Canvas that plays a multi-match tracking broadcast (from
    metrica.build_broadcast): both games, switching client-side per the
    schedule, with play-by-play captions. Self-contained — no Streamlit
    reruns needed during playback."""
    import json
    games = [{
        "label": gd["label"],
        "home": gd.get("home", "Home"), "away": gd.get("away", "Away"),
        "narration": gd.get("narration", ""), "audio": gd.get("audio"),
        "captions": gd["captions"],
        "frames": [{"t": fr.t, "b": list(fr.ball) if fr.ball else None,
                    "h": [list(p) for p in fr.home], "a": [list(p) for p in fr.away]}
                   for fr in gd["frames"]],
    } for gd in bdata["games"]]
    data = {"games": games, "schedule": bdata["schedule"], "speed": speed,
            "home_color": home_color, "away_color": away_color}
    return _BROADCAST_TEMPLATE.replace("__DATA__", json.dumps(data))


def build_tracking_feed(frames, home="Home", away="Away", label="Tracking feed",
                        speed=1.0, caption="", home_color="#4da6ff",
                        away_color="#ff8c42"):
    """Canvas that plays real 25fps tracking frames (all 22 players + ball).

    frames: list of core.metrica.Frame.
    """
    import json
    F = [{"t": fr.t, "b": list(fr.ball) if fr.ball else None,
          "h": [list(p) for p in fr.home], "a": [list(p) for p in fr.away]}
         for fr in frames]
    data = {"frames": F, "home": home, "away": away, "label": label,
            "speed": speed, "caption": caption,
            "home_color": home_color, "away_color": away_color}
    return _TRACK_TEMPLATE.replace("__DATA__", json.dumps(data))


def build_feed(events_window, home_team, away_team, danger, start_t, speed,
               label, score, is_fav, home_color="#4da6ff", away_color="#ff8c42"):
    """Build the self-contained canvas HTML for one match.

    events_window: list of (match_seconds, x, y, team_name, is_shot, is_goal)
    sorted by time, covering from start_t forward.
    """
    ev = [[round(t, 1), round(x, 1), round(y, 1),
           0 if team == home_team else 1, int(is_shot), int(is_goal)]
          for (t, x, y, team, is_shot, is_goal) in events_window]
    data = {
        "events": ev, "home": home_team, "away": away_team,
        "home_color": home_color, "away_color": away_color,
        "danger": round(danger, 3), "start_t": round(start_t, 1),
        "speed": speed, "label": label, "score": score, "is_fav": bool(is_fav),
    }
    return _TEMPLATE.replace("__DATA__", json.dumps(data))
