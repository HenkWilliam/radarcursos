import asyncio
import json
import os
import re
import sqlite3
import webbrowser
import urllib.request
import urllib.parse
from datetime import datetime
from urllib.parse import unquote, urlparse

from playwright.async_api import async_playwright


# ─── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "radar.log")
DB_FILE  = os.path.join(BASE_DIR, "cursos.db")
CFG_FILE = os.path.join(BASE_DIR, "config.json")

os.makedirs(LOG_DIR, exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────────
with open(CFG_FILE, "r", encoding="utf-8") as _f:
    CONFIG = json.load(_f)

INSTITUICOES_CONHECIDAS = CONFIG.get("instituicoes_conhecidas", [])

# ─── Consultas de busca ───────────────────────────────────────────────────────
CONSULTAS = [
    # Graduação / Tecnólogo
    '\"Análise e Desenvolvimento de Sistemas\" EAD gratuito edital',
    '\"Banco de Dados\" graduação EAD gratuito edital',
    '\"Ciência da Computação\" EAD gratuito edital',
    '\"Engenharia de Software\" EAD gratuito edital',
    '\"Sistemas de Informação\" EAD gratuito edital',
    '\"Sistemas para Internet\" EAD gratuito edital',
    '\"Ciência de Dados\" EAD gratuito edital',
    '\"Inteligência Artificial\" graduação EAD gratuito edital',
    '\"Segurança da Informação\" EAD gratuito edital',
    '\"Tecnologia da Informação\" EAD gratuito edital',
    '\"Redes de Computadores\" EAD gratuito edital',
    '\"Desenvolvimento Web\" graduação EAD gratuito edital',
    '\"Desenvolvimento Mobile\" graduação EAD gratuito edital',
    '\"Jogos Digitais\" graduação EAD gratuito edital',
    '\"Engenharia de Computação\" EAD gratuito edital',
    '\"Gestão de TI\" EAD gratuito edital',
    '\"Cloud Computing\" graduação EAD gratuito edital',
    '\"Internet das Coisas\" graduação EAD gratuito edital',
    '\"Cibersegurança\" graduação EAD gratuito edital',
    '\"UX Design\" graduação EAD gratuito edital',
    # Pós-graduação / MBA
    '\"MBA\" tecnologia gratuito edital',
    '\"pós-graduação\" tecnologia EAD gratuito edital',
    '\"especialização\" computação EAD gratuito edital',
    '\"especialização\" \"inteligência artificial\" gratuito edital',
    '\"especialização\" \"ciência de dados\" gratuito edital',
    '\"especialização\" \"segurança da informação\" gratuito edital',
    '\"especialização\" \"desenvolvimento de software\" gratuito edital',
    # Mestrado / Doutorado
    '\"mestrado\" computação gratuito edital',
    '\"mestrado\" \"inteligência artificial\" gratuito edital',
    '\"doutorado\" computação gratuito edital',
    # SISU / ENEM
    '\"SISU\" tecnologia \"ciência da computação\" edital',
    '\"SISU\" \"análise e desenvolvimento de sistemas\" edital',
    '\"vestibular\" tecnologia universidade federal 2026',
]


# ─── Log ─────────────────────────────────────────────────────────────────────
def limpar_log():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")


def log(mensagem: str):
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    texto = f"[{data}] {mensagem}"
    print(texto)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(texto + "\n")


# ─── Banco de dados ───────────────────────────────────────────────────────────
def iniciar_db():
    con = sqlite3.connect(DB_FILE)
    con.execute("""
        CREATE TABLE IF NOT EXISTS resultados (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            data_busca   TEXT,
            consulta     TEXT,
            titulo       TEXT,
            url          TEXT UNIQUE,
            descricao    TEXT,
            instituicao  TEXT,
            area         TEXT,
            nivel        TEXT,
            status_vaga  TEXT
        )
    """)
    # Migração: adiciona coluna status_vaga se não existir
    try:
        con.execute("ALTER TABLE resultados ADD COLUMN status_vaga TEXT")
    except sqlite3.OperationalError:
        pass  # Coluna já existe
    con.commit()
    return con


def salvar_resultado(con, consulta: str, resultado: dict):
    try:
        con.execute("""
            INSERT OR IGNORE INTO resultados
                (data_busca, consulta, titulo, url, descricao, instituicao, area, nivel, status_vaga)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            consulta,
            resultado["titulo"],
            resultado["url"],
            resultado["descricao"],
            resultado.get("instituicao", ""),
            resultado.get("area", ""),
            resultado.get("nivel", ""),
            resultado.get("status_vaga", ""),
        ))
        con.commit()
    except Exception as e:
        log(f"⚠️  Erro ao salvar no banco: {e}")


# ─── Utilitários ─────────────────────────────────────────────────────────────
def extrair_url_real(href: str) -> str:
    """Remove o redirect do DuckDuckGo e retorna a URL real."""
    if not href:
        return ""
    if "duckduckgo.com/l/" in href or href.startswith("//duckduckgo.com"):
        match = re.search(r"uddg=([^&]+)", href)
        if match:
            return unquote(match.group(1))
    if href.startswith("/"):
        return "https://duckduckgo.com" + href
    return href


def extrair_dominio(url: str) -> str:
    """Retorna o domínio limpo da URL."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        host = host.replace("www.", "")
        return host
    except Exception:
        return url


def detectar_instituicao(titulo: str, descricao: str, url: str) -> str:
    """Tenta identificar a instituição de ensino no título, descrição ou URL."""
    texto = f"{titulo} {descricao} {url}".upper()
    for inst in INSTITUICOES_CONHECIDAS:
        if inst.upper() in texto:
            return inst
    dominio = extrair_dominio(url)
    if dominio.endswith(".edu.br") or dominio.endswith(".gov.br"):
        partes = dominio.replace(".edu.br", "").replace(".gov.br", "").split(".")
        if partes:
            return partes[-1].upper()
    padroes = [
        r"(Universidade\s+(?:Federal|Estadual|Municipal)?\s*(?:de|do|da|dos|das)?\s+[\w\s]+?)[\s,\-\|]",
        r"(Instituto\s+Federal\s+(?:de|do|da)?\s*[\w\s]+?)[\s,\-\|]",
        r"(CEFET[\-\s]\w+)",
        r"(SENAC[\-\s]?\w*)",
        r"(SENAI[\-\s]?\w*)",
    ]
    texto_orig = f"{titulo} {descricao}"
    for padrao in padroes:
        m = re.search(padrao, texto_orig, re.IGNORECASE)
        if m:
            return m.group(1).strip()[:80]
    return extrair_dominio(url) or "—"


def detectar_nivel(titulo: str, descricao: str, consulta: str) -> str:
    texto = f"{titulo} {descricao} {consulta}".lower()
    if "doutorado"    in texto: return "Doutorado"
    if "mestrado"     in texto: return "Mestrado"
    if "mba"          in texto: return "MBA"
    if "pós-graduação" in texto or "pos-graduacao" in texto or "especialização" in texto:
        return "Pós-graduação"
    if "tecnólogo"    in texto or "tecnologo" in texto: return "Tecnólogo"
    if "técnico"      in texto or "tecnico"   in texto: return "Técnico"
    return "Graduação"


def detectar_area(titulo: str, descricao: str) -> str:
    texto = f"{titulo} {descricao}".lower()
    mapeamento = [
        ("ciência da computação",     "Ciência da Computação"),
        ("ciência de dados",          "Ciência de Dados"),
        ("análise e desenvolvimento", "ADS"),
        ("análise de sistemas",       "ADS"),
        ("banco de dados",            "Banco de Dados"),
        ("engenharia de software",    "Engenharia de Software"),
        ("engenharia de computação",  "Engenharia de Computação"),
        ("sistemas de informação",    "Sistemas de Informação"),
        ("sistemas para internet",    "Sistemas para Internet"),
        ("inteligência artificial",   "Inteligência Artificial"),
        ("segurança da informação",   "Segurança da Informação"),
        ("cibersegurança",            "Cibersegurança"),
        ("redes de computadores",     "Redes de Computadores"),
        ("tecnologia da informação",  "Tecnologia da Informação"),
        ("desenvolvimento web",       "Desenvolvimento Web"),
        ("desenvolvimento mobile",    "Desenvolvimento Mobile"),
        ("jogos digitais",            "Jogos Digitais"),
        ("cloud computing",           "Cloud Computing"),
        ("computação em nuvem",       "Cloud Computing"),
        ("internet das coisas",       "IoT"),
        ("iot",                       "IoT"),
        ("ux design",                 "UX Design"),
        ("ui design",                 "UX/UI Design"),
        ("gestão de ti",              "Gestão de TI"),
        ("blockchain",                "Blockchain"),
        ("robótica",                  "Robótica"),
        ("automação",                 "Automação"),
        ("computação",                "Computação"),
        ("informática",               "Informática"),
    ]
    for chave, label in mapeamento:
        if chave in texto:
            return label
    return "Tecnologia"


def detectar_status_vaga(titulo: str, descricao: str) -> str:
    """
    Detecta se a vaga provavelmente está aberta com base em heurísticas:
    - 'Aberto':    tem palavras de inscrição aberta + menciona ano atual ou futuro
    - 'Provável':  tem palavras de inscrição aberta mas sem data identificável
    - 'Encerrado': menciona apenas anos passados (sem ano atual/futuro)
    """
    texto_lower = f"{titulo} {descricao}".lower()
    texto_raw   = f"{titulo} {descricao}"
    ano_atual   = datetime.now().year

    # Anos mencionados no texto
    anos = [int(a) for a in re.findall(r"\b(20\d{2})\b", texto_raw)]
    tem_ano_atual_futuro = any(a >= ano_atual for a in anos)
    tem_so_anos_passados = bool(anos) and all(a < ano_atual for a in anos)

    # Palavras que indicam inscrição aberta
    palavras_aberto = CONFIG.get("palavras_aberto", [])
    tem_aberto = any(p.lower() in texto_lower for p in palavras_aberto)

    if tem_so_anos_passados:
        return "Encerrado"

    if tem_aberto and tem_ano_atual_futuro:
        return "Aberto"

    if tem_aberto:
        return "Provável"

    if tem_ano_atual_futuro:
        return "Provável"

    return "Encerrado"


# ─── Scraping ────────────────────────────────────────────────────────────────
async def pesquisar(page, consulta: str) -> list[dict]:
    log(f"🔎 Pesquisando: {consulta}")

    url = "https://html.duckduckgo.com/html/?q=" + consulta.replace(" ", "+")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        resultados = await page.locator(".result").all()
        log(f"   ↳ {len(resultados)} resultado(s) encontrado(s)")

        dados = []
        for resultado in resultados[:10]:
            try:
                titulo = await resultado.locator(".result__a").inner_text()
                href   = await resultado.locator(".result__a").get_attribute("href")

                try:
                    descricao = await resultado.locator(".result__snippet").inner_text()
                except Exception:
                    descricao = ""

                url_real    = extrair_url_real(href or "")
                instituicao = detectar_instituicao(titulo, descricao, url_real)
                nivel       = detectar_nivel(titulo, descricao, consulta)
                area        = detectar_area(titulo, descricao)
                status_vaga = detectar_status_vaga(titulo, descricao)

                dados.append({
                    "titulo":      titulo.strip(),
                    "url":         url_real,
                    "descricao":   descricao.strip(),
                    "instituicao": instituicao,
                    "nivel":       nivel,
                    "area":        area,
                    "status_vaga": status_vaga,
                    "consulta":    consulta,
                })
            except Exception:
                continue

        return dados

    except Exception as erro:
        log(f"❌ Erro na pesquisa: {erro}")
        return []


# ─── Relatório HTML ───────────────────────────────────────────────────────────
STATUS_CONFIG = {
    "Aberto":    {"emoji": "🟢", "color": "#22c55e", "bg": "rgba(34,197,94,.12)",  "border": "rgba(34,197,94,.35)"},
    "Provável":  {"emoji": "🟡", "color": "#eab308", "bg": "rgba(234,179,8,.12)",  "border": "rgba(234,179,8,.35)"},
    "Encerrado": {"emoji": "🔴", "color": "#ef4444", "bg": "rgba(239,68,68,.08)",  "border": "rgba(239,68,68,.25)"},
}


def gerar_html(resultados: list[dict]) -> str:
    areas  = sorted(set(r["area"]  for r in resultados))
    niveis = sorted(set(r["nivel"] for r in resultados))

    n_aberto    = sum(1 for r in resultados if r.get("status_vaga") == "Aberto")
    n_provavel  = sum(1 for r in resultados if r.get("status_vaga") == "Provável")
    n_encerrado = sum(1 for r in resultados if r.get("status_vaga") == "Encerrado")
    total       = len(resultados)
    data_str    = datetime.now().strftime("%d/%m/%Y às %H:%M")
    ano_atual   = datetime.now().year

    # ── Cards ──
    cards_html = ""
    for i, r in enumerate(resultados):
        url       = r["url"] or "#"
        titulo    = r["titulo"]
        inst      = r["instituicao"] or "—"
        area      = r["area"]
        nivel     = r["nivel"]
        descricao = r["descricao"][:350] + ("…" if len(r["descricao"]) > 350 else "")
        dominio   = extrair_dominio(url)
        status    = r.get("status_vaga", "Provável")
        sc        = STATUS_CONFIG.get(status, STATUS_CONFIG["Provável"])

        nivel_color = {
            "Doutorado":    "#7c3aed",
            "Mestrado":     "#2563eb",
            "MBA":          "#0891b2",
            "Pós-graduação":"#0d9488",
            "Tecnólogo":    "#059669",
            "Técnico":      "#65a30d",
            "Graduação":    "#d97706",
        }.get(nivel, "#6b7280")

        encerrado_class = ' encerrado-card' if status == "Encerrado" else ''

        cards_html += f"""
        <article class="card{encerrado_class}" data-area="{area}" data-nivel="{nivel}" data-status="{status}">
            <div class="card-header">
                <div class="card-badges">
                    <span class="badge badge-status" style="background:{sc['bg']};color:{sc['color']};border-color:{sc['border']}">{sc['emoji']} {status}</span>
                    <span class="badge badge-area">{area}</span>
                    <span class="badge badge-nivel" style="background:{nivel_color}22;color:{nivel_color};border-color:{nivel_color}44">{nivel}</span>
                </div>
                <a class="card-title" href="{url}" target="_blank" rel="noopener">{titulo}</a>
            </div>
            <div class="card-body">
                <div class="card-inst">
                    <span class="icon">🏛️</span>
                    <span class="inst-name">{inst}</span>
                </div>
                <p class="card-desc">{descricao or "Sem descrição disponível."}</p>
            </div>
            <div class="card-footer">
                <a class="card-link" href="{url}" target="_blank" rel="noopener">
                    <span>🔗</span> {dominio}
                </a>
                <span class="card-num">#{i + 1}</span>
            </div>
        </article>"""

    area_opts  = "".join(f'<option value="{a}">{a}</option>' for a in areas)
    nivel_opts = "".join(f'<option value="{n}">{n}</option>' for n in niveis)
    visiveis_default = n_aberto + n_provavel

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RadarCursos — Vagas Abertas em Tecnologia</title>
    <meta name="description" content="Radar de cursos gratuitos de tecnologia com vagas abertas no ensino superior brasileiro.">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --bg:       #0f0f13;
            --surface:  #18181f;
            --surface2: #22222c;
            --border:   #2a2a38;
            --accent:   #6366f1;
            --text:     #e4e4f0;
            --muted:    #8888aa;
            --radius:   14px;
        }}

        body {{ font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }}

        /* ── Header ── */
        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border-bottom: 1px solid var(--border);
            padding: 2.5rem 2rem 2rem;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        header::before {{
            content: '';
            position: absolute; inset: 0;
            background: radial-gradient(ellipse at 50% 0%, rgba(99,102,241,.25) 0%, transparent 70%);
        }}
        .header-inner {{ position: relative; z-index: 1; max-width: 900px; margin: auto; }}
        header h1 {{
            font-size: clamp(2rem, 5vw, 3rem); font-weight: 800;
            background: linear-gradient(135deg, #c7d2fe, #a5b4fc, #818cf8);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
            letter-spacing: -1px;
        }}
        header p {{ color: var(--muted); margin-top: .5rem; font-size: .95rem; }}
        .header-stats {{
            display: flex; justify-content: center; gap: 1rem;
            margin-top: 1.2rem; flex-wrap: wrap;
        }}
        .stat-chip {{
            border-radius: 999px; padding: .4rem 1rem;
            font-size: .82rem; font-weight: 700;
            border: 1px solid transparent; cursor: default;
        }}
        .stat-aberto   {{ background: rgba(34,197,94,.12);  color: #4ade80; border-color: rgba(34,197,94,.3); }}
        .stat-provavel {{ background: rgba(234,179,8,.12);  color: #fbbf24; border-color: rgba(234,179,8,.3); }}
        .stat-encerrado {{ background: rgba(239,68,68,.08); color: #f87171; border-color: rgba(239,68,68,.25); }}
        .stat-total     {{ background: rgba(99,102,241,.12);color: #a5b4fc; border-color: rgba(99,102,241,.3); }}

        /* ── Controls ── */
        .controls {{
            max-width: 1300px; margin: 1.8rem auto .5rem;
            padding: 0 1.5rem;
            display: flex; gap: .8rem; flex-wrap: wrap; align-items: center;
        }}
        .controls input, .controls select {{
            background: var(--surface); border: 1px solid var(--border);
            color: var(--text); border-radius: 10px; padding: .55rem 1rem;
            font-size: .9rem; font-family: inherit; outline: none;
            transition: border-color .2s;
        }}
        .controls input {{ flex: 1; min-width: 200px; }}
        .controls input:focus, .controls select:focus {{ border-color: var(--accent); }}
        .controls select option {{ background: #1e1e2a; }}

        .btn {{ border-radius: 10px; padding: .55rem 1.1rem; font-size: .88rem; font-family: inherit; cursor: pointer; font-weight: 600; border: 1px solid transparent; transition: background .2s, color .2s; }}
        .btn-reset {{ background: rgba(99,102,241,.12); border-color: rgba(99,102,241,.35); color: #a5b4fc; }}
        .btn-reset:hover {{ background: rgba(99,102,241,.25); }}
        .btn-encerrado {{
            background: rgba(239,68,68,.08); border-color: rgba(239,68,68,.25); color: #f87171;
        }}
        .btn-encerrado.ativo {{
            background: rgba(239,68,68,.2); border-color: rgba(239,68,68,.5); color: #fca5a5;
        }}
        .btn-encerrado:hover {{ background: rgba(239,68,68,.18); }}

        /* ── Counter ── */
        .counter {{ max-width: 1300px; margin: .4rem auto; padding: 0 1.5rem; color: var(--muted); font-size: .85rem; }}
        .counter strong {{ color: #a5b4fc; }}

        /* ── Grid ── */
        .grid {{ max-width: 1300px; margin: 1rem auto 3rem; padding: 0 1.5rem;
            display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.2rem; }}

        /* ── Card ── */
        .card {{
            background: var(--surface); border: 1px solid var(--border);
            border-radius: var(--radius); display: flex; flex-direction: column;
            transition: transform .2s, box-shadow .2s, border-color .2s;
        }}
        .card:hover {{ transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,.4); border-color: rgba(99,102,241,.5); }}
        .encerrado-card {{ opacity: .45; filter: grayscale(.6); }}
        .encerrado-card:hover {{ opacity: .7; }}

        .card-header {{ padding: 1.1rem 1.2rem .7rem; border-bottom: 1px solid var(--border); }}
        .card-badges {{ display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .6rem; }}
        .badge {{
            font-size: .7rem; font-weight: 700; border-radius: 6px;
            padding: .2rem .55rem; letter-spacing: .03em; text-transform: uppercase;
            border: 1px solid transparent;
        }}
        .badge-area {{ background: rgba(99,102,241,.15); color: #a5b4fc; border-color: rgba(99,102,241,.3); }}
        .badge-nivel {{ background: rgba(217,119,6,.12); color: #fbbf24; border-color: rgba(217,119,6,.3); }}
        .card-title {{ display: block; font-size: .98rem; font-weight: 700; color: var(--text); text-decoration: none; line-height: 1.4; transition: color .2s; }}
        .card-title:hover {{ color: #a5b4fc; }}

        .card-body {{ padding: .8rem 1.2rem; flex: 1; }}
        .card-inst {{ display: flex; align-items: center; gap: .45rem; margin-bottom: .6rem; }}
        .icon {{ font-size: 1rem; }}
        .inst-name {{ font-size: .85rem; font-weight: 600; color: #94a3b8; }}
        .card-desc {{ font-size: .83rem; color: var(--muted); line-height: 1.55; }}

        .card-footer {{ padding: .8rem 1.2rem; border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }}
        .card-link {{ display: flex; align-items: center; gap: .35rem; font-size: .78rem; color: var(--accent); text-decoration: none; font-weight: 600; max-width: 80%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; transition: color .2s; }}
        .card-link:hover {{ color: #c7d2fe; }}
        .card-num {{ font-size: .75rem; color: #444460; font-weight: 700; }}

        /* ── Empty state ── */
        .empty {{ text-align: center; padding: 4rem 1rem; color: var(--muted); display: none; }}
        .empty.visible {{ display: block; }}

        /* ── Aviso ── */
        .aviso {{
            max-width: 1300px; margin: 0 auto .5rem; padding: 0 1.5rem;
        }}
        .aviso-box {{
            background: rgba(234,179,8,.08); border: 1px solid rgba(234,179,8,.25);
            border-radius: 10px; padding: .7rem 1rem;
            font-size: .82rem; color: #d4b44a; line-height: 1.5;
        }}

        footer {{ text-align: center; padding: 1.5rem; color: #444460; font-size: .8rem; border-top: 1px solid var(--border); }}

        .card.hidden {{ display: none !important; }}
    </style>
</head>
<body>

<header>
    <div class="header-inner">
        <h1>🎓 RadarCursos</h1>
        <p>Vagas abertas em cursos gratuitos de tecnologia · {data_str}</p>
        <div class="header-stats">
            <span class="stat-chip stat-aberto">🟢 {n_aberto} Aberto(s)</span>
            <span class="stat-chip stat-provavel">🟡 {n_provavel} Provável(is)</span>
            <span class="stat-chip stat-encerrado">🔴 {n_encerrado} Encerrado(s)</span>
            <span class="stat-chip stat-total">📊 {total} total</span>
        </div>
    </div>
</header>

<div class="aviso">
    <div class="aviso-box">
        ⚠️ <strong>Atenção:</strong> O status de cada vaga é estimado automaticamente com base nas palavras-chave e datas encontradas na descrição. Sempre acesse o link oficial para confirmar se as inscrições estão abertas.
    </div>
</div>

<div class="controls">
    <input type="search" id="busca" placeholder="🔍 Filtrar por título, instituição ou descrição…" oninput="filtrar()">
    <select id="filtroArea" onchange="filtrar()">
        <option value="">Todas as áreas</option>
        {area_opts}
    </select>
    <select id="filtroNivel" onchange="filtrar()">
        <option value="">Todos os níveis</option>
        {nivel_opts}
    </select>
    <select id="filtroStatus" onchange="filtrar()">
        <option value="ativos">🟢🟡 Apenas abertos/prováveis</option>
        <option value="Aberto">🟢 Só abertos</option>
        <option value="Provável">🟡 Só prováveis</option>
        <option value="">Todos (incluir encerrados)</option>
    </select>
    <button class="btn btn-reset" onclick="resetar()">✕ Limpar</button>
</div>

<p class="counter" id="counter">Exibindo <strong id="visivel">{visiveis_default}</strong> de <strong>{total}</strong> resultado(s)</p>

<main class="grid" id="grid">
    {cards_html}
</main>

<div class="empty" id="empty">
    <p style="font-size:2rem">🔍</p>
    <p style="margin-top:.5rem">Nenhum resultado encontrado para os filtros selecionados.</p>
</div>

<footer>RadarCursos &mdash; Gerado em {data_str} · Ano de referência: {ano_atual} · Dados via DuckDuckGo</footer>

<script>
    // Ocultar encerrados por padrão
    document.querySelectorAll('.card[data-status="Encerrado"]').forEach(c => c.classList.add('hidden'));

    function filtrar() {{
        const busca      = document.getElementById('busca').value.toLowerCase();
        const area       = document.getElementById('filtroArea').value;
        const nivel      = document.getElementById('filtroNivel').value;
        const statusSel  = document.getElementById('filtroStatus').value;
        const cards      = document.querySelectorAll('.card');
        let visivel = 0;

        cards.forEach(card => {{
            const texto  = card.innerText.toLowerCase();
            const st     = card.dataset.status;

            const okBusca  = !busca || texto.includes(busca);
            const okArea   = !area  || card.dataset.area  === area;
            const okNivel  = !nivel || card.dataset.nivel === nivel;
            let   okStatus = true;

            if (statusSel === 'ativos')   okStatus = st === 'Aberto' || st === 'Provável';
            else if (statusSel === '')     okStatus = true;
            else                           okStatus = st === statusSel;

            if (okBusca && okArea && okNivel && okStatus) {{
                card.classList.remove('hidden');
                visivel++;
            }} else {{
                card.classList.add('hidden');
            }}
        }});

        document.getElementById('visivel').textContent = visivel;
        document.getElementById('empty').classList.toggle('visible', visivel === 0);
    }}

    function resetar() {{
        document.getElementById('busca').value        = '';
        document.getElementById('filtroArea').value   = '';
        document.getElementById('filtroNivel').value  = '';
        document.getElementById('filtroStatus').value = 'ativos';
        filtrar();
    }}
</script>
</body>
</html>"""

    return html


# ─── Telegram Alertas ─────────────────────────────────────────────────────────
def enviar_alerta_telegram(resultados_abertos: list[dict]):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return

    if not resultados_abertos:
        log("📢 Telegram: Nenhuma vaga com status 'Aberto' para notificar.")
        return

    log(f"📢 Enviando alerta Telegram para {len(resultados_abertos)} curso(s) abertos...")

    linhas = [
        "🎓 *RadarCursos — Novos Cursos Encontrados!*",
        f"📅 _{datetime.now().strftime('%d/%m/%Y %H:%M')}_\n"
    ]

    for i, r in enumerate(resultados_abertos[:8], start=1):
        titulo = r['titulo'].replace('*', '').replace('_', '')
        inst = r['instituicao'].replace('*', '').replace('_', '')
        url = r['url']
        linhas.append(f"🟢 *{i}. {titulo}*")
        linhas.append(f"🏛️ {inst} | 🎓 {r['nivel']}")
        linhas.append(f"🔗 [Acessar edital]({url})\n")

    if len(resultados_abertos) > 8:
        linhas.append(f"_+ mais {len(resultados_abertos) - 8} vagas no relatório completo!_")

    mensagem = "\n".join(linhas)

    try:
        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": mensagem,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true"
        }).encode("utf-8")
        req = urllib.request.Request(api_url, data=payload)
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                log("✅ Alerta Telegram enviado com sucesso!")
    except Exception as err:
        log(f"⚠️ Falha ao enviar Telegram: {err}")


# ─── Main ─────────────────────────────────────────────────────────────────────
async def main():
    limpar_log()

    log("=" * 70)
    log("RADAR DE CURSOS DE TECNOLOGIA")
    log("=" * 70)
    log("Início: " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    log(f"Total de consultas planejadas: {len(CONSULTAS)}")

    con = iniciar_db()
    todos_resultados: list[dict] = []
    urls_vistas: set[str] = set()

    async with async_playwright() as playwright:
        navegador = await playwright.chromium.launch(headless=True)
        pagina    = await navegador.new_page(viewport={"width": 1366, "height": 768})

        for i, consulta in enumerate(CONSULTAS, start=1):
            log(f"\n[{i}/{len(CONSULTAS)}] {consulta}")
            resultados = await pesquisar(pagina, consulta)

            for r in resultados:
                url = r["url"]
                if url and url not in urls_vistas:
                    urls_vistas.add(url)
                    todos_resultados.append(r)
                    salvar_resultado(con, consulta, r)

            await asyncio.sleep(2)

        await navegador.close()

    con.close()

    # ── Contadores por status ──
    abertos     = [r for r in todos_resultados if r["status_vaga"] == "Aberto"]
    provaveis   = [r for r in todos_resultados if r["status_vaga"] == "Provável"]
    encerrados  = [r for r in todos_resultados if r["status_vaga"] == "Encerrado"]

    n_aberto    = len(abertos)
    n_provavel  = len(provaveis)
    n_encerrado = len(encerrados)

    # ── Resumo no terminal ──
    print()
    print("=" * 70)
    print(f"  TOTAL DE RESULTADOS ÚNICOS: {len(todos_resultados)}")
    print(f"  🟢 Abertos:    {n_aberto}")
    print(f"  🟡 Prováveis:  {n_provavel}")
    print(f"  🔴 Encerrados: {n_encerrado}")
    print("=" * 70)

    for i, r in enumerate(todos_resultados, start=1):
        status_emoji = {"Aberto": "🟢", "Provável": "🟡", "Encerrado": "🔴"}.get(r["status_vaga"], "⚪")
        print(f"\n  {status_emoji} #{i}  [{r['nivel']}] {r['area']}")
        print(f"  Título:      {r['titulo']}")
        print(f"  Instituição: {r['instituicao']}")
        print(f"  Link:        {r['url']}")
        print(f"  Status:      {r['status_vaga']}")
        print(f"  Descrição:   {r['descricao'][:180]}{'…' if len(r['descricao']) > 180 else ''}")
        print(f"  {'-' * 66}")

    # ── Gerar relatório HTML ──
    relatorio_path = os.path.join(BASE_DIR, "relatorio.html")
    html = gerar_html(todos_resultados)

    with open(relatorio_path, "w", encoding="utf-8") as f:
        f.write(html)

    log(f"\n✅ Relatório HTML gerado: {relatorio_path}")
    log(f"✅ Resultados únicos: {len(todos_resultados)} ({n_aberto} abertos, {n_provavel} prováveis, {n_encerrado} encerrados)")

    # ── Alerta Telegram (opcional via variável de ambiente) ──
    enviar_alerta_telegram(abertos)

    log("RADAR FINALIZADO")

    # Abrir automaticamente no navegador local apenas se NÃO estiver em ambiente de CI/Actions
    if not os.environ.get("CI"):
        webbrowser.open(f"file:///{relatorio_path.replace(os.sep, '/')}")


if __name__ == "__main__":
    asyncio.run(main())