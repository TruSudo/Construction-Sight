from constructionsight.adapters.ceqanet_result_parser import parse_ceqanet_result_page


def test_parse_ceqanet_result_page_extracts_card_record() -> None:
    html = """
    <div class="search-result">
      <a href="/Project/2026061234">Fontana Warehouse Project</a>
      <dl>
        <dt>SCH Number</dt><dd>2026061234</dd>
        <dt>Lead Agency</dt><dd>Fontana, City of</dd>
        <dt>Document Type</dt><dd>NOP - Notice of Preparation of a Draft EIR</dd>
        <dt>County</dt><dd>San Bernardino</dd>
        <dt>City</dt><dd>Fontana</dd>
      </dl>
    </div>
    """

    report = parse_ceqanet_result_page(
        html,
        source_url="https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
    )

    assert report.record_count == 1
    record = report.records[0]
    assert record.title == "Fontana Warehouse Project"
    assert record.detail_url == "https://ceqanet.lci.ca.gov/Project/2026061234"
    assert record.sch_number == "2026061234"
    assert record.lead_agency == "Fontana, City of"
    assert record.document_type == "NOP - Notice of Preparation of a Draft EIR"
    assert record.county == "San Bernardino"
    assert record.city == "Fontana"


def test_parse_ceqanet_result_page_extracts_table_row_record() -> None:
    html = """
    <table>
      <tr>
        <th>Project</th><th>Agency</th>
      </tr>
      <tr>
        <td><a href="/Document/2024010001">Riverside Bridge Replacement</a></td>
        <td>Lead/Public Agency: Riverside County Transportation Commission</td>
        <td>SCH Number: 2024010001</td>
        <td>County: Riverside</td>
      </tr>
    </table>
    """

    report = parse_ceqanet_result_page(html)

    assert report.record_count == 1
    record = report.records[0]
    assert record.title == "Riverside Bridge Replacement"
    assert record.sch_number == "2024010001"
    assert record.lead_agency == "Riverside County Transportation Commission"
    assert record.county == "Riverside"


def test_parse_ceqanet_result_page_prefers_project_title_label_over_numeric_link() -> None:
    html = """
    <div class="search-result">
      <a href="/Project/2026060698">2026060698</a>
      <span>Project Title</span><span>Warehouse Distribution Center</span>
      <span>SCH Number</span><span>2026060698</span>
      <span>County</span><span>San Bernardino</span>
    </div>
    """

    report = parse_ceqanet_result_page(html)

    assert report.record_count == 1
    assert report.records[0].title == "Warehouse Distribution Center"
    assert report.records[0].sch_number == "2026060698"


def test_parse_ceqanet_result_page_uses_human_link_title_with_numeric_detail_link() -> None:
    html = """
    <div class="search-result">
      <a href="/Project/2026060698">2026060698</a>
      <a href="/Document/2026060698">Warehouse Distribution Center</a>
      <span>SCH Number</span><span>2026060698</span>
      <span>County</span><span>San Bernardino</span>
    </div>
    """

    report = parse_ceqanet_result_page(html)

    assert report.record_count == 1
    record = report.records[0]
    assert record.title == "Warehouse Distribution Center"
    assert record.sch_number == "2026060698"
    assert record.detail_url == "https://ceqanet.lci.ca.gov/Project/2026060698"


def test_parse_ceqanet_result_page_does_not_emit_fallback_links_when_blocks_parse() -> None:
    html = """
    <div class="search-result">
      <a href="/Project/2026060698">2026060698</a>
      <span>Project Title</span><span>Warehouse Distribution Center</span>
      <span>SCH Number</span><span>2026060698</span>
    </div>
    <a href="/Document/2026060698">2026060698</a>
    <a href="/Project/2026060698">2026060698</a>
    """

    report = parse_ceqanet_result_page(html)

    assert report.record_count == 1
    assert report.candidate_block_count == 1
    assert report.candidate_link_count == 3
    assert report.records[0].title == "Warehouse Distribution Center"


def test_parse_ceqanet_result_page_ignores_search_form_options_and_navigation() -> None:
    html = """
    <a href="/Home">Home</a>
    <select name="LeadAgency">
      <option>San Bernardino County</option>
      <option>Riverside County</option>
    </select>
    <form>
      <button>Search</button>
    </form>
    """

    report = parse_ceqanet_result_page(html)

    assert report.record_count == 0
    assert report.records == ()


def test_parse_ceqanet_result_page_deduplicates_block_and_link_records() -> None:
    html = """
    <article class="project-card">
      <a href="/Project/2025012345">Ontario Industrial Project</a>
      <span>SCH Number</span><span>2025012345</span>
    </article>
    """

    report = parse_ceqanet_result_page(html)

    assert report.record_count == 1
    assert report.candidate_block_count == 1
    assert report.candidate_link_count == 1


def test_parse_ceqanet_result_page_serializes_report() -> None:
    html = """
    <li>
      <a href="/Project/2025123456">Redlands Utility Project</a>
      <span>County: San Bernardino</span>
    </li>
    """

    payload = parse_ceqanet_result_page(html).to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_result_page_parse.v1"
    assert payload["metadata"]["record_count"] == 1
    assert payload["records"][0]["title"] == "Redlands Utility Project"
