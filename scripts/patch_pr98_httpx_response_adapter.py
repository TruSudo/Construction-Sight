"""Apply the exact HTTPX response-adapter correction for PR #98."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/constructionsight/ceqanet_csv_live_service.py"


def replace_once(old: str, new: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one PR98 patch anchor, found {count}: {old!r}")
    PATH.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        "import hashlib\nfrom collections.abc import Mapping\n",
        "import hashlib\nfrom collections.abc import Mapping\nfrom dataclasses import dataclass\n",
    )
    replace_once(
        "class _HttpxCsvClientAdapter:\n",
        "@dataclass(frozen=True)\n"
        "class _HttpxCsvResponseAdapter:\n"
        "    status_code: int\n"
        "    content: bytes\n"
        "    url: str\n"
        "    headers: dict[str, str]\n\n\n"
        "class _HttpxCsvClientAdapter:\n",
    )
    replace_once(
        "    ) -> httpx.Response:\n"
        "        \"\"\"Fetch one URL using the wrapped configured HTTPX client.\"\"\"\n\n"
        "        return self._client.get(\n"
        "            url,\n"
        "            follow_redirects=follow_redirects,\n"
        "            timeout=timeout,\n"
        "        )\n",
        "    ) -> CeqanetCsvLiveHttpResponse:\n"
        "        \"\"\"Fetch one URL and narrow the rich HTTPX response contract.\"\"\"\n\n"
        "        response = self._client.get(\n"
        "            url,\n"
        "            follow_redirects=follow_redirects,\n"
        "            timeout=timeout,\n"
        "        )\n"
        "        return _HttpxCsvResponseAdapter(\n"
        "            status_code=response.status_code,\n"
        "            content=response.content,\n"
        "            url=str(response.url),\n"
        "            headers=dict(response.headers),\n"
        "        )\n",
    )


if __name__ == "__main__":
    main()
