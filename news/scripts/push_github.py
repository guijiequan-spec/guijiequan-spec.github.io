#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
增量推送目录到 GitHub 仓库子目录（默认 news/）。

与裁员看板那份的区别：先在本地算 git blob sha1，与远端 tree 比对，
只上传真正变化的文件 —— 新闻站点文件多，全量重传会很慢。

Token 读取顺序：--token / GITHUB_TOKEN / <工作区>/.workbuddy/github_token.txt /
~/.workbuddy/github_token.txt / <本目录>/.github_token
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".workbuddy", ".idea", ".vscode"}
SKIP_NAMES = {".DS_Store", "Thumbs.db", ".github_token", "github_token.txt",
              "new_items.json", "push-to-github.bat"}
SKIP_SUFFIX = {".pyc", ".pyo", ".log", ".tmp"}


def find_token(cli=None):
    if cli:
        return cli.strip()
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env.strip()
    here = Path(__file__).resolve().parent.parent      # news-hub/
    for p in [here.parent / ".workbuddy" / "github_token.txt",
              Path.home() / ".workbuddy" / "github_token.txt",
              here / ".github_token"]:
        try:
            if p.is_file():
                t = p.read_text(encoding="utf-8").strip()
                if t:
                    return t
        except OSError:
            pass
    return None


def blob_sha(data):
    """git 计算 blob 哈希的算法，可与远端 tree 的 sha 直接比对。"""
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def api(method, path, token, payload=None, retries=2):
    url = path if path.startswith("http") else API + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    last = (0, {"message": "unknown"})
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + token)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "news-hub-sync")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read().decode("utf-8")
                return r.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            try:
                j = json.loads(body)
            except Exception:
                j = {"message": body[:400]}
            last = (e.code, j)
            if e.code in (500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return last
        except urllib.error.URLError as e:
            last = (0, {"message": "网络不可达: %s" % e.reason})
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return last
    return last


def collect(local_dir):
    out = {}
    root = Path(local_dir)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if set(rel.parts[:-1]) & SKIP_DIRS:
            continue
        if rel.name in SKIP_NAMES or p.suffix in SKIP_SUFFIX:
            continue
        out["/".join(rel.parts)] = p.read_bytes()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="guijiequan-spec/guijiequan-spec.github.io")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--target", default="news")
    ap.add_argument("--message", default="chore: 更新新闻情报中心")
    ap.add_argument("--token", default=None)
    ap.add_argument("--force", action="store_true", help="忽略 sha 比对，全部重传")
    args = ap.parse_args()

    token = find_token(args.token)
    if not token:
        print("[FAIL] 未找到 GitHub Token，请写入 %s"
              % (Path(args.dir).parent / ".workbuddy" / "github_token.txt"))
        return 2

    repo, branch = args.repo, args.branch
    target = args.target.strip("/")
    prefix = (target + "/") if target else ""

    files = collect(args.dir)
    if not files:
        print("[FAIL] 本地目录为空")
        return 3

    # 本地 git blob sha
    local_sha = {prefix + k: blob_sha(v) for k, v in files.items()}

    st, me = api("GET", "/user", token)
    if st != 200:
        print("[FAIL] Token 无效 (%s): %s" % (st, (me or {}).get("message")))
        return 4

    st, ref = api("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch), token)
    if st != 200:
        print("[FAIL] 读取分支失败 (%s): %s" % (st, (ref or {}).get("message")))
        return 5
    base_sha = ref["object"]["sha"]

    st, bc = api("GET", "/repos/%s/git/commits/%s" % (repo, base_sha), token)
    if st != 200:
        print("[FAIL] 读取 commit 失败 (%s)" % st)
        return 5
    base_tree = bc["tree"]["sha"]

    st, tree = api("GET", "/repos/%s/git/trees/%s?recursive=1" % (repo, base_tree), token)
    existing = {}
    if st == 200:
        for node in tree.get("tree", []):
            if node.get("type") == "blob":
                existing[node["path"]] = node["sha"]

    # 差异：新增/变更 + 待删除
    changed = [p for p, s in local_sha.items() if args.force or existing.get(p) != s]
    stale = [p for p in existing if p.startswith(prefix) and p not in local_sha]

    print("[1/4] 本地 %d 文件｜远端同目录 %d 文件"
          % (len(files), sum(1 for k in existing if k.startswith(prefix))))
    print("[2/4] 需上传 %d 个，需删除 %d 个" % (len(changed), len(stale)))

    if not changed and not stale:
        print("无变化，跳过提交。")
        return 0

    entries = []
    rev = {prefix + k: v for k, v in files.items()}
    for i, p in enumerate(sorted(changed), 1):
        st, blob = api("POST", "/repos/%s/git/blobs" % repo, token, {
            "content": base64.b64encode(rev[p]).decode("ascii"),
            "encoding": "base64",
        })
        if st not in (200, 201):
            print("[FAIL] 上传失败 %s (%s): %s" % (p, st, (blob or {}).get("message")))
            if st == 403:
                print("       → 403：Token 缺少 Contents: Read and write")
            return 6
        entries.append({"path": p, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        if i % 20 == 0 or i == len(changed):
            print("      已上传 %d/%d" % (i, len(changed)))

    for p in stale:
        entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})

    st, new_tree = api("POST", "/repos/%s/git/trees" % repo, token,
                       {"base_tree": base_tree, "tree": entries})
    if st not in (200, 201):
        print("[FAIL] 建 tree 失败 (%s): %s" % (st, (new_tree or {}).get("message")))
        return 7

    st, commit = api("POST", "/repos/%s/git/commits" % repo, token,
                     {"message": args.message, "tree": new_tree["sha"], "parents": [base_sha]})
    if st not in (200, 201):
        print("[FAIL] 建 commit 失败 (%s)" % st)
        return 8

    st, upd = api("PATCH", "/repos/%s/git/refs/heads/%s" % (repo, branch), token,
                  {"sha": commit["sha"], "force": False})
    if st not in (200, 201):
        print("[WARN] 首次更新分支失败 (%s)，可能被并发提交抢先，重试一次" % st)
        st2, ref2 = api("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch), token)
        if st2 == 200:
            st, upd = api("PATCH", "/repos/%s/git/refs/heads/%s" % (repo, branch), token,
                          {"sha": commit["sha"], "force": False})
        if st not in (200, 201):
            print("[FAIL] 更新分支失败 (%s): %s" % (st, (upd or {}).get("message")))
            return 9

    print("[3/4] commit %s" % commit["sha"][:10])
    print("[4/4] 已推送 → https://%s.github.io/%s/"
          % (repo.split("/")[0].lower(), target))
    return 0


if __name__ == "__main__":
    sys.exit(main())
