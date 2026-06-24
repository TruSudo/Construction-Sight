import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_chain_cli import app

runner = CliRunner()


def _listing_html() -> str:
    return """
    <html>
      <body>
        <table>
          <tr class="result">
            <td><a href="/Project/2017101033">2017101033</a></td>
            <td>SCH Number</td><td>2017101033</td>
            <td>Lead/Public Agency</td><td>San Bernardino County</td>
            <td>County</td><td>San Bernardino</td>
          </tr>
          <tr class="result">
            <td><a href="/Project/2026061234">2026061234</a></td>
            <td>SCH Number</td><td>2026061234</td>
            <td>Lead/Public Agency</td><td>Fontana, City of</td>
            <td>County</td><td>San Bernardino</td>
          </tr>
        </table>
      </body>
    </html>
    """


def _detail_html() -> str:
    return """
    <html>
      <body>
        <main>
          <h1>Project Details</h1>
          <dl>
            <dt>Project Title</dt><dd>San Bernardino Countywide Plan</dd>
            <dt>SCH Number</dt><dd>2017101033</dd>
            <dt>Project Description</dt><dd>Countywide policy plan.</dd>
          </dl>
        </main>
      </body>
    </html>
    """


def _execution_json(path: Path, *, body_text: str, final_url: str) -> None:
    payload = {
        "metadata": {"schema_version": "ceqanet_execution_fixture.v1"},
        "snapshots": [
            {
                "method": "GET",
                "request_url": final_url,
                "final_url": final_url,
                "status_code": 200,
                "content_type": "text/html; charset=utf-8",
                "body_text": body_text,
                "body_length": len(body_text),
                "body_truncated": False,
                "executed": True,
                "reachable": True,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_chain_cli_emits_json(tmp_path: Path) -> None:
    listing_path = tmp_path / "listing.json"
    detail_path = tmp_path / "detail.json"
    _execution_json(
        listing_path,
        body_text=_listing_html(),
        final_url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
    )
    _execution_json(
        detail_path,
        body_text=_detail_html(),
        final_url="https://ceqanet.lci.ca.gov/Project/2017101033",
    )

    result = runner.invoke(
        app,
        [
            "build",
            "--listing-execution",
            str(listing_path),
            "--detail-execution",
            str(detail_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_chain_report.v1"
    assert payload["metadata"]["network_executed"] is False
    assert payload["metadata"]["persistence_mutated"] is False
    assert payload["metadata"]["result_record_count"] == 2
    assert payload["metadata"]["detail_parse_count"] == 1
    assert payload["metadata"]["enriched_count"] == 1
    assert payload["metadata"]["missing_detail_count"] == 1
    assert payload["metadata"]["sch_mismatch_count"] == 0
    assert payload["result_parse"]["metadata"]["record_count"] == 2
    assert payload["detail_parse_summaries"][0]["sch_number"] == "2017101033"
    assert payload["enrichment"]["records"][0]["title"] == "San Bernardino Countywide Plan"
    assert payload["enrichment"]["records"][0]["enrichment_status"] == "enriched"
    assert payload["enrichment"]["records"][1]["enrichment_status"] == "missing_detail"


def test_ceqanet_chain_cli_writes_json_output(tmp_path: Path) -> None:
    listing_path = tmp_path / "listing.json"
    output_path = tmp_path / "chain.json"
    _execution_json(
        listing_path,
        body_text=_listing_html(),
        final_url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
    )

    result = runner.invoke(
        app,
        [
            "build",
            "--listing-execution",
            str(listing_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet chain report JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["result_record_count"] == 2
    assert payload["metadata"]["detail_parse_count"] == 0
    assert payload["metadata"]["missing_detail_count"] == 2


def test_ceqanet_chain_cli_rejects_output_without_json(tmp_path: Path) -> None:
    listing_path = tmp_path / "listing.json"
    _execution_json(
        listing_path,
        body_text=_listing_html(),
        final_url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
    )

    result = runner.invoke(
        app,
        [
            "build",
            "--listing-execution",
            str(listing_path),
            "--output",
            str(tmp_path / "chain.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_chain_cli_rejects_empty_listing_snapshots(tmp_path: Path) -> None:
    listing_path = tmp_path / "listing.json"
    listing_path.write_text(json.dumps({"snapshots": []}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "build",
            "--listing-execution",
            str(listing_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "must contain a non-empty snapshots list" in result.output


def test_ceqanet_chain_cli_rejects_snapshot_without_body_text(tmp_path: Path) -> None:
    listing_path = tmp_path / "listing.json"
    listing_path.write_text(
        json.dumps({"snapshots": [{"final_url": "https://ceqanet.lci.ca.gov/Search"}]}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            "--listing-execution",
            str(listing_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "selected snapshot must contain string body_text" in result.output
