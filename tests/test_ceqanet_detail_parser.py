from constructionsight.adapters.ceqanet_detail_parser import parse_ceqanet_detail_page


def test_parse_ceqanet_detail_page_extracts_labeled_project_metadata() -> None:
    html = """
    <html>
      <head><title>CEQAnet</title></head>
      <body>
        <main>
          <h1>Project Details</h1>
          <dl>
            <dt>Project Title</dt><dd>Fontana Warehouse Project</dd>
            <dt>SCH Number</dt><dd>2026061234</dd>
            <dt>Lead Agency</dt><dd>Fontana, City of</dd>
            <dt>Document Type</dt><dd>NOP - Notice of Preparation of a Draft EIR</dd>
            <dt>County</dt><dd>San Bernardino</dd>
            <dt>City</dt><dd>Fontana</dd>
            <dt>Project Location</dt><dd>Near I-10 and Sierra Avenue</dd>
            <dt>Contact Person</dt><dd>Planning Division</dd>
          </dl>
          <a href="/Documents/2026061234">Notice document</a>
        </main>
      </body>
    </html>
    """

    report = parse_ceqanet_detail_page(
        html,
        source_url="https://ceqanet.lci.ca.gov/Project/2026061234",
    )

    assert report.title == "Fontana Warehouse Project"
    assert report.title_source == "human_label"
    assert report.has_human_title is True
    assert report.sch_number == "2026061234"
    assert report.lead_agency == "Fontana, City of"
    assert report.document_type == "NOP - Notice of Preparation of a Draft EIR"
    assert report.county == "San Bernardino"
    assert report.city == "Fontana"
    assert report.project_location == "Near I-10 and Sierra Avenue"
    assert report.contact == "Planning Division"
    assert report.links[0].absolute_url == "https://ceqanet.lci.ca.gov/Documents/2026061234"


def test_parse_ceqanet_detail_page_extracts_colon_delimited_labels() -> None:
    html = """
    <section>
      <h1>CEQAnet Detail</h1>
      <p>Project Name: Riverside Bridge Replacement</p>
      <p>SCH Number: 2024010001</p>
      <p>Lead/Public Agency: Riverside County Transportation Commission</p>
      <p>County: Riverside</p>
      <p>Document Type: Mitigated Negative Declaration</p>
    </section>
    """

    report = parse_ceqanet_detail_page(html)

    assert report.title == "Riverside Bridge Replacement"
    assert report.title_source == "human_label"
    assert report.sch_number == "2024010001"
    assert report.lead_agency == "Riverside County Transportation Commission"
    assert report.county == "Riverside"
    assert report.document_type == "Mitigated Negative Declaration"


def test_parse_ceqanet_detail_page_rejects_adjacent_header_labels_as_values() -> None:
    html = """
    <main>
      <p>Document Type</p>
      <p>Lead/Public Agency</p>
      <p>Received</p>
      <p>Project Title</p>
      <p>San Bernardino Countywide Plan</p>
      <p>SCH Number</p>
      <p>2017101033</p>
      <p>Document Description</p>
      <p>Note: Review Period Per Lead The Project is a comprehensive plan.</p>
    </main>
    """

    report = parse_ceqanet_detail_page(html)

    assert report.title == "San Bernardino Countywide Plan"
    assert report.title_source == "human_label"
    assert report.sch_number == "2017101033"
    assert report.document_type is None
    assert report.lead_agency is None
    assert report.project_description == "Note: Review Period Per Lead The Project is a comprehensive plan."
    assert "document_type" not in report.label_values
    assert "lead_agency" not in report.label_values


def test_parse_ceqanet_detail_page_uses_heading_when_no_title_label_exists() -> None:
    html = """
    <html>
      <head><title>CEQAnet</title></head>
      <body>
        <h1>Redlands Utility Project</h1>
        <p>SCH Number: 2025123456</p>
        <p>County: San Bernardino</p>
      </body>
    </html>
    """

    report = parse_ceqanet_detail_page(html)

    assert report.title == "Redlands Utility Project"
    assert report.title_source == "human_heading"
    assert report.has_human_title is True
    assert report.sch_number == "2025123456"


def test_parse_ceqanet_detail_page_uses_html_title_when_heading_is_not_useful() -> None:
    html = """
    <html>
      <head><title>Ontario Industrial Project - CEQAnet</title></head>
      <body>
        <h1>Project Details</h1>
        <p>SCH Number: 2025012345</p>
      </body>
    </html>
    """

    report = parse_ceqanet_detail_page(html)

    assert report.title == "Ontario Industrial Project"
    assert report.title_source == "html_title"
    assert report.sch_number == "2025012345"


def test_parse_ceqanet_detail_page_marks_sch_only_title() -> None:
    html = """
    <html>
      <body>
        <h1>Project Details</h1>
        <p>SCH Number: 2026060698</p>
      </body>
    </html>
    """

    report = parse_ceqanet_detail_page(
        html,
        source_url="https://ceqanet.lci.ca.gov/Project/2026060698",
    )

    assert report.title == "2026060698"
    assert report.title_source == "sch_number"
    assert report.has_human_title is False
    assert report.sch_number == "2026060698"


def test_parse_ceqanet_detail_page_serializes_report() -> None:
    html = """
    <main>
      <h1>Fontana Warehouse Project</h1>
      <p>SCH Number: 2026061234</p>
    </main>
    """

    payload = parse_ceqanet_detail_page(html).to_dict()

    assert payload["metadata"]["schema_version"] == "ceqanet_detail_page_parse.v1"
    assert payload["metadata"]["has_human_title"] is True
    assert payload["metadata"]["label_count"] >= 1
    assert payload["detail"]["title"] == "Fontana Warehouse Project"
    assert payload["detail"]["title_source"] == "human_heading"
    assert payload["detail"]["sch_number"] == "2026061234"
