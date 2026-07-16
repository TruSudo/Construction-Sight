from constructionsight.adapters.ceqanet_search_contract import (
    CEQANET_FIELD_CITY,
    CEQANET_FIELD_COUNTY,
    CEQANET_FIELD_DOCUMENT_TYPE,
    CEQANET_FIELD_LEAD_AGENCY,
    CEQANET_FIELD_REGION,
)
from constructionsight.adapters.ceqanet_search_vocabulary import (
    classify_ceqanet_lead_agency,
    parse_ceqanet_search_vocabulary,
)


def test_parse_ceqanet_search_vocabulary_extracts_contract_select_options() -> None:
    html = """
    <html>
      <body>
        <select name="DocumentType">
          <option value="">(Any)</option>
          <option>EIR - Draft EIR</option>
          <option value="NOP - Notice of Preparation of a Draft EIR">
            NOP - Notice of Preparation of a Draft EIR
          </option>
        </select>
        <select id="LeadAgency" name="LeadAgency">
          <option value="">(Any)</option>
          <option selected>Redlands, City of</option>
          <option>San Bernardino County Transportation Authority</option>
        </select>
        <select name="County">
          <option>San Bernardino</option>
          <option>Riverside</option>
        </select>
      </body>
    </html>
    """

    vocabulary = parse_ceqanet_search_vocabulary(html)

    document_types = vocabulary.group(CEQANET_FIELD_DOCUMENT_TYPE)
    assert document_types.values == (
        "",
        "EIR - Draft EIR",
        "NOP - Notice of Preparation of a Draft EIR",
    )
    assert document_types.labels == (
        "(Any)",
        "EIR - Draft EIR",
        "NOP - Notice of Preparation of a Draft EIR",
    )

    lead_agencies = vocabulary.group(CEQANET_FIELD_LEAD_AGENCY)
    assert lead_agencies.options[1].label == "Redlands, City of"
    assert lead_agencies.options[1].value == "Redlands, City of"
    assert lead_agencies.options[1].selected is True

    counties = vocabulary.group(CEQANET_FIELD_COUNTY)
    assert counties.values == ("San Bernardino", "Riverside")


def test_parse_ceqanet_search_vocabulary_ignores_uncontracted_selects() -> None:
    html = """
    <select name="Unrelated">
      <option>Ignore Me</option>
    </select>
    <select name="City">
      <option>Ontario</option>
      <option>Rancho Cucamonga</option>
    </select>
    """

    vocabulary = parse_ceqanet_search_vocabulary(html)

    assert vocabulary.has_group(CEQANET_FIELD_CITY) is True
    assert vocabulary.group(CEQANET_FIELD_CITY).values == (
        "Ontario",
        "Rancho Cucamonga",
    )
    assert vocabulary.has_group("Unrelated") is False

def test_parse_ceqanet_search_vocabulary_handles_unclosed_options_and_label_attrs() -> None:
    html = """
    <select name="Region">
      <option value="1" label="Southern California">
      <option>Inland Empire</option>
    </select>
    """

    vocabulary = parse_ceqanet_search_vocabulary(html)

    regions = vocabulary.group(CEQANET_FIELD_REGION)
    assert [(option.label, option.value) for option in regions.options] == [
        ("Southern California", "1"),
        ("Inland Empire", "Inland Empire"),
    ]


def test_parse_ceqanet_search_vocabulary_returns_json_safe_dict() -> None:
    html = """
    <select name="DocumentType">
      <option value="">(Any)</option>
      <option>MND - Mitigated Negative Declaration</option>
    </select>
    """

    vocabulary = parse_ceqanet_search_vocabulary(html)

    assert vocabulary.to_dict() == {
        CEQANET_FIELD_DOCUMENT_TYPE: [
            {
                "field_name": CEQANET_FIELD_DOCUMENT_TYPE,
                "label": "(Any)",
                "value": "",
                "selected": False,
            },
            {
                "field_name": CEQANET_FIELD_DOCUMENT_TYPE,
                "label": "MND - Mitigated Negative Declaration",
                "value": "MND - Mitigated Negative Declaration",
                "selected": False,
            },
        ]
    }


def test_classify_ceqanet_lead_agency_identifies_practical_source_types() -> None:
    assert classify_ceqanet_lead_agency("Redlands, City of") == "city"
    assert classify_ceqanet_lead_agency("San Bernardino County") == "county"

    assert (
        classify_ceqanet_lead_agency("San Bernardino City Unified School District")
        == "school_district"
    )
    assert (
        classify_ceqanet_lead_agency("Riverside County Transportation Commission")
        == "transportation_agency"
    )
    assert (
        classify_ceqanet_lead_agency("San Bernardino County Local Agency Formation Commission")
        == "lafco"
    )
    assert classify_ceqanet_lead_agency("Orange County Water District") == "special_district"
    assert classify_ceqanet_lead_agency("Sanitation District No. 2") == "sanitation_wastewater"
    assert classify_ceqanet_lead_agency("ACE Charter School") == "charter_school"
    assert classify_ceqanet_lead_agency("Air Resources Board (ARB)") == "air_quality_agency"
