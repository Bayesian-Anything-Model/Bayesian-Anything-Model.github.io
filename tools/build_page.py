"""Build assets + HTML fragments for the BAM project page from the Overleaf sources."""
import io, json, os, re, sys
import pymupdf
from PIL import Image

PAPER = "/users/aspagnol/Overleaf/BAM"
POSTER = "/users/aspagnol/Overleaf/BAM-poster"
SITE = "/users/aspagnol/bayesian-anything-model.github.io"
IMG = os.path.join(SITE, "static/images")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.template.html")

os.makedirs(IMG, exist_ok=True)


def save_pil(im, out_noext, small_png=True):
    """WebP for photos, PNG for tiny images (they are upscaled with nearest neighbour)."""
    im = im.convert("RGB")
    if small_png and max(im.size) <= 256:
        path = out_noext + ".png"
        im.save(path, optimize=True)
    else:
        path = out_noext + ".webp"
        im.save(path, quality=85, method=6)
    return path


def extract_single(pdf, out_noext):
    """Save the (single) raster image embedded in a figure PDF at native resolution."""
    doc = pymupdf.open(pdf)
    infos = doc[0].get_image_info(xrefs=True)
    if len(infos) == 1:
        raw = doc.extract_image(infos[0]["xref"])
        im = Image.open(io.BytesIO(raw["image"]))
        return save_pil(im, out_noext), im.size
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1.25, 1.25))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return save_pil(im, out_noext, small_png=False), im.size


def rel(p):
    return os.path.relpath(p, SITE)


# ---------------------------------------------------------------- Figure 1 tiles
TEASER_TILES = [  # (obs xref, sample xref, slug, dataset, task, layout class)
    (5, 9, "div2k-sr", "DIV2K", r"SR ×4", "t-big"),
    (18, 25, "afhq-deb", "AFHQ", "Gaussian deblurring", "t-afhq"),
    (33, 38, "ffhq-jpeg", "FFHQ", "JPEG (Q = 10)", "t-jpeg"),
    (45, 49, "ffhq-inp", "FFHQ", "Inpainting", "t-ffhq"),
    (57, 62, "kohler", "Köhler", "Blind motion deblurring", "t-kohler"),
    (69, 73, "lsun-inp", "LSUN", "Inpainting", "t-lsun1"),
    (80, 84, "lsun-sr", "LSUN", r"SR ×4", "t-lsun2"),
]


def build_teaser():
    out = os.path.join(IMG, "teaser")
    os.makedirs(out, exist_ok=True)
    doc = pymupdf.open(os.path.join(PAPER, "Figures/paper/teaser.pdf"))
    html = []
    for ox, sx, slug, ds, task, cls in TEASER_TILES:
        paths = []
        for xref, kind in ((ox, "obs"), (sx, "bam")):
            raw = doc.extract_image(xref)
            im = Image.open(io.BytesIO(raw["image"]))
            base = os.path.join(out, f"{slug}-{kind}")
            paths.append(save_pil(im, base))
        html.append(f'''      <div class="teaser-tile {cls}">
        <img-comparison-slider value="50">
          <img slot="first" src="{rel(paths[0])}" alt="{ds} {task}: observation" loading="lazy">
          <img slot="second" src="{rel(paths[1])}" alt="{ds} {task}: BAM posterior sample" loading="lazy">
        </img-comparison-slider>
        <span class="tile-tag tag-left">Observation</span><span class="tile-tag tag-right">BAM</span>
        <span class="tile-label">{ds} | {task}</span>
      </div>''')
    return "\n".join(html)


# ---------------------------------------------------------------- vector figures
def build_vectors():
    for src, name in ((os.path.join(POSTER, "flow-map.pdf"), "flow-map"),
                      (os.path.join(PAPER, "Figures/flops_lpips_bubbles.pdf"), "pareto")):
        page = pymupdf.open(src)[0]
        open(os.path.join(IMG, name + ".svg"), "w").write(page.get_svg_image(text_as_path=True))
        page.get_pixmap(dpi=250).save(os.path.join(IMG, name + ".png"))
    # social-media banner (1200x600) from the teaser collage
    page = pymupdf.open(os.path.join(PAPER, "Figures/paper/teaser.pdf"))[0]
    pix = page.get_pixmap(matrix=pymupdf.Matrix(1200 / page.rect.width, 600 / page.rect.height))
    Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(os.path.join(IMG, "banner.jpg"), quality=88)


def build_ct():
    out = os.path.join(IMG, "ct")
    os.makedirs(out, exist_ok=True)
    names = ["gt_panel", "fbp_panel", "bam_sample_panel", "bam_mean_panel",
             "section4_std_zoom", "section4_residual_zoom"]
    labels = ["Ground truth", "Filtered backprojection", "BAM sample", "BAM mean",
              "4×4 std. (N = 64)", "4×4 residual"]
    cells = []
    for n, lab in zip(names, labels):
        page = pymupdf.open(os.path.join(PAPER, f"Figures/CT/{n}.pdf"))[0]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0))
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        p = save_pil(im, os.path.join(out, n), small_png=False)
        cells.append(f'<figure class="ct-cell"><figcaption>{lab}</figcaption>'
                     f'<img src="{rel(p)}" alt="CT: {lab}" loading="lazy"></figure>')
    return "\n        ".join(cells)


# ---------------------------------------------------------------- LaTeX helpers
def tex_inline(s):
    s = s.replace(r"\BAMFT", "BAM<sup>★</sup>").replace(r"\RAMFT", "RAM<sup>★</sup>")
    s = s.replace("I$^2$SB", "I<sup>2</sup>SB").replace(r"K\"ohler", "Köhler")
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"\\textbf\{([^{}]*)\}", r"<b>\1</b>", s)
    s = re.sub(r"\\underline\{([^{}]*)\}", r"<u>\1</u>", s)
    s = s.replace("$\\uparrow$", "↑").replace("$\\downarrow$", "↓")
    s = s.replace("\\uparrow", "↑").replace("\\downarrow", "↓")
    return s.strip()


def brace_arg(s, i):
    """Return (content, end) of the balanced {...} starting at s[i]=='{'."""
    assert s[i] == "{", s[i:i + 20]
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    raise ValueError


def multicol_text(cell):
    i = cell.index(r"\multicolumn") + len(r"\multicolumn")
    for _ in range(2):  # skip {ncols}{colspec}
        _, i = brace_arg(cell, i)
    content, _ = brace_arg(cell, i)
    return content


# ---------------------------------------------------------------- tables
def parse_table(tex, label):
    i = tex.index(r"\label{" + label + "}")
    start = tex.index(r"\begin{tabularx}", i)
    end = tex.index(r"\end{tabularx}", start)
    body = tex[start:end]
    cap_i = tex.rfind(r"\caption{", 0, i)
    caption, _ = brace_arg(tex, cap_i + len(r"\caption"))
    lines = [l.strip() for l in body.split("\n")]
    groups, metrics, sections = [], [], []
    for l in lines:
        if l.startswith("Method &"):
            groups = [tex_inline(multicol_text(c)) for c in l.split("&") if "multicolumn" in c]
        elif l.startswith("& &"):
            metrics = [tex_inline(c.replace("\\\\", "")) for c in l.split("&")[2:]]
        elif l.startswith(r"\multicolumn"):
            sections.append({"title": tex_inline(multicol_text(l)), "rows": []})
        elif "&" in l and sections:
            bam = l.startswith(r"\rowcolor")
            l = re.sub(r"^\\rowcolor\{[^}]*\}\s*", "", l)
            l = re.sub(r"\\\\(\[[^\]]*\])?\s*$", "", l)
            cells = [tex_inline(c) for c in l.split("&")]
            sections[-1]["rows"].append((bam, cells))
    return caption, groups, metrics, sections


def table_html(caption, groups, metrics, sections, tid):
    per = len(metrics) // len(groups)
    h = [f'<div class="table-container"><table class="table results-table is-narrow is-hoverable" id="{tid}">',
         "<thead><tr><th rowspan=\"2\">Method</th><th rowspan=\"2\" class=\"num\">NFEs</th>"]
    h += [f'<th colspan="{per}" class="grp">{g}</th>' for g in groups]
    h.append("</tr><tr>")
    h += [f'<th class="num{" grp-start" if k % per == 0 else ""}">{m}</th>' for k, m in enumerate(metrics)]
    h.append("</tr></thead>")
    ncol = 2 + len(metrics)
    for sec in sections:
        h.append(f'<tbody><tr class="sec"><td colspan="{ncol}">{sec["title"]}</td></tr>')
        for bam, cells in sec["rows"]:
            tds = [f"<td>{cells[0]}</td>", f'<td class="num">{cells[1]}</td>']
            tds += [f'<td class="num{" grp-start" if k % per == 0 else ""}">{c}</td>'
                    for k, c in enumerate(cells[2:])]
            h.append(('<tr class="bam-row">' if bam else "<tr>") + "".join(tds) + "</tr>")
        h.append("</tbody>")
    h.append("</table></div>")
    return "\n".join(h)


def caption_html(cap):
    cap = re.sub(r"\\textbf\{([^{}]*)\}", r"<b>\1</b>", cap.replace("$\\sigma_y=0.05$", "σ<sub>y</sub> = 0.05"))
    cap = tex_inline(cap).replace("thre e", "three").replace("--", "–")
    return cap


def build_tables():
    exp = open(os.path.join(PAPER, "Sections/experiments.tex")).read()
    app = open(os.path.join(PAPER, "Sections/appendix_additional_results.tex")).read()
    main = table_html(*parse_table(exp, "tab:main-restoration"), "tab-main")
    tabs, panes = [], []
    for k, ds in enumerate(["DIV2K", "FFHQ", "AFHQ", "LSUN"]):
        cap, g, m, s = parse_table(app, f"tab:compact-{ds}")
        g = [x.replace("$\\sigma_y=0.025$", "σ<sub>y</sub> = 0.025").replace("$\\sigma_y=0.05$", "σ<sub>y</sub> = 0.05") for x in g]
        nimg = re.search(r"with (\d+) (?:test )?images", cap).group(1)
        tabs.append(f'<li class="{"is-active" if k == 0 else ""}"><a data-tab="full-{ds}">{ds}</a></li>')
        panes.append(f'<div class="tab-pane{" is-active" if k == 0 else ""}" id="full-{ds}">'
                     f'<p class="table-note">{ds}: {nimg} test images. BAM and BAM<sup>★</sup> use three steps.</p>'
                     + table_html(cap, g, m, s, f"tab-{ds}") + "</div>")
    full = ('<div class="tabs is-centered is-toggle is-small" data-tabs="full-tables"><ul>' + "".join(tabs)
            + '</ul></div>\n<div data-panes="full-tables">' + "\n".join(panes) + "</div>")
    return main, full


# ---------------------------------------------------------------- qualitative figures
def parse_figure(tex, label):
    i = tex.index(r"\label{" + label + "}")
    start = tex.rfind(r"\begin{tabular}", 0, i)
    end = tex.index(r"\end{tabular}", start)
    body = tex[start:end]
    header = next(l for l in body.split("\n") if l.strip().startswith(r"\textbf{Obs"))
    methods = [tex_inline(c.replace("\\\\", "")).replace("<b>", "").replace("</b>", "") for c in header.split("&")]
    rows = []
    for l in body.split("\n"):
        l = l.strip()
        if l.startswith(r"\multicolumn"):
            rows.append({"title": multicol_text(l), "cells": []})
        elif l.startswith(r"\BAMPaper"):
            for c in l.split("&"):
                c = c.strip()
                m = re.match(r"\\BAMPaperZoom\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}", c)
                rows[-1]["cells"].append((m.group(1), float(m.group(2)), float(m.group(3))) if m else None)
    return methods, rows


def title_html(t):
    t = t.replace(r"$\sigma_y=0.05$", "σ<sub>y</sub> = 0.05").replace(r"$\sigma_y = 0.05$", "σ<sub>y</sub> = 0.05")
    t = t.replace(r"pre-compression $\sigma_\text{JPEG}=0.01$", "pre-compression σ<sub>JPEG</sub> = 0.01")
    t = t.replace(r"$Q=10$", "Q = 10").replace(r"$\times4$", "×4")
    return tex_inline(t)


def build_figures():
    exp = open(os.path.join(PAPER, "Sections/experiments.tex")).read()
    specs = [("DIV2K", "fig:main-DIV2K"), ("FFHQ", "fig:main-FFHQ"), ("AFHQ", "fig:main-AFHQ")]
    tabs, panes, data = [], [], {}
    for k, (ds, label) in enumerate(specs):
        methods, rows = parse_figure(exp, label)
        out = os.path.join(IMG, "results", ds.lower())
        os.makedirs(out, exist_ok=True)
        ncol = len(methods)
        g = [f'<div class="qual-grid" style="--ncol:{ncol}">']
        g += [f'<div class="qual-head">{m}</div>' for m in methods]
        for r, row in enumerate(rows):
            g.append(f'<div class="qual-row-title">{title_html(row["title"])}</div>')
            ex_id = f"{ds}-{r}"
            data[ex_id] = {"title": title_html(row["title"]), "items": []}
            for c, (meth, cell) in enumerate(zip(methods, row["cells"])):
                if cell is None:
                    g.append('<div class="qual-cell missing"><span>–</span></div>')
                    continue
                path, x0, y0 = cell
                p, size = extract_single(os.path.join(PAPER, path), os.path.join(out, f"r{r}-c{c}"))
                top = 1 - y0 - 0.125
                data[ex_id]["items"].append({"name": meth, "src": rel(p)})
                g.append(
                    f'<div class="qual-cell" data-ex="{ex_id}" data-idx="{len(data[ex_id]["items"]) - 1}" '
                    f'style="--x:{x0};--y:{top:.3f}" title="Click to compare">'
                    f'<div class="qual-img"><img src="{rel(p)}" alt="{ds}: {meth}" loading="lazy"><i class="zoom-box"></i></div>'
                    f'<div class="qual-zoom"><img src="{rel(p)}" alt="" loading="lazy"></div></div>')
        g.append("</div>")
        tabs.append(f'<li class="{"is-active" if k == 0 else ""}"><a data-tab="qual-{ds}">{ds}</a></li>')
        panes.append(f'<div class="tab-pane{" is-active" if k == 0 else ""}" id="qual-{ds}"><div class="qual-scroll">'
                     + "\n".join(g) + "</div></div>")
    html = ('<div class="tabs is-centered is-toggle is-small" data-tabs="qual"><ul>' + "".join(tabs)
            + '</ul></div>\n<div data-panes="qual">' + "\n".join(panes) + "</div>")
    return html, json.dumps(data, ensure_ascii=False)


if __name__ == "__main__":
    teaser = build_teaser()
    build_vectors()
    ct = build_ct()
    main_table, full_tables = build_tables()
    qual, qual_data = build_figures()
    page = open(TEMPLATE).read()
    for key, val in {"TEASER": teaser, "CT": ct, "MAIN_TABLE": main_table, "FULL_TABLES": full_tables,
                     "QUAL": qual, "QUAL_DATA": qual_data}.items():
        marker = "<!--@" + key + "@-->"
        assert marker in page, marker
        page = page.replace(marker, val)
    open(os.path.join(SITE, "index.html"), "w").write(page)
    print("ok")
