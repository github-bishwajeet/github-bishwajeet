# README.md from a template, so the numbers in every image's alt text stay current.
# Every image is a <picture> with a dark <source>. Pictures in PHONE also get phone sources.
# Source order matters: the browser takes the first one whose media matches, so dark+phone comes
# first, then phone, then dark, then the light desktop <img>.
from datetime import date
from html import escape

from board import board_label
from cards import app_fact, app_label, fmt, hero_label, site_label, whoami_label
from graphs import graph_titles, last_days, title_of, total_of


PHONE = ("hero", "github", "whoami")


def line_title(data, today):
    return title_of(total_of(last_days(data, today)), "in the last 30 days")


def picture(name, width, alt, phone=False, bust=""):
    """GitHub's camo CDN caches profile images by URL; bust changes the query so refreshes show."""
    a = f"assets/{name}"
    q = f"?v={bust}" if bust else ""
    srcs = []
    if phone:
        srcs.append(f'<source media="(prefers-color-scheme: dark) and (max-width: 600px)" srcset="{a}-phone-dark.svg{q}">')
        srcs.append(f'<source media="(max-width: 600px)" srcset="{a}-phone-light.svg{q}">')
    srcs.append(f'<source media="(prefers-color-scheme: dark)" srcset="{a}-dark.svg{q}">')
    attr = f'height="{width[1:]}"' if width.startswith("h") else f'width="{width}"'
    return f'<picture>{"".join(srcs)}<img src="{a}-light.svg{q}" {attr} alt="{escape(alt, quote=True)}"></picture>'


def link(url, inner):
    return f'<a href="{url}">{inner}</a>'


def link_items(P):
    """Ordered social/site links from profile.json (skip keys that are not link objects)."""
    L = P["links"]
    skip = {"source", "as_of"}
    items = []
    for key, val in L.items():
        if key in skip or not isinstance(val, dict) or "url" not in val:
            continue
        items.append(val)
    return items


def render(data, P):
    L = P["links"]
    # Include design stamp so same-day visual pushes still bust camo (date alone is not enough).
    bust = data["today"].replace("-", "") + "oss"
    out = [link(L["site"]["url"], picture("hero", "100%", hero_label(P, data), "hero" in PHONE, bust)), ""]
    badges = []
    for item in link_items(P):
        name = item.get("badge") or item["label"].lower().replace(".", "")
        alt = f"{item['label']} {item.get('handle', '')}".strip()
        badges.append(link(item["url"], picture(f"badge-{name}", "h44", alt, bust=bust)))
    out += ['<p align="center">', *badges, "</p>", ""]
    out += [picture("github", "100%", board_label(data), "github" in PHONE, bust), ""]
    for key, summary, total, title in graph_titles(data, date.fromisoformat(data["today"])):
        pic = picture(f"graph-{key}", "100%", title, True, bust)
        if summary is None:
            out += [pic, ""]
        else:
            unit = "contribution" if total == 1 else "contributions"
            out += [f"<details><summary>{summary}: {fmt(total)} {unit}</summary>", "", pic, "", "</details>", ""]
    out += [picture("line-30d", "100%", line_title(data, date.fromisoformat(data["today"])), True, bust), ""]
    out += [picture("whoami", "100%", whoami_label(data, P), "whoami" in PHONE, bust), ""]
    out += [picture("label-ship", "100%", "What I ship", True, bust), ""]
    apps = []
    for a in P["apps"]:
        alt = app_label(a, app_fact(a, data, P))
        apps.append(link(a["url"], picture(f"app-{a['id']}", "49%", alt, True, bust)))
    out += ['<p align="center">', *apps, "</p>", ""]
    more = " · ".join(link(m["url"], m["name"]) for m in P.get("more", []))
    if more:
        out += [f'<p align="center"><sub>more ships: {more}</sub></p>', ""]
    videos = (data.get("videos") or {}).get("videos") or []
    if videos:
        out += [picture("label-videos", "100%", "Latest videos", True, bust), ""]
        vids = [link(f"https://www.youtube.com/watch?v={v['id']}",
                     picture(f"video-{v['id']}", "32%", v["title"], True, bust))
                for v in videos]
        out += ['<p align="center">', *vids, "</p>", ""]
    footer = P.get("footer", {}).get("value") or "Drawn in a sticker-board design system · numbers redrawn every night by a GitHub Action"
    out += [f'<p align="center"><sub>{footer} · {link(L["site"]["url"], site_label(P))}</sub></p>', ""]
    return "\n".join(out)
