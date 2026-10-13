#!/usr/bin/env python3
"""Build a static availability calendar from an Airbnb iCal feed.
Reads AIRBNB_ICS_URL (or ICS_FILE for local testing). Never prints the URL or event summaries."""
import os, sys, calendar, datetime as dt, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Santo_Domingo")
MONTHS = 3

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
*{box-sizing:border-box}body{margin:0;background:#F3F6F6;color:#112733;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{display:flex;gap:16px;overflow-x:auto;scroll-snap-type:x mandatory;padding:12px}
.month{flex:0 0 min(320px,88vw);scroll-snap-align:start;background:#fff;border-radius:10px;padding:12px}
h2{color:#0F4949;font-size:1.05rem;margin:0 0 8px;text-align:center}
.grid{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center}
.dow{font-size:.75rem;color:#0F4949;font-weight:600}
.day{padding:7px 0;border-radius:6px;font-size:.9rem}
.open{border:1px solid #45B9BA}.booked{background:#E1E4E5;color:#9AA1A4;text-decoration:line-through}.past{color:#C3C8CA}
.legend,.note{font-size:.8rem;text-align:center;margin:4px 12px}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle;margin:0 4px 0 12px}
</style></head><body>
<div class="legend"><span class="sw" style="border:1px solid #45B9BA"></span>Available<span class="sw" style="background:#E1E4E5"></span>Booked</div>
<div class="wrap">%s</div>
<p class="note">Synced from Airbnb. Send your dates through the contact form to book.<br><small>Updated %s</small></p>
</body></html>"""

if __name__ == "__main__":
    now = dt.datetime.now(TZ)
    booked = parse(load_ics())
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(TEMPLATE % (render(booked, now.date()), now.strftime("%b %d, %Y %I:%M %p AST")))
    print(f"Built public/index.html ({len(booked)} booked nights)")
