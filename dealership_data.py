import requests
import pandas as pd
import time
import re


# ============================================================
# WIKIDATA CONFIGURATION
# ============================================================

ENDPOINT = "https://query.wikidata.org/sparql"

HEADERS = {
    "User-Agent": (
        "academic-sponsorship-research/1.0 "
        "(contact: your.email@university.edu)"
    )
}


# ============================================================
# RUN WIKIDATA QUERY
# ============================================================

def query_wikidata(query, max_retries=5):

    for attempt in range(max_retries):

        try:

            response = requests.post(
                ENDPOINT,
                data={
                    "query": query,
                    "format": "json"
                },
                headers=HEADERS,
                timeout=90
            )

            if response.status_code == 200:

                data = response.json()

                rows = [
                    {
                        key: value.get("value")
                        for key, value in item.items()
                    }
                    for item in data["results"]["bindings"]
                ]

                return pd.DataFrame(rows)

            if response.status_code in (429, 502, 503, 504):

                wait = 10 * (attempt + 1)

                print(
                    f"Wikidata error {response.status_code}; "
                    f"retry in {wait}s"
                )

                time.sleep(wait)

                continue

            response.raise_for_status()

        except requests.exceptions.RequestException as e:

            if attempt == max_retries - 1:
                raise

            wait = 10 * (attempt + 1)

            print(
                f"{e}; retry in {wait}s"
            )

            time.sleep(wait)

    raise RuntimeError(
        "Wikidata query failed after retries."
    )


# ============================================================
# EXTRACT QID FROM WIKIDATA URL
# ============================================================

def extract_qid(value):

    if pd.isna(value):
        return pd.NA

    match = re.search(
        r"(Q\d+)$",
        str(value)
    )

    return (
        match.group(1)
        if match
        else pd.NA
    )


# ============================================================
# GENERAL SPONSORSHIP QUERY
#
# Important:
# sport is OPTIONAL.
#
# We do NOT require ?entity wdt:P641 ?sport,
# otherwise valid sponsorship relationships could disappear.
# ============================================================

def make_query(
    property_id,
    limit=2000,
    offset=0
):

    return f"""
    PREFIX wdt:  <http://www.wikidata.org/prop/direct/>
    PREFIX p:    <http://www.wikidata.org/prop/>
    PREFIX ps:   <http://www.wikidata.org/prop/statement/>
    PREFIX pq:   <http://www.wikidata.org/prop/qualifier/>
    PREFIX prov: <http://www.w3.org/ns/prov#>
    PREFIX pr:   <http://www.wikidata.org/prop/reference/>

    SELECT DISTINCT
        ?entity
        ?statement
        ?sponsor
        ?sport
        ?startDate
        ?endDate
        ?referenceURL
    WHERE {{

        ?entity p:{property_id} ?statement .

        ?statement
            ps:{property_id}
            ?sponsor .

        OPTIONAL {{
            ?entity
                wdt:P641
                ?sport .
        }}

        OPTIONAL {{
            ?statement
                pq:P580
                ?startDate .
        }}

        OPTIONAL {{
            ?statement
                pq:P582
                ?endDate .
        }}

        OPTIONAL {{

            ?statement
                prov:wasDerivedFrom
                ?reference .

            ?reference
                pr:P854
                ?referenceURL .
        }}
    }}

    LIMIT {limit}
    OFFSET {offset}
    """


# ============================================================
# DOWNLOAD ONE RELATIONSHIP TYPE
# ============================================================

def download_relationship(
    property_id,
    relationship,
    chunk_size=2000,
    max_rows=10000
):

    chunks = []

    offset = 0

    while offset < max_rows:

        print(
            f"{relationship}: rows "
            f"{offset:,} - "
            f"{offset + chunk_size - 1:,}"
        )

        query = make_query(
            property_id=property_id,
            limit=chunk_size,
            offset=offset
        )

        chunk = query_wikidata(
            query
        )

        if chunk.empty:
            break

        chunk["relationship"] = relationship

        chunks.append(
            chunk
        )

        print(
            "  received:",
            len(chunk)
        )

        if len(chunk) < chunk_size:
            break

        offset += chunk_size

        time.sleep(3)

    if not chunks:

        return pd.DataFrame()

    return pd.concat(
        chunks,
        ignore_index=True
    )


# ============================================================
# 1. STANDARD SPONSORS
# P859 = sponsor
# ============================================================

df_sponsor = download_relationship(
    property_id="P859",
    relationship="sponsor",
    chunk_size=2000
)

print(
    "\nP859:",
    df_sponsor.shape
)


# ============================================================
# 2. KIT / EQUIPMENT SUPPLIERS
# P5995 = kit supplier
# ============================================================

df_kit = download_relationship(
    property_id="P5995",
    relationship="kit_supplier",
    chunk_size=2000
)

print(
    "\nP5995:",
    df_kit.shape
)


# ============================================================
# COMBINE
# ============================================================

df = pd.concat(
    [
        df_sponsor,
        df_kit
    ],
    ignore_index=True
)

df = (
    df
    .drop_duplicates()
    .reset_index(drop=True)
)

print(
    "\nCombined:",
    df.shape
)


# ============================================================
# CREATE QIDS CORRECTLY
# ============================================================

df["entity_qid"] = (
    df["entity"]
    .apply(extract_qid)
)

df["sponsor_qid"] = (
    df["sponsor"]
    .apply(extract_qid)
)

if "sport" in df.columns:

    df["sport_qid"] = (
        df["sport"]
        .apply(extract_qid)
    )

else:

    df["sport_qid"] = pd.NA


# ============================================================
# DATES
# ============================================================

for col in [
    "startDate",
    "endDate"
]:

    if col in df.columns:

        df[col] = pd.to_datetime(
            df[col],
            errors="coerce",
            utc=True
        )


# ============================================================
# SAVE RAW SPONSORSHIP DATA
# ============================================================

df.to_csv(
    "wikidata_sponsorships.csv",
    index=False,
    encoding="utf-8-sig"
)

print(
    "\nSaved:",
    "wikidata_sponsorships.csv"
)


# ============================================================
# BASIC CHECK
# ============================================================

print(
    "\nRelationship counts:"
)

print(
    df[
        "relationship"
    ].value_counts(
        dropna=False
    )
)


# ============================================================
# ============================================================
# TEST CASE:
# CRISTIANO RONALDO -> NIKE
#
# Cristiano Ronaldo = Q11571
# Nike              = Q483915
# ============================================================
# ============================================================

ronaldo_query = """
PREFIX wd:       <http://www.wikidata.org/entity/>
PREFIX p:        <http://www.wikidata.org/prop/>
PREFIX ps:       <http://www.wikidata.org/prop/statement/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd:       <http://www.bigdata.com/rdf#>

SELECT
    ?entity
    ?entityLabel
    ?sponsor
    ?sponsorLabel
WHERE {

    VALUES ?entity {
        wd:Q11571
    }

    ?entity
        p:P859
        ?statement .

    ?statement
        ps:P859
        ?sponsor .

    SERVICE wikibase:label {
        bd:serviceParam
            wikibase:language
            "en" .
    }
}
"""


ronaldo = query_wikidata(
    ronaldo_query
)


# ============================================================
# CREATE RONALDO / SPONSOR QIDS
# ============================================================

ronaldo["entity_qid"] = (
    ronaldo["entity"]
    .apply(extract_qid)
)

ronaldo["sponsor_qid"] = (
    ronaldo["sponsor"]
    .apply(extract_qid)
)


# ============================================================
# FINAL CLEAN EXAMPLE
# ============================================================

ronaldo_example = (
    ronaldo[
        [
            "entityLabel",
            "entity_qid",
            "sponsorLabel",
            "sponsor_qid"
        ]
    ]
    .drop_duplicates()
    .reset_index(drop=True)
)


print(
    "\n"
    "========================================\n"
    "CRISTIANO RONALDO SPONSORSHIP EXAMPLE\n"
    "========================================"
)

print(
    ronaldo_example.to_string(
        index=False
    )
)