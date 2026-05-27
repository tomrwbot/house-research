# Property Links Feature

## Overview

The daily digest now includes clickable links to realestate.com.au property listings, making it easy to access property details directly from the digest.

## Features

### Daily Digest Links

Property listings in the daily digest are formatted as Telegram markdown links:

```
[Address](https://www.realestate.com.au/property-...)
```

When viewed in Telegram or other markdown-aware clients, these appear as clickable links.

**Example digest output:**
```
[1] [Main Road, Ballarat VIC 3350, Australia](https://www.realestate.com.au/property-house-vic-3350-134891235)
    Price: $520,000 AUD | 4BR / 2BA | Amenity Score: 66.0/100
```

### Email Ingestion with URL Preservation

The `ingest_email.py` script automatically:
- Extracts realestate.com.au URLs from email content
- Preserves URLs during property ingestion
- Prevents loss of listing URLs when updating properties
- Validates URLs before storing

## Usage

### Adding URLs to Properties

Properties can have a `url` field in `properties.json`:

```json
{
  "id": "ballarat_001",
  "address": "Sturt Street, Ballarat VIC 3350, Australia",
  "price_aud": 450000,
  "url": "https://www.realestate.com.au/property-house-vic-3350-134891234"
}
```

### Ingesting from Email

```bash
python3 scripts/ingest_email.py \
  --id prop_001 \
  --address "Test Street, Ballarat VIC" \
  --price 450000 \
  --bedrooms 3 \
  --bathrooms 1 \
  --url "https://www.realestate.com.au/property-house-vic-3350-test"
```

With email content extraction:

```bash
python3 scripts/ingest_email.py \
  --id prop_002 \
  --address "New Street, Ballarat VIC" \
  --price 520000 \
  --email-content "Check out: https://www.realestate.com.au/property-house-vic-3350-new"
```

## Implementation Details

### Daily Digest (`scripts/daily_digest.py`)

- Modified `generate_digest()` to extract and format property URLs
- Links are rendered as Telegram markdown: `[address](url)`
- Properties without URLs are displayed as plain text
- Links are preserved in the digest output format

### Email Ingestor (`scripts/ingest_email.py`)

- New `EmailPropertyIngestor` class handles email-based property ingestion
- Extracts URLs using regex pattern: `https?://(?:www\.)?realestate\.com\.au/property-[a-z0-9\-]+`
- Preserves existing URLs when updating properties
- Integrates seamlessly with properties.json workflow

### URL Pattern

The regex pattern matches URLs like:
- `https://www.realestate.com.au/property-house-vic-3350-123456`
- `https://realestate.com.au/property-apartment-nsw-2000-123456`
- Both with and without the `www` prefix

## Testing

All features are covered by comprehensive tests:

### Daily Digest Tests
- URL inclusion in digest output
- Markdown link formatting
- Properties without URLs handled correctly

### Email Ingestion Tests
- URL extraction from email content
- URL preservation during ingestion
- Complete workflow from email to saved properties
- URL regex pattern validation

**Run tests:**
```bash
pytest tests/test_daily_digest.py -v
pytest tests/test_ingest_email.py -v
pytest tests/ -v  # All tests
```

**Example test output:**
```
tests/test_daily_digest.py::TestDigestFormatting::test_digest_includes_property_urls PASSED
tests/test_ingest_email.py::TestEmailPropertyIngestor::test_extract_url_from_content PASSED
tests/test_ingest_email.py::TestURLPreservation::test_url_preserved_through_workflow PASSED
```

## Migration

### For Existing Properties

Add `url` field to existing properties in `properties.json`:

```bash
jq '.properties[] |= . + {"url": null}' properties.json > temp.json
mv temp.json properties.json
```

Then manually add realestate.com.au URLs as properties are found.

### For New Properties

Include the `url` field when adding new properties:

```json
{
  "id": "new_prop",
  "address": "Address, City STATE POSTCODE, Australia",
  "price_aud": 450000,
  "bedrooms": 3,
  "bathrooms": 2,
  "url": "https://www.realestate.com.au/property-..."
}
```

## Future Enhancements

- [ ] Automatic URL lookup based on address and price
- [ ] Multiple listing sources (Domain.com.au, etc.)
- [ ] URL validation via HEAD request
- [ ] URL change tracking in properties.json
- [ ] Scheduled URL verification to catch dead links
