#!/usr/bin/env python3
"""物件一覧Web管理画面。"""
import sqlite3
import os
from flask import Flask, request, render_template_string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "properties.db")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>不動産チェッカー</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Hiragino Sans', 'Meiryo', sans-serif; background: #f5f5f5; color: #333; }
.header { background: #2c3e50; color: white; padding: 16px 24px; }
.header h1 { font-size: 20px; }
.header .stats { font-size: 14px; margin-top: 4px; opacity: 0.8; }
.filters { background: white; padding: 12px 24px; border-bottom: 1px solid #ddd; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.filters select, .filters input { padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
.filters button { padding: 8px 16px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
.filters button:hover { background: #2980b9; }
.container { max-width: 1200px; margin: 0 auto; padding: 16px; }
.card { background: white; border-radius: 8px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
.card.new { border-left: 4px solid #e74c3c; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.card-title { font-size: 16px; font-weight: bold; }
.card-title a { color: #2c3e50; text-decoration: none; }
.card-title a:hover { color: #3498db; }
.card-site { font-size: 12px; padding: 2px 8px; border-radius: 12px; color: white; white-space: nowrap; }
.site-kenbiya { background: #2ecc71; }
.site-rakumachi { background: #3498db; }
.site-suumo { background: #e74c3c; }
.site-athome { background: #f39c12; }
.site-fudosan { background: #9b59b6; }
.site-custom { background: #95a5a6; }
.card-details { display: flex; gap: 20px; margin-top: 8px; font-size: 14px; color: #666; flex-wrap: wrap; }
.card-details span { display: flex; align-items: center; gap: 4px; }
.card-date { font-size: 12px; color: #999; margin-top: 8px; }
.price { color: #e74c3c; font-weight: bold; font-size: 18px; }
.yield-rate { color: #27ae60; font-weight: bold; }
.pagination { display: flex; justify-content: center; gap: 8px; margin-top: 16px; }
.pagination a, .pagination span { padding: 8px 14px; border-radius: 4px; text-decoration: none; font-size: 14px; }
.pagination a { background: white; color: #333; border: 1px solid #ddd; }
.pagination a:hover { background: #3498db; color: white; }
.pagination span.current { background: #3498db; color: white; }
.empty { text-align: center; padding: 60px; color: #999; font-size: 18px; }
</style>
</head>
<body>
<div class="header">
  <h1>不動産チェッカー - 物件一覧</h1>
  <div class="stats">全 {{ total }} 件 ｜ 最終巡回: {{ last_check }}</div>
</div>
<form class="filters" method="get">
  <select name="site">
    <option value="">全サイト</option>
    {% for s in sites %}
    <option value="{{ s }}" {{ 'selected' if s == current_site }}>{{ s }}</option>
    {% endfor %}
  </select>
  <select name="sort">
    <option value="newest" {{ 'selected' if sort == 'newest' }}>新着順</option>
    <option value="price_asc" {{ 'selected' if sort == 'price_asc' }}>価格が安い順</option>
    <option value="price_desc" {{ 'selected' if sort == 'price_desc' }}>価格が高い順</option>
  </select>
  <input type="text" name="q" value="{{ q }}" placeholder="キーワード検索...">
  <button type="submit">検索</button>
</form>
<div class="container">
{% if properties %}
  {% for p in properties %}
  <div class="card {{ 'new' if p.is_new }}">
    <div class="card-header">
      <div>
        <div class="card-title"><a href="{{ p.url }}" target="_blank">{{ p.title }}</a></div>
        <div class="card-details">
          {% if p.price %}<span class="price">{{ p.price }}</span>{% endif %}
          {% if p.yield_rate %}<span class="yield-rate">{{ p.yield_rate }}</span>{% endif %}
          {% if p.address %}<span>📍 {{ p.address }}</span>{% endif %}
        </div>
        <div class="card-date">{{ p.first_seen_fmt }} に検知 ｜ {{ p.site }}</div>
      </div>
      <span class="card-site {{ p.site_class }}">{{ p.site }}</span>
    </div>
  </div>
  {% endfor %}
  <div class="pagination">
    {% if page > 1 %}
    <a href="?page={{ page - 1 }}&site={{ current_site }}&sort={{ sort }}&q={{ q }}">&laquo; 前へ</a>
    {% endif %}
    <span class="current">{{ page }} / {{ total_pages }}</span>
    {% if page < total_pages %}
    <a href="?page={{ page + 1 }}&site={{ current_site }}&sort={{ sort }}&q={{ q }}">次へ &raquo;</a>
    {% endif %}
  </div>
{% else %}
  <div class="empty">物件が見つかりません</div>
{% endif %}
</div>
</body>
</html>
"""

SITE_CLASS_MAP = {
    "健美家": "site-kenbiya",
    "楽待": "site-rakumachi",
    "SUUMO": "site-suumo",
    "アットホーム": "site-athome",
    "不動産ジャパン": "site-fudosan",
}

PER_PAGE = 30


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    site = request.args.get("site", "")
    sort = request.args.get("sort", "newest")
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))

    conn = get_db()

    # サイト一覧
    sites = [r[0] for r in conn.execute("SELECT DISTINCT site FROM properties ORDER BY site").fetchall()]

    # フィルタ条件
    where = []
    params = []
    if site:
        where.append("site = ?")
        params.append(site)
    if q:
        where.append("(title LIKE ? OR address LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    # 合計件数
    total = conn.execute(f"SELECT COUNT(*) FROM properties {where_sql}", params).fetchone()[0]
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = max(1, min(page, total_pages))

    # ソート
    if sort == "price_asc":
        order = "CAST(REPLACE(REPLACE(REPLACE(price, '万円', ''), ',', ''), '　', '') AS REAL) ASC"
    elif sort == "price_desc":
        order = "CAST(REPLACE(REPLACE(REPLACE(price, '万円', ''), ',', ''), '　', '') AS REAL) DESC"
    else:
        order = "first_seen DESC"

    offset = (page - 1) * PER_PAGE
    rows = conn.execute(
        f"SELECT * FROM properties {where_sql} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [PER_PAGE, offset],
    ).fetchall()

    # 最終巡回時刻
    last_check_row = conn.execute("SELECT MAX(last_seen) FROM properties").fetchone()
    last_check = last_check_row[0][:16].replace("T", " ") if last_check_row and last_check_row[0] else "未取得"

    # 24時間以内の新着判定
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

    properties = []
    for r in rows:
        properties.append({
            "url": r["url"],
            "title": r["title"],
            "price": r["price"],
            "site": r["site"],
            "address": r["address"],
            "yield_rate": r["yield_rate"],
            "first_seen_fmt": r["first_seen"][:16].replace("T", " ") if r["first_seen"] else "",
            "site_class": SITE_CLASS_MAP.get(r["site"], "site-custom"),
            "is_new": r["first_seen"] > cutoff if r["first_seen"] else False,
        })

    conn.close()

    return render_template_string(
        HTML_TEMPLATE,
        properties=properties,
        total=total,
        sites=sites,
        current_site=site,
        sort=sort,
        q=q,
        page=page,
        total_pages=total_pages,
        last_check=last_check,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
