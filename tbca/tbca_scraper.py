#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrator da Tabela Brasileira de Composicao de Alimentos (TBCA - USP/FoRC).
Fonte: https://www.tbca.net.br/  (Licenca CC BY-NC-ND 4.0 - uso pessoal, citar a fonte)

Arquitetura (o site mudou em 2026 -> ver NOTAS):
  Fase 1 - CATALOGO: percorre composicao_alimentos.php?pagina=N (UTF-8),
           coleta por linha: codigo, descricao, nome_cientifico, grupo, marca
           e o HREF (token criptografado) para a pagina de detalhe. Deduplica por codigo.
  Fase 2 - DETALHES: para cada item, abre a pagina via HREF e le a tabela de
           nutrientes (Componente | Unidades | Valor por 100g). Captura TODOS os
           componentes exatamente como o site mostra (mantem 'tr', virgula decimal etc).

Robustez nuvem: checkpoint em disco a cada CHECKPOINT_EVERY itens e commit no
git a cada COMMIT_EVERY itens, para uma nova sessao retomar de onde parou.

NOTAS sobre mudancas do site (vs. instrucoes originais):
  - Encoding agora e UTF-8 (nao ISO-8859-1).
  - A pagina de detalhe NAO aceita mais ?cod_produto=CODIGO; so o token criptografado
    presente no href da listagem funciona. Por isso o catalogo guarda o href.
  - Paginacao por GET: ?pagina=N&atuald=X (100/pagina, ~59 paginas).
"""
import json
import os
import re
import sys
import time
import subprocess
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
BASE = "https://www.tbca.net.br/base-dados/"
LIST_URL = BASE + "composicao_alimentos.php"
HERE = os.path.dirname(os.path.abspath(__file__))

CATALOG_FILE = os.path.join(HERE, "tbca_catalog.json")
CHECKPOINT_FILE = os.path.join(HERE, "tbca_checkpoint.json")
JSON_OUT = os.path.join(HERE, "tbca.json")
XLSX_OUT = os.path.join(HERE, "tbca.xlsx")
LOG_FILE = os.path.join(HERE, "scrape.log")

DELAY = 0.6              # pausa entre requisicoes
MAX_RETRIES = 5
CHECKPOINT_EVERY = 50
COMMIT_EVERY = 200
GIT_BRANCH = "claude/tbca-extract"
DO_GIT_COMMIT = True

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TBCA-personal-extract/1.0; CC BY-NC-ND)",
    "Accept": "text/html,application/xhtml+xml",
}


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url, params=None):
    """GET com retry/backoff. Forca UTF-8 (site declara charset=UTF-8)."""
    backoff = 2
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = SESSION.get(url, params=params, timeout=40)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            log(f"  ! fetch falhou (tentativa {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(backoff)
                backoff *= 2
    raise RuntimeError(f"GET falhou apos {MAX_RETRIES} tentativas: {url} :: {last_err}")


# ---------------------------- FASE 1: CATALOGO ------------------------------
def parse_list_page(html):
    """Retorna lista de dicts da pagina de listagem."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []
    out = []
    for tr in table.find_all("tr")[1:]:  # pula header
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        a = tr.find("a", href=True)
        href = urljoin(BASE, a["href"]) if a else None
        codigo = tds[0].get_text(strip=True)
        if not codigo:
            continue
        out.append({
            "codigo": codigo,
            "descricao": tds[1].get_text(strip=True),
            "nome_cientifico": tds[2].get_text(strip=True) if len(tds) > 2 else "",
            "grupo": tds[3].get_text(strip=True) if len(tds) > 3 else "",
            "marca": tds[4].get_text(strip=True) if len(tds) > 4 else "",
            "href": href,
        })
    return out


def build_catalog():
    if os.path.exists(CATALOG_FILE):
        with open(CATALOG_FILE, encoding="utf-8") as f:
            cat = json.load(f)
        log(f"Catalogo existente carregado: {len(cat)} itens")
        return cat
    log("Construindo catalogo (percorrendo paginas)...")
    seen = set()
    catalog = []
    page = 1
    empty_streak = 0
    while True:
        atuald = ((page - 1) // 10) + 1
        html = fetch(LIST_URL, params={"pagina": page, "atuald": atuald})
        rows = parse_list_page(html)
        if not rows:
            empty_streak += 1
            log(f"  pagina {page}: 0 linhas")
            if empty_streak >= 2:
                break
            page += 1
            time.sleep(DELAY)
            continue
        empty_streak = 0
        added = 0
        for r in rows:
            if r["codigo"] in seen:
                continue
            seen.add(r["codigo"])
            catalog.append(r)
            added += 1
        log(f"  pagina {page}: {len(rows)} linhas, +{added} novos (total {len(catalog)})")
        page += 1
        time.sleep(DELAY)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    log(f"Catalogo salvo: {len(catalog)} itens unicos")
    return catalog


# ---------------------------- FASE 2: DETALHES ------------------------------
def parse_detail(html):
    """Le a tabela de nutrientes.
    Retorna (nutrientes, medidas, n_rows):
      nutrientes = {"Componente (unid)": valor_por_100g}
      medidas    = [{"medida": <nome porcao>, "valores": {"Componente (unid)": valor}}, ...]
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="display") or soup.find("table")
    nutrientes = {}
    medidas = []
    n_rows = 0
    if not table:
        return nutrientes, medidas, 0
    rows = table.find_all("tr")
    if not rows:
        return nutrientes, medidas, 0
    header = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    # localiza a coluna "Valor por 100g" de forma robusta
    val_idx = 2
    for i, h in enumerate(header):
        if "100g" in h.replace(" ", "").lower() or "100 g" in h.lower():
            val_idx = i
            break
    # colunas de medidas caseiras = tudo apos "Valor por 100g"
    measure_names = header[val_idx + 1:]
    medidas_valores = [dict() for _ in measure_names]
    for tr in rows[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) <= val_idx:
            continue
        componente = cells[0].get_text(strip=True)
        unidade = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        valor = cells[val_idx].get_text(strip=True)
        if not componente:
            continue
        key = f"{componente} ({unidade})" if unidade else componente
        # se houver chave repetida (raro), nao sobrescreve silenciosamente
        if key in nutrientes:
            key = f"{componente} ({unidade}) [{n_rows}]"
        nutrientes[key] = valor
        # valores das medidas caseiras para este componente
        for j, _ in enumerate(measure_names):
            ci = val_idx + 1 + j
            if ci < len(cells):
                medidas_valores[j][key] = cells[ci].get_text(strip=True)
        n_rows += 1
    for name, vals in zip(measure_names, medidas_valores):
        if name:
            medidas.append({"medida": name, "valores": vals})
    return nutrientes, medidas, n_rows


def git_commit(msg):
    if not DO_GIT_COMMIT:
        return
    try:
        subprocess.run(["git", "add", "-f", CHECKPOINT_FILE, CATALOG_FILE], cwd=HERE,
                       check=False, capture_output=True)
        r = subprocess.run(["git", "commit", "-m", msg], cwd=HERE,
                           check=False, capture_output=True, text=True)
        if r.returncode == 0:
            log(f"  git commit ok: {msg}")
            # push para sobreviver a reset de container (retry/backoff)
            backoff = 2
            for attempt in range(1, 5):
                p = subprocess.run(["git", "push", "origin", GIT_BRANCH], cwd=HERE,
                                   check=False, capture_output=True, text=True)
                if p.returncode == 0:
                    log(f"  git push ok ({len(msg)})")
                    break
                log(f"  git push falhou (tent {attempt}): {p.stderr.strip()[:120]}")
                time.sleep(backoff)
                backoff *= 2
        else:
            # nada a commitar nao e erro
            if "nothing to commit" not in (r.stdout + r.stderr):
                log(f"  git commit aviso: {r.stdout.strip()} {r.stderr.strip()}")
    except Exception as e:
        log(f"  git commit falhou: {e}")


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("results", {})
    return {}


def save_checkpoint(results):
    tmp = CHECKPOINT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False)
    os.replace(tmp, CHECKPOINT_FILE)


def scrape(catalog, limit=None):
    results = load_checkpoint()
    log(f"Iniciando detalhes. Ja processados: {len(results)}")
    failures = []
    pending = [c for c in catalog if c["codigo"] not in results]
    if limit:
        pending = pending[:limit]
    log(f"A processar agora: {len(pending)} (limit={limit})")
    done_since_commit = 0
    for i, item in enumerate(pending, 1):
        cod = item["codigo"]
        try:
            html = fetch(item["href"])
            nutrientes, medidas, n_rows = parse_detail(html)
            if n_rows == 0:
                failures.append(cod)
                log(f"  [{i}/{len(pending)}] {cod}: 0 nutrientes (FALHA)")
            else:
                log(f"  [{i}/{len(pending)}] {cod}: {n_rows} nutrientes, {len(medidas)} medidas")
            results[cod] = {
                "codigo": cod,
                "descricao": item["descricao"],
                "nome_cientifico": item.get("nome_cientifico", ""),
                "grupo": item.get("grupo", ""),
                "marca": item.get("marca", ""),
                "nutrientes": nutrientes,
                "medidas_caseiras": medidas,
            }
        except Exception as e:
            failures.append(cod)
            log(f"  [{i}/{len(pending)}] {cod}: ERRO {e}")
        done_since_commit += 1
        if i % CHECKPOINT_EVERY == 0:
            save_checkpoint(results)
            log(f"  -- checkpoint salvo ({len(results)} itens) --")
        if done_since_commit >= COMMIT_EVERY:
            save_checkpoint(results)
            git_commit(f"tbca: checkpoint {len(results)} alimentos")
            done_since_commit = 0
        time.sleep(DELAY)
    save_checkpoint(results)
    return results, failures


# ---------------------------- SAIDAS ----------------------------------------
def write_outputs(results):
    # ordena por codigo
    items = [results[k] for k in sorted(results.keys())]
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    log(f"tbca.json salvo: {len(items)} alimentos")

    # uniao de todas as colunas de nutrientes (ordem de primeira aparicao)
    from openpyxl import Workbook
    nutrient_cols = []
    seen = set()
    for it in items:
        for k in it["nutrientes"].keys():
            if k not in seen:
                seen.add(k)
                nutrient_cols.append(k)
    wb = Workbook()
    ws = wb.active
    ws.title = "Por_100g"
    base_cols = ["codigo", "descricao", "nome_cientifico", "grupo", "marca"]
    ws.append(base_cols + nutrient_cols)
    for it in items:
        row = [it["codigo"], it["descricao"], it.get("nome_cientifico", ""),
               it.get("grupo", ""), it.get("marca", "")]
        nut = it["nutrientes"]
        row += [nut.get(c, "") for c in nutrient_cols]
        ws.append(row)

    # Aba 2: medidas caseiras em formato longo (escalavel)
    ws2 = wb.create_sheet("Medidas_Caseiras")
    ws2.append(["codigo", "descricao", "medida", "componente_unidade", "valor"])
    n_med = 0
    for it in items:
        for med in it.get("medidas_caseiras", []):
            nome = med["medida"]
            for comp, val in med["valores"].items():
                ws2.append([it["codigo"], it["descricao"], nome, comp, val])
                n_med += 1
    wb.save(XLSX_OUT)
    log(f"tbca.xlsx salvo: aba Por_100g={len(items)} linhas x {len(nutrient_cols)} nutrientes; "
        f"aba Medidas_Caseiras={n_med} linhas")
    return len(items), len(nutrient_cols), nutrient_cols


# ---------------------------- MAIN ------------------------------------------
def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=None,
                   help="limita numero de alimentos a processar (teste)")
    p.add_argument("--catalog-only", action="store_true")
    p.add_argument("--outputs-only", action="store_true",
                   help="apenas gera tbca.json/xlsx a partir do checkpoint")
    args = p.parse_args()

    if args.outputs_only:
        results = load_checkpoint()
        n, ncols, _ = write_outputs(results)
        log(f"RESUMO: {n} alimentos, {ncols} colunas de nutrientes")
        return

    catalog = build_catalog()
    if args.catalog_only:
        log(f"Catalogo pronto: {len(catalog)} itens")
        return

    results, failures = scrape(catalog, limit=args.limit)
    n, ncols, cols = write_outputs(results)
    log("=" * 60)
    log(f"RESUMO FINAL: {n} alimentos | {ncols} colunas de nutrientes")
    log(f"Catalogo total: {len(catalog)} | processados: {len(results)}")
    if failures:
        log(f"FALHAS ({len(failures)}): {failures[:50]}{' ...' if len(failures) > 50 else ''}")
    else:
        log("Sem falhas.")


if __name__ == "__main__":
    main()
