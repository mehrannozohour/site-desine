# Google Places business assistant

This small Python CLI searches Google Places for one or more queries and exports business contact data to CSV.

## What it exports

- business name
- phone number
- website
- address
- Google Maps URL
- rating and review count
- business status and types

## Setup

1. Create a Google Places API key in your own Google Cloud account.
2. Copy `.env.example` to `.env` or set `GOOGLE_PLACES_API_KEY` in your shell.
3. Run the script with one or more queries.

## Example

```bash
python places_assistant.py --query "dentist in Tehran" --query "restaurant in Shiraz" --output businesses.csv
```

## Notes

- The script uses Google Places Web Service, not browser scraping.
- It cannot create or obtain an API key for you.
- Results depend on the query and on what Google returns through the API.
