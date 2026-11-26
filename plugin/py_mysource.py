#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
from urllib.parse import quote, urljoin


class Spider(Spider):
    """自建源示例：央视网公开接口，栏目 -> 列表 -> 详情 -> HLS 直链"""

    LIST_COLUMN = "https://api.cntv.cn/NewVideo/getVideoListByColumn"
    LIST_ALBUM = "https://api.cntv.cn/NewVideo/getVideoListByAlbumIdNew"
    VIDEO_INFO = "https://vdn.apps.cntv.cn/api/getHttpVideoInfo.do"
    PAGE_SIZE = 20

    COLUMNS = [
        ("动物世界", "TOPC1451378967257534"),
        ("探索发现", "TOPC1451557893544236"),
        ("我爱发明", "TOPC1569314345479107"),
        ("我爱发明·新版", "TOPC1451557970755294"),
        ("经典咏流传 第五季", "VIDAIiNbDQzOjE5mLl3T4t2B220403"),
        ("等着我", "TOPC1451378757637200"),
    ]

    header = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://tv.cctv.com/"
    }
    config = {
        "player": {},
        "filter": {}
    }

    def getName(self):
        return "自建·央视"

    def init(self, extend=""):
        self.extend = (extend or "").strip()

    def isVideoFormat(self, url):
        return str(url).split("?")[0].lower().endswith((".m3u8", ".mp4", ".flv"))

    def manualVideoCheck(self):
        return False

    # ---------------- 内部方法 ----------------

    def _list_url(self, tid, pg, year=""):
        api = self.LIST_COLUMN if str(tid).startswith("TOPC") else self.LIST_ALBUM
        url = "{}?id={}&p={}&n={}&sort=desc&mode=0&serviceId=tvcctv&t=json".format(
            api, tid, pg, self.PAGE_SIZE)
        if year:
            url += "&d={}".format(quote(str(year)))
        return url

    def _to_videos(self, jo):
        videos = []
        data = jo.get("data") or {}
        for vod in data.get("list") or []:
            image = vod.get("image", "")
            brief = (vod.get("brief", "") or "").replace("\r", " ").replace("\n", " ").strip()
            videos.append({
                "vod_id": "{}###{}".format(vod.get("guid", ""), image),
                "vod_name": vod.get("title", ""),
                "vod_pic": image,
                "vod_remarks": brief[:28]
            })
        return videos

    # ---------------- 接口 ----------------

    def homeContent(self, filter):
        result = {
            "class": [{"type_name": n, "type_id": i} for n, i in self.COLUMNS],
            "filters": {}
        }
        # 需要年份筛选时按下面格式加，key 必须和栏目 type_id 对上：
        # result["filters"]["TOPC1451557970755294"] = [{"key": "d", "name": "年份",
        #     "value": [{"n": "全部", "v": ""}, {"n": "2025", "v": "2025"}]}]
        return result

    def homeVideoContent(self):
        try:
            tid = self.COLUMNS[0][1]
            rsp = self.fetch(self._list_url(tid, 1), headers=self.header)
            return {"list": self._to_videos(rsp.json())}
        except Exception as e:
            print("homeVideoContent error:", e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"list": [], "page": int(pg), "pagecount": 9999,
                  "limit": self.PAGE_SIZE, "total": 999999}
        try:
            year = ""
            if isinstance(extend, dict):
                year = extend.get("d", "")
            rsp = self.fetch(self._list_url(tid, int(pg), year), headers=self.header)
            jo = rsp.json()
            videos = self._to_videos(jo)
            total = int((jo.get("data") or {}).get("total") or 0)
            result["list"] = videos
            result["limit"] = len(videos) or self.PAGE_SIZE
            if total:
                result["pagecount"] = max(int(pg), (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
                result["total"] = total
        except Exception as e:
            print("categoryContent error:", e)
        return result

    def detailContent(self, array):
        try:
            item = array[0] if isinstance(array, list) else array
            pid, _, pic = str(item).partition("###")
            rsp = self.fetch("{}?pid={}".format(self.VIDEO_INFO, pid), headers=self.header)
            jo = rsp.json()
            title = (jo.get("title") or "").strip() or pid

            eps = []
            for ch in jo.get("chapters") or []:
                url = ch.get("url") or ""
                if not url:
                    continue
                name = ch.get("title") or "分段{}".format(len(eps) + 1)
                eps.append("{}${}".format(name, url))
            if not eps and jo.get("hls_url"):
                eps = ["{}${}".format(title, jo.get("hls_url").strip())]

            vod = {
                "vod_id": pid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": "",
                "vod_remarks": "",
                "vod_year": "",
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_play_from": "CCTV",
                "vod_play_url": "#".join(eps)
            }
            return {"list": [vod]}
        except Exception as e:
            print("detailContent error:", e)
            return {"list": []}

    def searchContent(self, key, quick):
        # 央视站内搜索接口已下线，这里退化为“各栏目最近一页本地匹配”。
        # 接全站搜索时只改这一个方法即可，其余不用动。
        videos = []
        try:
            k = (key or "").lower()
            for _, tid in self.COLUMNS:
                rsp = self.fetch(self._list_url(tid, 1), headers=self.header)
                for v in self._to_videos(rsp.json()):
                    if k in v["vod_name"].lower():
                        videos.append(v)
                if len(videos) >= 30:
                    break
        except Exception as e:
            print("searchContent error:", e)
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        # CCTV 返回的就是 HLS 直链，直接交给播放器，不需要嗅探
        return {"parse": 0, "playUrl": "", "url": id, "header": self.header}

    def localProxy(self, param):
        # 代理地址：http://127.0.0.1:UndCover/proxy?do=py_mysource&api=python&type=m3u8&url=...
        typ = param.get("type", "")
        url = param.get("url", "")
        if typ == "m3u8" and url:
            content = self.fetch(url, headers=self.header).text
            lines = []
            for line in content.splitlines():
                line = line.strip()
                # 相对路径和 /asp/... 这种绝对路径都要补成完整地址
                if line and not line.startswith("#"):
                    line = urljoin(url, line)
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
