# Parcel Row Preview

Parcel row preview is the safety gate after parcel source schema preview and before `ParcelRecord` creation.

It previews candidate parcel rows from a lawful source fixture, file sample, API sample, or future provider response. It does not persist parcel records.

## Core rule

Do not create parcel records until rows have passed basic source checks.

The preview must answer:

```text
Do mapped APN and county fields exist?
Does each sample row contain APN and county values?
Can APNs be normalized?
Can addresses be normalized when present?
Is geometry present when mapped?
Which rows need review?
```

## Preview output

The report includes:

- source key
- source format
- row count
- usable row count
- skipped row count
- mapped roles
- row-level normalized APN
- row-level normalized address
- county
- source record ID
- geometry-present flag
- limitations
- next action

## Statuses

Parcel row preview can return:

- `ready_for_parcel_record_model`
- `needs_schema_mapping`
- `row_issues`
- `empty_source`

## CLI

```bash
constructionsight-parcel-sources preview-rows --input row-preview.json
constructionsight-parcel-sources preview-rows --input row-preview.json --json-output
```

File output requires `--json-output`.

## Next phase

After a row preview is clean, ConstructionSight can build the actual `ParcelRecord` and geometry-normalization layer.
