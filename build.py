#!/usr/bin/env python3
"""Build a static availability calendar from an Airbnb iCal feed.
Reads AIRBNB_ICS_URL (or ICS_FILE for local testing). Never prints the URL or event summaries."""
import os, sys, calendar, datetime as dt, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Santo_Domingo")
MONTHS = 12

def load_ics():
    f = os.environ.get("ICS_FILE")
    if f:
        return open(f, encoding="utf-8").read()
    url = os.environ.get("AIRBNB_ICS_URL")
    if not url:
        sys.exit("AIRBNB_ICS_URL not set")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 calendar-sync"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        sys.exit(f"Fetch failed ({type(e).__name__})")  # no URL in output

def parse_date(val):
    v = val.strip()
    if "T" in v:
        d = dt.datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
        if v.endswith("Z"):
            d = d.replace(tzinfo=dt.timezone.utc).astimezone(TZ)
        return d.date()
    return dt.datetime.strptime(v[:8], "%Y%m%d").date()

def parse(text):
    text = text.replace("\r\n", "\n").replace("\n ", "").replace("\n\t", "")
    booked, ev = set(), None
    for line in text.split("\n"):
        if line == "BEGIN:VEVENT": ev = {}
        elif line == "END:VEVENT":
            if ev and "s" in ev:
                s = ev["s"]; e = ev.get("e", s + dt.timedelta(days=1))
                while s < e:  # end date = checkout, stays available
                    booked.add(s); s += dt.timedelta(days=1)
            ev = None
        elif ev is not None and ":" in line:
            k, v = line.split(":", 1); k = k.split(";")[0]
            if k == "DTSTART": ev["s"] = parse_date(v)
            elif k == "DTEND": ev["e"] = parse_date(v)
    return booked

def render(booked, today):
    cal = calendar.Calendar(firstweekday=6)
    out = []
    y, m = today.year, today.month
    for _ in range(MONTHS):
        rows = ['<section class="month"><h2>%s %d</h2><div class="grid">' % (calendar.month_name[m], y)]
        rows += ['<div class="dow">%s</div>' % d for d in "SMTWTFS"]
        for d in cal.itermonthdates(y, m):
            if d.month != m: rows.append('<div></div>'); continue
            cls = "past" if d < today else ("booked" if d in booked else "open")
            label = "booked" if cls == "booked" else ("available" if cls == "open" else "past")
            rows.append(f'<div class="day {cls}" aria-label="{d.isoformat()} {label}">{d.day}</div>')
        rows.append("</div></section>")
        out.append("".join(rows))
        m += 1
        if m > 12: m, y = 1, y + 1
    return "\n".join(out)

TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Availability</title><style>
*{box-sizing:border-box}html,body{margin:0;background:#F3F6F6;color:#112733;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.bar{display:flex;align-items:center;justify-content:space-between;padding:8px 12px 2px}
.legend{font-size:.75rem;letter-spacing:.02em}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;vertical-align:-1px;margin:0 5px 0 12px}
.nav{display:flex;gap:8px}
.nav button{width:32px;height:32px;border-radius:50%;border:1px solid #0F4949;background:transparent;color:#0F4949;cursor:pointer;display:grid;place-items:center;transition:all .2s}
.nav button:hover:not(:disabled){background:#0F4949;color:#F3F6F6}
.nav button:disabled{opacity:.25;cursor:default}
.nav svg{width:14px;height:14px}
.wrap{display:flex;gap:14px;overflow-x:auto;scroll-snap-type:x mandatory;scroll-behavior:smooth;padding:8px 0;margin:0 12px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.wrap::-webkit-scrollbar{display:none}
.month{flex:0 0 calc((100% - 28px)/3);scroll-snap-align:start;background:#fff;border-radius:10px;padding:10px 10px 8px}
@media(max-width:820px){.month{flex-basis:calc((100% - 14px)/2)}}
@media(max-width:540px){.month{flex-basis:100%}}
h2{color:#0F4949;font-size:.95rem;font-weight:600;letter-spacing:.04em;margin:0 0 6px;text-align:center}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;text-align:center}
.dow{font-size:.68rem;color:#0F4949;font-weight:600}
.day{padding:3px 0;border-radius:5px;font-size:.78rem;line-height:1.25}
.open{border:1px solid #45B9BA}.booked{background:#E1E4E5;color:#9AA1A4;text-decoration:line-through;border:1px solid #E1E4E5}.past{color:#C3C8CA;border:1px solid transparent}
.note{font-size:.72rem;text-align:center;margin:2px 12px 6px}
</style></head><body>
<div class="bar"><div class="legend"><span class="sw" style="border:1px solid #45B9BA;margin-left:0"></span>Available<span class="sw" style="background:#E1E4E5"></span>Booked</div>
<div class="nav"><button id="prev" aria-label="Previous months"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M10 3 5 8l5 5"/></svg></button>
<button id="next" aria-label="Next months"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="m6 3 5 5-5 5"/></svg></button></div></div>
<div class="wrap" id="wrap">{{MONTHS}}</div>
<p class="note">Synced from Airbnb. Send your dates through the contact form to book. <span style="opacity:.6">Updated {{UPDATED}}</span></p>
<script>
var w=document.getElementById('wrap'),p=document.getElementById('prev'),n=document.getElementById('next');
function step(){var m=w.querySelector('.month');return m.offsetWidth+14}
function per(){return Math.max(1,Math.round(w.clientWidth/step()))}
function upd(){p.disabled=w.scrollLeft<5;n.disabled=w.scrollLeft+w.clientWidth>=w.scrollWidth-5}
p.onclick=function(){w.scrollBy({left:-step()*per()})};n.onclick=function(){w.scrollBy({left:step()*per()})};
w.addEventListener('scroll',upd);window.addEventListener('resize',upd);window.addEventListener('load',upd);upd();
var h=location.hash.match(/page=([0-9]+)/);if(h){w.style.scrollBehavior='auto';w.scrollLeft=step()*per()*(+h[1]);upd()}
</script>
</body></html>"""

if __name__ == "__main__":
    now = dt.datetime.now(TZ)
    booked = parse(load_ics())
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("{{MONTHS}}", render(booked, now.date())).replace("{{UPDATED}}", now.strftime("%b %d, %Y %I:%M %p AST")))
    print(f"Built public/index.html ({len(booked)} booked nights)")
