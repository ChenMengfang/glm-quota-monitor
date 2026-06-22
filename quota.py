"""额度查询模块 —— 调用智谱/Z.ai 的 monitor 接口。

接口来源：官方插件 glm-plan-usage 的 query-usage.mjs
  https://github.com/zai-org/zai-coding-plugins

返回统一的 Quota 数据结构，供 GUI 使用。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class QuotaData:
    """一次查询的统一结果。"""
    level: str = ""                  # 套餐等级，如 "lite" / "pro"
    token_pct: float = 0.0           # 5h token 窗口使用百分比
    token_reset_ts: int | None = None
    mcp_pct: float = 0.0             # MCP 月用量百分比
    mcp_current: int = 0
    mcp_total: int = 0
    mcp_remaining: int = 0
    mcp_reset_ts: int | None = None
    mcp_details: list[dict] = field(default_factory=list)  # [{code, usage}]
    error: str = ""                  # 非空表示查询失败
    loaded: bool = False             # 是否已成功加载过真实数据

    @property
    def is_empty(self) -> bool:
        """从未加载过真实数据（刚启动的初始状态）。"""
        return not self.loaded and not self.error


def _http_get(url: str, auth_token: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={
        "Authorization": auth_token,            # 直接用 key，不加 Bearer
        "Content-Type": "application/json",
        "Accept-Language": "zh-CN,zh",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    j = json.loads(body)
    return j.get("data", j) if isinstance(j, dict) else j


def _platform_domain(base_url: str) -> tuple[str, str]:
    """从 base_url 提取域名，并返回 (domain, platform_label)。"""
    parsed = urllib.parse.urlparse(base_url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    if "api.z.ai" in base_url:
        return domain, "Z.ai"
    if "bigmodel.cn" in base_url:
        return domain, "智谱"
    return domain, "未知"


def query_quota(base_url: str, api_key: str) -> QuotaData:
    """查询套餐额度。失败时 QuotaData.error 被设置。"""
    result = QuotaData()
    if not api_key or not base_url:
        result.error = "缺少 Base URL 或 API Key"
        return result

    try:
        domain, _ = _platform_domain(base_url)
        quota_url = f"{domain}/api/monitor/usage/quota/limit"

        data = _http_get(quota_url, api_key)
        result.level = (data.get("level") or "").strip()

        for item in data.get("limits", []):
            t = item.get("type")
            if t == "TOKENS_LIMIT":
                result.token_pct = float(item.get("percentage", 0) or 0)
                result.token_reset_ts = item.get("nextResetTime")
            elif t == "TIME_LIMIT":
                result.mcp_pct = float(item.get("percentage", 0) or 0)
                result.mcp_current = int(item.get("currentValue", 0) or 0)
                result.mcp_total = int(item.get("usage", 0) or 0)
                result.mcp_remaining = int(item.get("remaining", 0) or 0)
                result.mcp_reset_ts = item.get("nextResetTime")
                for d in item.get("usageDetails", []):
                    result.mcp_details.append({
                        "code": d.get("modelCode", "?"),
                        "usage": d.get("usage", 0),
                    })
        result.loaded = True  # 成功解析过真实数据
    except Exception as e:  # noqa: BLE001
        result.error = str(e)[:120]
    return result


# ── 时间格式化辅助 ──────────────────────────────────────────────
def ts_to_countdown(ts_ms: int | None, now: datetime | None = None) -> str:
    """把毫秒时间戳转成 "1小时32分后" / "3天后" 倒计时文本。"""
    if not ts_ms:
        return ""
    now = now or datetime.now()
    delta = datetime.fromtimestamp(ts_ms / 1000) - now
    secs = max(0, int(delta.total_seconds()))
    if secs == 0:
        return "即将重置"
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins = rem // 60
    if days > 0:
        return f"{days}天{hours}小时后"
    if hours > 0:
        return f"{hours}小时{mins}分后"
    return f"{mins}分钟后"


def ts_to_clock(ts_ms: int | None) -> str:
    """毫秒时间戳 → "06-22 00:32" 钟点文本。"""
    if not ts_ms:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%m-%d %H:%M")
