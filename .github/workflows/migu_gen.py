#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migu_gen.py - 从 8.138.7.223 咪咕工具批量生成 m3u8 源
流程：
  1. 登录 ds/login.php
  2. 读取 tool/migu.php 的地址前缀列表
  3. 逐个 check_api 检测，只保留"有效"前缀
  4. 对每个有效前缀调用 tool/mg.php?url=<前缀> 获取频道列表(TXT)
  5. 转成 m3u 格式，写出 migu/m1.m3u8 ... + migu/sources.txt(索引)
用法：python3 migu_gen.py
输出：./migu/*.m3u8 和 ./migu/sources.txt
"""
import re
import os
import sys
import ssl
import urllib.parse
import urllib.request
import http.cookiejar

SITE = "http://8.138.7.223/ds"
LOGIN_URL = SITE + "/login.php"
MIGU_URL = SITE + "/tool/migu.php"
MG_URL = SITE + "/tool/mg.php"

USERNAME = "yjb0913"
PASSWORD = "qQ10291319"

# 输出目录与"源文件"在仓库里的访问前缀（用于写 sources.txt）
OUT_DIR = "migu"
REPO_M3U_BASE = "https://godlike.ezpull.asia/https://raw.githubusercontent.com/yangjb0913/Collect-IPTV/main/migu/"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"


class Session:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPRedirectHandler(),
        )

    def req(self, url, data=None, timeout=30):
        headers = {"User-Agent": UA, "Referer": MIGU_URL}
        body = None
        if data is not None:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        r = self.opener.open(urllib.request.Request(url, data=body, headers=headers), timeout=timeout)
        return r.status, r.read()


def login(s):
    code, body = s.req(LOGIN_URL, {"username": USERNAME, "password": PASSWORD}, timeout=30)
    # 302 -> index.php 表示成功
    print(f"[login] status={code}")
    if code != 200:
        print("[login] FAILED, 请检查账号/网络")
        return False
    return True


def get_prefixes(s):
    code, body = s.req(MIGU_URL)
    html = body.decode("utf-8", "ignore")
    prefixes = re.findall(r'data-api="([^"]+)"[^>]*>.*?data-addr="([^"]+)"', html, re.S)
    # 以 data-addr 为准
    addrs = []
    for api, addr in prefixes:
        if addr not in addrs:
            addrs.append(addr)
    print(f"[prefixes] 共 {len(addrs)} 个: {addrs}")
    return addrs


def check_valid(s, prefix):
    code, body = s.req(MIGU_URL, {"check_api": prefix}, timeout=60)
    return body.decode("utf-8", "ignore").strip() == "ok"


def fetch_list(s, prefix):
    url = MG_URL + "?url=" + urllib.parse.quote(prefix, safe="")
    code, body = s.req(url, timeout=60)
    if code != 200:
        return None
    return body.decode("utf-8", "ignore")


def txt_to_m3u(txt, group):
    """TXT(频道名,地址) 转 m3u。"""
    lines = ["#EXTM3U"]
    for line in txt.splitlines():
        line = line.strip()
        if not line or "," not in line or "#genre#" in line:
            continue
        name, url = line.split(",", 1)
        name = name.strip()
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            continue
        lines.append(f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    s = Session()
    if not login(s):
        sys.exit(1)

    prefixes = get_prefixes(s)
    valid = [p for p in prefixes if check_valid(s, p)]
    print(f"[valid] 有效前缀 {len(valid)} 个: {valid}")
    if not valid:
        print("[valid] 没有有效前缀")
        sys.exit(1)

    index = []
    for i, prefix in enumerate(valid, start=1):
        txt = fetch_list(s, prefix)
        if not txt:
            print(f"[gen] {prefix} 生成失败，跳过")
            continue
        m3u = txt_to_m3u(txt, "咪咕直播")
        fname = os.path.join(OUT_DIR, f"m{i}.m3u8")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(m3u)
        count = m3u.count("#EXTINF")
        index.append(f"{REPO_M3U_BASE}m{i}.m3u8")
        print(f"[gen] {prefix} -> {fname} ({count} 频道)")

    if not index:
        print("[gen] 没有生成任何文件")
        sys.exit(1)

    idx_name = os.path.join(OUT_DIR, "sources.txt")
    with open(idx_name, "w", encoding="utf-8") as f:
        f.write("\n".join(index) + "\n")
    print(f"[index] 写入 {idx_name}，共 {len(index)} 个源")
    for u in index:
        print("   ", u)


if __name__ == "__main__":
    main()
