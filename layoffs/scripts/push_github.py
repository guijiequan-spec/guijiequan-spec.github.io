#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把看板目录同步推送到 GitHub 仓库的指定子目录（默认 layoffs/）。

依赖：仅标准库（urllib），无需 pip 安装。

Token 读取顺序：
  1. 环境变量 GITHUB_TOKEN
  2. <工作区>/.workbuddy/github_token.txt
  3. ~/.workbuddy/github_token.txt
  4. 看板目录/.github_token

用法：
  python scripts/push_github.py                    # 用默认参数推送
  python scripts/push_github.py --dry-run          # 只算差异，不写
  python scripts/push_github.py --repo owner/repo --target layoffs

权限要求（fine-grained PAT）：
  Contents: Read and write   +   Metadata: Read
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"

# 沙箱出网对 api.github.com 会间歇性 SSL EOF，靠重试兜住
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = [3, 8, 20]          # 第 1/2/3 次重试前的等待
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# 不推送的本地垃圾
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".workbuddy", ".idea", ".vscode"}
SKIP_NAMES = {
    ".DS_Store", "Thumbs.db", ".github_token",
    "new_items.json",              # 每日增量暂存，合并入库后即无用
    "push-to-github.bat",          # 本地一键脚本，不必上网
    "github_token.txt",
}
SKIP_SUFFIX = {".pyc", ".pyo", ".log"}


def find_token(cli_token=None):
    if cli_token:
        return cli_token.strip()
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return env.strip()
    here = Path(__file__).resolve().parent.parent          # china-layoffs-dashboard/
    ws = here.parent                                        # 工作区根目录
    candidates = [
        ws / ".workbuddy" / "github_token.txt",
        Path.home() / ".workbuddy" / "github_token.txt",
        here / ".github_token",
    ]
    for p in candidates:
        try:
            if p.is_file():
                t = p.read_text(encoding="utf-8").strip()
                if t:
                    return t
        except OSError:
            pass
    return None


def api(method, path, token, payload=None, accept="application/vnd.github+json"):
    url = path if path.startswith("http") else API + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "layoffs-dashboard-sync")
    if data:
        req.add_header("Content-Type", "application/json")

    last_status, last_payload = 0, {"message": "未知错误"}
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read().decode("utf-8")
                return r.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            try:
                j = json.loads(body)
            except Exception:
                j = {"message": body[:400]}
            last_status, last_payload = e.code, j
            # 401/403/404/422 是凭证或请求本身的问题，重试无用
            if e.code not in RETRYABLE_STATUS:
                return e.code, j
        except urllib.error.URLError as e:
            last_status, last_payload = 0, {"message": "网络不可达: %s" % e.reason}

        if attempt < MAX_ATTEMPTS - 1:
            wait = BACKOFF_SECONDS[attempt]
            print("      [retry] 第 %d 次失败（%s），%d 秒后重试…"
                  % (attempt + 1, (last_payload or {}).get("message"), wait))
            time.sleep(wait)

    return last_status, last_payload


def collect(local_dir):
    """返回 {相对路径: bytes}，相对路径用 / 分隔。"""
    out = {}
    root = Path(local_dir)
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        parts = set(rel.parts[:-1])
        if parts & SKIP_DIRS:
            continue
        if rel.name in SKIP_NAMES or p.suffix in SKIP_SUFFIX:
            continue
        out["/".join(rel.parts)] = p.read_bytes()
    return out


def verify_remote(repo, branch, target, local_dir):
    """回读远端核心数据文件，与本地比对条目数与 updated_at。"""
    checks = [("data/layoffs.json", "items"), ("data/summary.json", None)]
    # 两个文件记录时间的键名不同，都试一遍
    TIME_KEYS = ("updated_at", "generated_at", "source_updated_at")
    token = find_token()
    all_ok = True
    for rel, key in checks:
        path = "/repos/%s/contents/%s/%s" % (repo, target, rel) if target \
            else "/repos/%s/contents/%s" % (repo, rel)
        st, f = api("GET", path + "?ref=" + branch, token)
        if st != 200 or not f or "content" not in f:
            print("      [skip] 远端 %s 读取失败 (%s)" % (rel, st))
            continue
        try:
            remote = json.loads(base64.b64decode("".join(f["content"].split())).decode("utf-8"))
        except Exception as e:
            print("      [skip] 远端 %s 解析失败: %s" % (rel, e))
            continue
        local = json.loads((Path(local_dir) / rel).read_text(encoding="utf-8"))
        if key:
            rn, ln = len(remote.get(key, [])), len(local.get(key, []))
            same = rn == ln
            print("      [%s] %s 条目数 远端=%d 本地=%d"
                  % ("OK  " if same else "FAIL", rel, rn, ln))
            all_ok = all_ok and same
        for tk in TIME_KEYS:
            if tk in remote:
                ru, lu = remote.get(tk), local.get(tk)
                same = ru == lu
                print("      [%s] %s %s 远端=%s 本地=%s"
                      % ("OK  " if same else "FAIL", rel, tk, ru, lu))
                all_ok = all_ok and same
                break
    return all_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="guijiequan-spec/guijiequan-spec.github.io")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--target", default="layoffs", help="仓库内目标子目录，留空表示仓库根")
    ap.add_argument("--message", default="chore: 更新裁员看板数据")
    ap.add_argument("--token", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = find_token(args.token)
    if not token:
        print("[FAIL] 未找到 GitHub Token。请把 fine-grained PAT 写入：")
        print("       %s" % (Path(args.dir).parent / ".workbuddy" / "github_token.txt"))
        print("       或设置环境变量 GITHUB_TOKEN")
        return 2

    repo = args.repo
    branch = args.branch
    target = args.target.strip("/")

    files = collect(args.dir)
    if not files:
        print("[FAIL] 本地目录为空，未推送")
        return 3

    print("[1/6] 本地文件 %d 个" % len(files))

    # 0. 校验 token 与仓库可写
    st, me = api("GET", "/user", token)
    if st != 200:
        print("[FAIL] Token 无效或已过期 (%s): %s" % (st, (me or {}).get("message")))
        return 4
    print("      身份: %s" % me.get("login"))

    st, repo_info = api("GET", "/repos/%s" % repo, token)
    if st != 200:
        print("[FAIL] 读不到仓库 %s (%s): %s" % (repo, st, (repo_info or {}).get("message")))
        return 4
    perms = repo_info.get("permissions") or {}
    print("      仓库权限: push=%s admin=%s" % (perms.get("push"), perms.get("admin")))
    if not perms.get("push"):
        print("[WARN] 该 token 在仓库上没有 push 权限，后面写入大概率 403")

    # 1. 取分支 HEAD
    st, ref = api("GET", "/repos/%s/git/ref/heads/%s" % (repo, branch), token)
    if st == 404:
        print("[FAIL] 分支 %s 不存在（本脚本不负责初始化仓库）" % branch)
        return 5
    if st != 200:
        print("[FAIL] 读取分支失败 (%s): %s" % (st, (ref or {}).get("message")))
        return 5
    base_sha = ref["object"]["sha"]
    print("[2/6] 分支 %s HEAD = %s" % (branch, base_sha[:10]))

    # 2. 取基线 tree（递归）
    st, base_commit = api("GET", "/repos/%s/git/commits/%s" % (repo, base_sha), token)
    if st != 200:
        print("[FAIL] 读取 commit 失败 (%s)" % st)
        return 5
    base_tree = base_commit["tree"]["sha"]

    st, tree = api("GET", "/repos/%s/git/trees/%s?recursive=1" % (repo, base_tree), token)
    existing = {}
    if st == 200:
        for node in tree.get("tree", []):
            if node.get("type") == "blob":
                existing[node["path"]] = node["sha"]
    prefix = (target + "/") if target else ""
    print("[3/6] 仓库现有文件 %d 个（目标目录下 %d 个）"
          % (len(existing), sum(1 for k in existing if k.startswith(prefix))))

    # 3. 逐个建 blob
    entries = []
    for i, (rel, data) in enumerate(sorted(files.items()), 1):
        dest = prefix + rel
        st, blob = api("POST", "/repos/%s/git/blobs" % repo, token, {
            "content": base64.b64encode(data).decode("ascii"),
            "encoding": "base64",
        })
        if st not in (200, 201):
            print("[FAIL] 创建 blob 失败 %s (%s): %s" % (rel, st, (blob or {}).get("message")))
            if st == 403:
                print("       → 403 通常是 Token 缺少 Contents: Read and write 权限")
            return 6
        entries.append({"path": dest, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        if i % 10 == 0 or i == len(files):
            print("      已上传 %d/%d" % (i, len(files)))

    # 4. 删除目标目录下本地已不存在的历史文件
    local_set = {prefix + k for k in files}
    stale = [p for p in existing if p.startswith(prefix) and p not in local_set]
    for p in stale:
        entries.append({"path": p, "mode": "100644", "type": "blob", "sha": None})
    if stale:
        print("[4/6] 清理远端多余文件 %d 个" % len(stale))
    else:
        print("[4/6] 无多余文件需清理")

    if args.dry_run:
        print("[DRY-RUN] 将写入 %d 个文件到 %s/%s，未提交"
              % (len(files), repo, target or ""))
        return 0

    # 5. 建 tree + commit
    st, new_tree = api("POST", "/repos/%s/git/trees" % repo, token, {
        "base_tree": base_tree, "tree": entries,
    })
    if st not in (200, 201):
        print("[FAIL] 创建 tree 失败 (%s): %s" % (st, (new_tree or {}).get("message")))
        return 7

    st, commit = api("POST", "/repos/%s/git/commits" % repo, token, {
        "message": args.message, "tree": new_tree["sha"], "parents": [base_sha],
    })
    if st not in (200, 201):
        print("[FAIL] 创建 commit 失败 (%s): %s" % (st, (commit or {}).get("message")))
        return 8
    print("[5/6] commit %s" % commit["sha"][:10])

    # 6. 更新分支
    st, upd = api("PATCH", "/repos/%s/git/refs/heads/%s" % (repo, branch), token, {
        "sha": commit["sha"], "force": False,
    })
    if st not in (200, 201):
        print("[FAIL] 更新分支失败 (%s): %s" % (st, (upd or {}).get("message")))
        return 9
    print("[6/6] 已推送到 %s@%s" % (branch, commit["sha"][:10]))

    # 7. 回读远端，确认内容与本地一致（不只看退出码）
    ok = verify_remote(repo, branch, target, args.dir)
    if not ok:
        print("[WARN] 远端校验未通过，请手动复核："
              "https://github.com/%s/tree/%s/%s" % (repo, branch, target))
    print("")
    print("完成。若该仓库已开启 Pages，1–2 分钟后可访问：")
    print("  https://%s.github.io/%s/" % (repo.split("/")[0].lower(), target))
    return 0 if ok else 10


if __name__ == "__main__":
    sys.exit(main())
