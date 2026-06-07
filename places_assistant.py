#!/usr/bin/env python3
"""Search Google Places and export business contact data to CSV.

This script uses the Google Places Web Service with a user-provided API key.
It searches for businesses matching one or more queries and exports the
results with phone number, website, address, rating, and a Google Maps link.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Iterable


PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
CSV_COLUMNS = [
    "query",
    "name",
    "phone",
    "website",
    "address",
    "maps_url",
    "rating",
    "reviews",
    "business_status",
    "types",
    "place_id",
]


@dataclass
class BusinessRecord:
    query: str
    name: str
    phone: str
    website: str
    address: str
    maps_url: str
    rating: str
    reviews: str
    business_status: str
    types: str
    place_id: str


def build_request(url: str, params: dict[str, str]) -> urllib.request.Request:
    query_string = urllib.parse.urlencode(params)
    return urllib.request.Request(f"{url}?{query_string}", headers={"User-Agent": "Mozilla/5.0"})


def fetch_json(url: str, params: dict[str, str]) -> dict:
    request = build_request(url, params)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def get_api_key(explicit_key: str | None) -> str:
    api_key = explicit_key or os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(
            "Missing GOOGLE_PLACES_API_KEY. Set it in your environment before running the script."
        )
    return api_key


def text_search(api_key: str, query: str, language: str, region: str, max_results: int) -> list[dict]:
    results: list[dict] = []
    page_token: str | None = None

    while True:
        params = {
            "key": api_key,
            "query": query,
            "language": language,
            "region": region,
        }
        if page_token:
            params["pagetoken"] = page_token

        payload = fetch_json(PLACES_TEXT_SEARCH_URL, params)
        status = payload.get("status", "")

        if status not in {"OK", "ZERO_RESULTS", "INVALID_REQUEST"}:
            message = payload.get("error_message", status)
            raise RuntimeError(f"Text search failed for {query!r}: {message}")

        results.extend(payload.get("results", []))
        if len(results) >= max_results:
            return results[:max_results]

        page_token = payload.get("next_page_token")
        if not page_token:
            return results

        time.sleep(2)


def place_details(api_key: str, place_id: str, language: str) -> dict:
    params = {
        "key": api_key,
        "place_id": place_id,
        "fields": "name,formatted_address,formatted_phone_number,international_phone_number,website,url,business_status,rating,user_ratings_total,types",
        "language": language,
    }
    payload = fetch_json(PLACES_DETAILS_URL, params)
    status = payload.get("status", "")
    if status not in {"OK", "ZERO_RESULTS"}:
        message = payload.get("error_message", status)
        raise RuntimeError(f"Place details failed for {place_id!r}: {message}")
    return payload.get("result", {})


def normalize_phone(details: dict) -> str:
    return details.get("international_phone_number") or details.get("formatted_phone_number") or ""


def to_record(query: str, place_summary: dict, details: dict) -> BusinessRecord:
    maps_url = details.get("url") or f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(place_summary.get('name', ''))}&query_place_id={urllib.parse.quote(place_summary.get('place_id', ''))}"
    return BusinessRecord(
        query=query,
        name=details.get("name") or place_summary.get("name", ""),
        phone=normalize_phone(details),
        website=details.get("website", ""),
        address=details.get("formatted_address") or place_summary.get("formatted_address", ""),
        maps_url=maps_url,
        rating=str(details.get("rating", place_summary.get("rating", "")) or ""),
        reviews=str(details.get("user_ratings_total", place_summary.get("user_ratings_total", "")) or ""),
        business_status=details.get("business_status", ""),
        types=";".join(details.get("types", place_summary.get("types", [])) or []),
        place_id=place_summary.get("place_id", ""),
    )


def search_businesses(
    api_key: str,
    query: str,
    language: str,
    region: str,
    max_results: int,
) -> list[BusinessRecord]:
    summaries = text_search(api_key, query, language, region, max_results)
    records: list[BusinessRecord] = []
    seen_place_ids: set[str] = set()

    for summary in summaries:
        place_id = summary.get("place_id", "")
        if not place_id or place_id in seen_place_ids:
            continue
        seen_place_ids.add(place_id)

        details = place_details(api_key, place_id, language)
        records.append(to_record(query, summary, details))

    return records


def load_queries(path: str | None, inline_queries: list[str]) -> list[str]:
    if inline_queries:
        return inline_queries
    if not path:
        return []
    with open(path, "r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]


def write_csv(records: Iterable[BusinessRecord], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search Google Places and export businesses with phone numbers and websites."
    )
    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help="Search query to run. Repeat for multiple queries.",
    )
    parser.add_argument(
        "--queries-file",
        help="Optional text file with one query per line.",
    )
    parser.add_argument(
        "--output",
        default="businesses.csv",
        help="CSV output path.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=60,
        help="Maximum results per query.",
    )
    parser.add_argument(
        "--language",
        default="fa",
        help="Places API language code.",
    )
    parser.add_argument(
        "--region",
        default="ir",
        help="Places API region code.",
    )
    parser.add_argument(
        "--api-key",
        help="Google Places API key. If omitted, reads GOOGLE_PLACES_API_KEY.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    api_key = get_api_key(args.api_key)
    queries = load_queries(args.queries_file, args.query)

    if not queries:
        print("Provide at least one --query or --queries-file.", file=sys.stderr)
        return 2

    all_records: list[BusinessRecord] = []
    seen: set[tuple[str, str]] = set()

    for query in queries:
        print(f"Searching: {query}")
        try:
            records = search_businesses(api_key, query, args.language, args.region, args.max_results)
        except Exception as exc:
            print(f"Skipping {query!r}: {exc}", file=sys.stderr)
            continue

        for record in records:
            key = (record.query, record.place_id)
            if key in seen:
                continue
            seen.add(key)
            all_records.append(record)

    if not all_records:
        print("No records found.", file=sys.stderr)
        return 1

    write_csv(all_records, args.output)
    print(f"Wrote {len(all_records)} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
