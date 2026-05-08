"""CSV and HTML export of flight results."""

from datetime import datetime
from pathlib import Path

import pandas as pd

from config import OUTPUT_CSV
from utils import get_logger

logger = get_logger("exporter")

OUTPUT_HTML = OUTPUT_CSV.replace(".csv", ".html")


# ------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------

def export_csv(df: pd.DataFrame, path: str = OUTPUT_CSV) -> None:
    if df.empty:
        logger.warning("DataFrame is empty – CSV not written.")
        return
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info("CSV saved: %s  (%d rows)", path, len(df))


# ------------------------------------------------------------------
# HTML
# ------------------------------------------------------------------

def export_html(df: pd.DataFrame, path: str = OUTPUT_HTML) -> None:
    if df.empty:
        logger.warning("DataFrame is empty – HTML not written.")
        return

    df_sorted = df.sort_values("preis_eur", ascending=True).reset_index(drop=True)
    rows_html = "\n".join(_render_row(i, row) for i, row in df_sorted.iterrows())

    stats = _build_stats(df_sorted)
    generated = datetime.now().strftime("%d.%m.%Y %H:%M Uhr")

    html = _HTML_TEMPLATE.format(
        generated=generated,
        total=stats["total"],
        cheapest=stats["cheapest"],
        direct_count=stats["direct_count"],
        airports=stats["airports"],
        rows=rows_html,
    )

    Path(path).write_text(html, encoding="utf-8")
    logger.info("HTML saved: %s  (%d rows)", path, len(df_sorted))


# ------------------------------------------------------------------
# Row renderer
# ------------------------------------------------------------------

def _render_row(rank: int, row: pd.Series) -> str:
    direct = row["direktflug"] == "ja"
    stops = int(row["zwischenstopps"])
    badge_cls = "badge-direct" if direct else ("badge-one" if stops == 1 else "badge-multi")
    badge_txt = "Direktflug" if direct else f"{stops} Stopp{'s' if stops != 1 else ''}"
    price_cls = "price-low" if row["preis_eur"] < 200 else ("price-mid" if row["preis_eur"] < 350 else "price-high")

    nights = ""
    try:
        d1 = datetime.strptime(row["abflugdatum"], "%Y-%m-%d")
        d2 = datetime.strptime(row["rueckflugdatum"], "%Y-%m-%d")
        nights = f"{(d2 - d1).days} Nächte"
    except Exception:
        pass

    abflugzeit  = row["abflugzeit"]  or "—"
    rueckzeit   = row["rueckflugzeit"] or "—"
    url         = row["buchungs_url"] or "#"
    url_short   = url if len(url) <= 60 else url[:57] + "…"

    return f"""
    <li class="offer-item">
      <details>
        <summary>
          <span class="rank">#{rank + 1}</span>
          <span class="{price_cls} price-tag">{row['preis_eur']:.2f}&nbsp;€</span>
          <span class="route">{row['abflughafen']} &rarr; PMI</span>
          <span class="dates">{_fmt_date(row['abflugdatum'])} &rarr; {_fmt_date(row['rueckflugdatum'])}</span>
          <span class="airline-name">{row['airline']}</span>
          <span class="badge {badge_cls}">{badge_txt}</span>
          <span class="source-tag">{row['quelle']}</span>
        </summary>
        <div class="detail-grid">
          <div class="detail-col">
            <h4>Hinflug</h4>
            <p><strong>Abflug:</strong> {row['abflughafen']} am {_fmt_date(row['abflugdatum'])} um {abflugzeit}</p>
            <p><strong>Ziel:</strong> Palma de Mallorca (PMI)</p>
          </div>
          <div class="detail-col">
            <h4>Rückflug</h4>
            <p><strong>Abflug:</strong> PMI am {_fmt_date(row['rueckflugdatum'])} um {rueckzeit}</p>
            <p><strong>Ziel:</strong> {row['abflughafen']}</p>
          </div>
          <div class="detail-col">
            <h4>Details</h4>
            <p><strong>Airline:</strong> {row['airline']}</p>
            <p><strong>Aufenthalt:</strong> {nights}</p>
            <p><strong>Stopps:</strong> {badge_txt}</p>
            <p><strong>Quelle:</strong> {row['quelle']}</p>
            <p><strong>Abgerufen:</strong> {row.get('abgerufen_am', '—')}</p>
          </div>
          <div class="detail-col detail-booking">
            <h4>Buchung</h4>
            <a class="book-btn" href="{url}" target="_blank" rel="noopener">
              Jetzt buchen &rarr;
            </a>
            <p class="url-small" title="{url}">{url_short}</p>
          </div>
        </div>
      </details>
    </li>"""


# ------------------------------------------------------------------
# Stats
# ------------------------------------------------------------------

def _build_stats(df: pd.DataFrame) -> dict:
    airports = ", ".join(sorted(df["abflughafen"].unique()))
    cheapest = df["preis_eur"].min()
    direct_count = int((df["direktflug"] == "ja").sum())
    return {
        "total": len(df),
        "cheapest": f"{cheapest:.2f}",
        "direct_count": direct_count,
        "airports": airports,
    }


def _fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return d


# ------------------------------------------------------------------
# HTML template
# ------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flugpreisvergleich – PAD / HAJ / DUS nach PMI</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f0f4f8;
    color: #1a202c;
    min-height: 100vh;
  }}

  header {{
    background: linear-gradient(135deg, #1a56db 0%, #0e3fa8 100%);
    color: #fff;
    padding: 2rem 1.5rem 1.5rem;
  }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 0.3rem; }}
  header p  {{ opacity: .8; font-size: .9rem; }}

  .stats-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    background: #fff;
    border-bottom: 1px solid #e2e8f0;
    padding: .75rem 1.5rem;
    font-size: .85rem;
    color: #4a5568;
  }}
  .stat {{ display: flex; align-items: center; gap: .4rem; }}
  .stat strong {{ color: #1a202c; }}

  .controls {{
    display: flex;
    flex-wrap: wrap;
    gap: .5rem;
    padding: 1rem 1.5rem;
    background: #fff;
    border-bottom: 1px solid #e2e8f0;
    align-items: center;
  }}
  .controls label {{ font-size: .85rem; color: #4a5568; margin-right: .25rem; }}
  .filter-btn {{
    padding: .35rem .85rem;
    border: 1px solid #cbd5e0;
    border-radius: 9999px;
    background: #fff;
    font-size: .8rem;
    cursor: pointer;
    transition: all .15s;
  }}
  .filter-btn:hover, .filter-btn.active {{
    background: #1a56db;
    color: #fff;
    border-color: #1a56db;
  }}
  .search-input {{
    padding: .35rem .75rem;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    font-size: .85rem;
    margin-left: auto;
    width: 200px;
  }}

  main {{ padding: 1.5rem; max-width: 1200px; margin: 0 auto; }}

  .offer-list {{ list-style: none; display: flex; flex-direction: column; gap: .6rem; }}

  .offer-item details {{
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
    transition: box-shadow .15s;
  }}
  .offer-item details:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,.08); }}
  .offer-item details[open] {{ box-shadow: 0 4px 16px rgba(26,86,219,.12); border-color: #93c5fd; }}

  summary {{
    display: flex;
    align-items: center;
    gap: .75rem;
    flex-wrap: wrap;
    padding: .85rem 1.1rem;
    cursor: pointer;
    user-select: none;
    list-style: none;
  }}
  summary::-webkit-details-marker {{ display: none; }}
  summary::after {{
    content: "▸";
    margin-left: auto;
    color: #a0aec0;
    font-size: .85rem;
    flex-shrink: 0;
  }}
  details[open] summary::after {{ content: "▾"; }}

  .rank {{ font-size: .75rem; color: #a0aec0; min-width: 2rem; }}

  .price-tag {{ font-size: 1.2rem; font-weight: 700; min-width: 6rem; }}
  .price-low  {{ color: #059669; }}
  .price-mid  {{ color: #d97706; }}
  .price-high {{ color: #dc2626; }}

  .route {{ font-weight: 600; font-size: .95rem; min-width: 7rem; }}
  .dates {{ font-size: .85rem; color: #4a5568; min-width: 14rem; }}
  .airline-name {{ font-size: .85rem; color: #2d3748; min-width: 7rem; }}
  .source-tag {{
    font-size: .72rem;
    background: #edf2ff;
    color: #3b5bdb;
    padding: .2rem .55rem;
    border-radius: 9999px;
    white-space: nowrap;
  }}

  .badge {{
    font-size: .72rem;
    padding: .2rem .55rem;
    border-radius: 9999px;
    white-space: nowrap;
    font-weight: 600;
  }}
  .badge-direct {{ background: #dcfce7; color: #166534; }}
  .badge-one    {{ background: #fef9c3; color: #854d0e; }}
  .badge-multi  {{ background: #fee2e2; color: #991b1b; }}

  .detail-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.25rem;
    padding: 1.1rem 1.3rem 1.3rem;
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
  }}
  .detail-col h4 {{ font-size: .78rem; text-transform: uppercase; color: #718096;
                    letter-spacing: .05em; margin-bottom: .5rem; }}
  .detail-col p  {{ font-size: .85rem; color: #4a5568; margin-bottom: .25rem; line-height: 1.5; }}
  .detail-col p strong {{ color: #2d3748; }}

  .detail-booking {{ display: flex; flex-direction: column; gap: .6rem; }}
  .book-btn {{
    display: inline-block;
    background: #1a56db;
    color: #fff;
    font-weight: 600;
    font-size: .9rem;
    padding: .6rem 1.2rem;
    border-radius: 8px;
    text-decoration: none;
    text-align: center;
    transition: background .15s;
    white-space: nowrap;
  }}
  .book-btn:hover {{ background: #1648c0; }}
  .url-small {{ font-size: .72rem; color: #a0aec0; word-break: break-all; }}

  .no-results {{
    text-align: center;
    color: #a0aec0;
    padding: 3rem;
    font-size: 1rem;
  }}

  footer {{
    text-align: center;
    padding: 2rem;
    font-size: .8rem;
    color: #a0aec0;
  }}
</style>
</head>
<body>

<header>
  <h1>✈ Flugpreisvergleich &ndash; PAD / HAJ / DUS &rarr; Palma de Mallorca (PMI)</h1>
  <p>Reisezeitraum: 18. Mai 2026 &ndash; 30. Juni 2026 &nbsp;|&nbsp; Aufenthalt: 7&ndash;10 Nächte &nbsp;|&nbsp; 1 Erwachsener</p>
</header>

<div class="stats-bar">
  <div class="stat">🔍 <strong>{total}</strong> Angebote gefunden</div>
  <div class="stat">💰 Günstigster Preis: <strong>{cheapest} €</strong></div>
  <div class="stat">✅ Direktflüge: <strong>{direct_count}</strong></div>
  <div class="stat">🛫 Abflughäfen: <strong>{airports}</strong></div>
  <div class="stat" style="margin-left:auto">Stand: {generated}</div>
</div>

<div class="controls">
  <label>Abflughafen:</label>
  <button class="filter-btn active" onclick="filterAirport(this,'ALL')">Alle</button>
  <button class="filter-btn" onclick="filterAirport(this,'PAD')">PAD</button>
  <button class="filter-btn" onclick="filterAirport(this,'HAJ')">HAJ</button>
  <button class="filter-btn" onclick="filterAirport(this,'DUS')">DUS</button>

  <label style="margin-left:.75rem">Flugtyp:</label>
  <button class="filter-btn active" onclick="filterDirect(this,'ALL')">Alle</button>
  <button class="filter-btn" onclick="filterDirect(this,'ja')">Nur Direktflüge</button>

  <input class="search-input" type="search" placeholder="Airline, Quelle …" oninput="filterSearch(this.value)">
</div>

<main>
  <ul class="offer-list" id="offerList">
{rows}
  </ul>
  <p class="no-results" id="noResults" style="display:none">Keine Angebote gefunden.</p>
</main>

<footer>Generiert am {generated} &nbsp;|&nbsp; Alle Preise in EUR inkl. Steuern und Gebühren (soweit von der Quelle angegeben)</footer>

<script>
  let activeAirport = 'ALL';
  let activeDirect  = 'ALL';
  let searchTerm    = '';

  function applyFilters() {{
    const items = document.querySelectorAll('.offer-item');
    let visible = 0;
    items.forEach(li => {{
      const summary = li.querySelector('summary').innerText;
      const matchAirport = activeAirport === 'ALL' || summary.includes(activeAirport);
      const matchDirect  = activeDirect  === 'ALL' ||
        (activeDirect === 'ja' ? li.querySelector('.badge-direct') : true);
      const matchSearch  = !searchTerm ||
        summary.toLowerCase().includes(searchTerm.toLowerCase());
      const show = matchAirport && matchDirect && matchSearch;
      li.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    document.getElementById('noResults').style.display = visible === 0 ? '' : 'none';
  }}

  function filterAirport(btn, value) {{
    document.querySelectorAll('.controls .filter-btn').forEach(b => {{
      if (['ALL','PAD','HAJ','DUS'].includes(b.innerText) || b.innerText === 'Alle')
        b.classList.remove('active');
    }});
    btn.classList.add('active');
    activeAirport = value;
    applyFilters();
  }}

  function filterDirect(btn, value) {{
    btn.closest('.controls').querySelectorAll('.filter-btn').forEach(b => {{
      if (b.innerText === 'Alle' || b.innerText === 'Nur Direktflüge')
        b.classList.remove('active');
    }});
    btn.classList.add('active');
    activeDirect = value;
    applyFilters();
  }}

  function filterSearch(value) {{
    searchTerm = value;
    applyFilters();
  }}
</script>
</body>
</html>"""
