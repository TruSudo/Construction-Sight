"""Apply exact production and test corrections for PR #98."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "src/constructionsight/ceqanet_csv_live_service.py"
TEST_PATH = ROOT / "tests/test_ceqanet_csv_live.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one PR98 patch anchor in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        SERVICE_PATH,
        "import hashlib\nfrom collections.abc import Mapping\n",
        "import hashlib\nfrom collections.abc import Mapping\nfrom dataclasses import dataclass\n",
    )
    replace_once(
        SERVICE_PATH,
        "class CeqanetCsvLiveHttpResponse(Protocol):\n"
        "    \"\"\"Minimal response contract used by the one-request executor.\"\"\"\n\n"
        "    status_code: int\n"
        "    content: bytes\n"
        "    url: Any\n"
        "    headers: Mapping[str, str]\n",
        "class CeqanetCsvLiveHttpResponse(Protocol):\n"
        "    \"\"\"Read-only response contract used by the one-request executor.\"\"\"\n\n"
        "    @property\n"
        "    def status_code(self) -> int:\n"
        "        \"\"\"Return the HTTP response status.\"\"\"\n\n"
        "    @property\n"
        "    def content(self) -> bytes:\n"
        "        \"\"\"Return the exact response bytes.\"\"\"\n\n"
        "    @property\n"
        "    def url(self) -> Any:\n"
        "        \"\"\"Return the final response URL.\"\"\"\n\n"
        "    @property\n"
        "    def headers(self) -> Mapping[str, str]:\n"
        "        \"\"\"Return response headers through a read-only mapping contract.\"\"\"\n",
    )
    replace_once(
        SERVICE_PATH,
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
        SERVICE_PATH,
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
    replace_once(
        TEST_PATH,
        "import json\nfrom dataclasses import dataclass\n",
        "import json\nimport re\nfrom dataclasses import dataclass\n",
    )
    replace_once(
        TEST_PATH,
        "runner = CliRunner()\n",
        "runner = CliRunner()\n"
        "_ANSI_ESCAPE = re.compile(r\"\\x1b\\[[0-9;]*m\")\n"
        "_RICH_BORDER = str.maketrans(\"\", \"\", \"│╭╮╰╯─\")\n\n\n"
        "def _plain_terminal(text: str) -> str:\n"
        "    without_ansi = _ANSI_ESCAPE.sub(\"\", text)\n"
        "    without_border = without_ansi.translate(_RICH_BORDER)\n"
        "    return \" \".join(without_border.split())\n",
    )
    replace_once(
        TEST_PATH,
        "    assert result.exit_code != 0\n"
        "    assert \"explicit --execute-live authorization is required\" in result.output\n",
        "    assert result.exit_code != 0\n"
        "    assert (\n"
        "        \"explicit --execute-live authorization is required\"\n"
        "        in _plain_terminal(result.output)\n"
        "    )\n",
    )


if __name__ == "__main__":
    main()
