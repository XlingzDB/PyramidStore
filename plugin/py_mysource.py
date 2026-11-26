#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import re
from urllib.parse import quote


class Spider(Spider):
    # ============ 1. 站点常量，改这里 ============
    BASE = "https://example.com"        # TODO 换成目标站根地址
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    header = {
        "User-Agent": UA,
        "Referer": BASE
    }
    config = {
        "player": {},
        "filter": {}
    }

    def getName(self):
        return "我的源"

    def init(self, extend=""):
        # extend 来自配置项 ext 后面的 ?extend=xxx，不要写进仓库
        self.extend = (extend or "").strip()
        self.timeout = 10

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(m3u8|mp4|flv)(\?|$)", url or ""))

    def manualVideoCheck(self):
        return False

    # ============ 2. 首页分类 ============
    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "电影", "type_id": "1"},
            {"type_name": "电视剧", "type_id": "2"},
            {"type_name": "综艺", "type_id": "3"},
            {"type_name": "动漫", "type_id": "4"},
        ]
        filters = {}   # 需要筛选就按下方格式填，不需要就给空 dict
        # filters = {"1": [{"key": "year", "name": "年份", "value": [
        #     {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}]}]}
        result["class"] = classes
        result["filters"] = filters
        return result

    def homeVideoContent(self):
        # 首页推荐，失败就返回空列表，绝对不要抛异常
        try:
            rsp = self.fetch(self.BASE, headers=self.header)
            root = self.html(rsp.text)
            videos = []
            for a in root.xpath('//ul[@class="vodlist"]/li/a'):     # TODO 换选择器
                href = a.get("href") or ""
                videos.append({
                    "vod_id": self.regStr(href, r"/(\d+)\.html"),
                    "vod_name": a.xpath('string(.)').strip(),
                    "vod_pic": "",
                    "vod_remarks": ""
                })
            return {"list": videos}
        except Exception as e:
            print("homeVideoContent error:", e)
            return {"list": []}

    # ============ 3. 分类列表 ============
    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 9999, "limit": 20, "total": 999999}
        try:
            url = "{}/list/{}/page/{}".format(self.BASE, tid, pg)   # TODO 分类链接规则
            rsp = self.fetch(url, headers=self.header)
            root = self.html(rsp.text)
            videos = []
            for li in root.xpath('//div[@class="module-item"]'):    # TODO 换选择器
                a = li.xpath('.//a')[0]
                href = a.get("href") or ""
                videos.append({
                    "vod_id": self.regStr(href, r"/(\d+)\.html"),
                    "vod_name": li.xpath('.//a[@class="title"]/text()')[0].strip(),
                    "vod_pic": "",
                    "vod_remarks": li.xpath('string(.//span[@class="note"])').strip()
                })
            result["list"] = videos
            result["limit"] = len(videos) or 20
        except Exception as e:
            print("categoryContent error:", e)
        return result

    # ============ 4. 详情 + 选集 ============
    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else ids
            url = "{}/detail/{}.html".format(self.BASE, vod_id)      # TODO 详情链接规则
            rsp = self.fetch(url, headers=self.header)
            root = self.html(rsp.text)

            name = root.xpath('//h1/text()')[0].strip()
            pic = root.xpath('//img[@class="lazyload"]/@data-src')
            play_urls = root.xpath('//ul[@class="content_playlist"]/li/a')  # TODO 换选择器

            eps = []
            for a in play_urls:
                ep_name = a.xpath('string(.)').strip()
                ep_url = a.get("href") or ""
                if ep_url.startswith("/"):
                    ep_url = self.BASE + ep_url
                eps.append("{}${}".format(ep_name, ep_url))

            vod = {
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic[0] if pic else "",
                "vod_content": "",
                "vod_play_from": "默认线路",
                "vod_play_url": "#".join(eps)
            }
            return {"list": [vod]}
        except Exception as e:
            print("detailContent error:", e)
            return {"list": []}

    # ============ 5. 搜索 ============
    def searchContent(self, key, quick):
        try:
            url = "{}/search/{}.html".format(self.BASE, quote(key))  # TODO 搜索链接规则
            rsp = self.fetch(url, headers=self.header)
            root = self.html(rsp.text)
            videos = []
            for li in root.xpath('//div[@class="module-item"]'):     # TODO 换选择器
                a = li.xpath('.//a')[0]
                videos.append({
                    "vod_id": self.regStr(a.get("href") or "", r"/(\d+)\.html"),
                    "vod_name": li.xpath('string(.//a[@class="title"])').strip(),
                    "vod_pic": "",
                    "vod_remarks": ""
                })
            return {"list": videos}
        except Exception as e:
            print("searchContent error:", e)
            return {"list": []}

    # ============ 6. 播放 ============
    def playerContent(self, flag, id, vipFlags):
        # 若 id 就是可直链播放的 m3u8/mp4，直接交给播放器
        if self.isVideoFormat(id):
            return {"parse": 0, "playUrl": "", "url": id, "header": self.header}
        # 若需要嗅探/解析，返回 parse 1 并给出详情页地址或解析接口
        return {"parse": 1, "playUrl": "", "url": id, "header": self.header}

    # ============ 7. 本地代理（处理 m3u8 相对路径等） ============
    def localProxy(self, param):
        # 代理地址：http://127.0.0.1:UndCover/proxy?do=py_mysource&api=python&type=m3u8&url=...
        typ = param.get("type", "")
        url = param.get("url", "")
        if typ == "m3u8" and url:
            content = self.fetch(url, headers=self.header).text
            base_dir = url.rsplit("/", 1)[0] + "/"
            lines = []
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("http"):
                    line = base_dir + line
                lines.append(line)
            action = {
                "url": "",
                "header": self.header,
                "param": "",
                "type": "string",
                "after": ""
            }
            return [200, "application/octet-stream", action, "\n".join(lines)]

        action = {
            "url": url,
            "header": self.header,
            "param": "",
            "type": "stream",
            "after": ""
        }
        return [200, "video/MP2T", action, ""]
