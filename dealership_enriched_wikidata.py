import pandas as pd
import re
import time


# ============================================================
# 1. FUNCTION: GET WIKIDATA LABELS FROM QIDS
# ============================================================

def get_wikidata_labels(qids, chunk_size=200):

    qids = (
        pd.Series(qids)
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    # Keep only valid Wikidata QIDs
    qids = [
        qid
        for qid in qids
        if re.fullmatch(r"Q\d+", qid)
    ]

    results = []

    for i in range(0, len(qids), chunk_size):

        chunk = qids[i:i + chunk_size]

        values = " ".join(
            f"wd:{qid}"
            for qid in chunk
        )

        query = f"""
        PREFIX wd:       <http://www.wikidata.org/entity/>
        PREFIX wikibase: <http://wikiba.se/ontology#>
        PREFIX bd:       <http://www.bigdata.com/rdf#>

        SELECT
            ?item
            ?itemLabel
        WHERE {{

            VALUES ?item {{
                {values}
            }}

            SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "en,fr" .
            }}
        }}
        """

        tmp = query_wikidata(query)

        if not tmp.empty:
            results.append(tmp)

        time.sleep(1)

    if not results:
        return pd.DataFrame(
            columns=[
                "qid",
                "label"
            ]
        )

    labels = pd.concat(
        results,
        ignore_index=True
    )

    labels["qid"] = (
        labels["item"]
        .str.extract(r"(Q\d+)$")[0]
    )

    labels = (
        labels[
            [
                "qid",
                "itemLabel"
            ]
        ]
        .rename(
            columns={
                "itemLabel": "label"
            }
        )
        .drop_duplicates(
            subset="qid"
        )
        .reset_index(drop=True)
    )

    return labels


# ============================================================
# 2. FUNCTION: GET SPORTS ASSOCIATED WITH ENTITIES
#
# P641 = sport
# ============================================================

def get_entity_sports(entity_qids, chunk_size=200):

    entity_qids = (
        pd.Series(entity_qids)
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
    )

    entity_qids = [
        qid
        for qid in entity_qids
        if re.fullmatch(r"Q\d+", qid)
    ]

    results = []

    for i in range(0, len(entity_qids), chunk_size):

        chunk = entity_qids[
            i:i + chunk_size
        ]

        values = " ".join(
            f"wd:{qid}"
            for qid in chunk
        )

        query = f"""
        PREFIX wd:       <http://www.wikidata.org/entity/>
        PREFIX wdt:      <http://www.wikidata.org/prop/direct/>
        PREFIX wikibase: <http://wikiba.se/ontology#>
        PREFIX bd:       <http://www.bigdata.com/rdf#>

        SELECT DISTINCT
            ?entity
            ?entityLabel
            ?sport
            ?sportLabel
        WHERE {{

            VALUES ?entity {{
                {values}
            }}

            OPTIONAL {{
                ?entity wdt:P641 ?sport .
            }}

            SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "en,fr" .
            }}
        }}
        """

        tmp = query_wikidata(query)

        if not tmp.empty:
            results.append(tmp)

        time.sleep(1)

    if not results:
        return pd.DataFrame(
            columns=[
                "entity_qid",
                "entityLabel",
                "sport_qid",
                "sportLabel"
            ]
        )

    sports = pd.concat(
        results,
        ignore_index=True
    )

    sports["entity_qid"] = (
        sports["entity"]
        .str.extract(r"(Q\d+)$")[0]
    )

    if "sport" in sports.columns:

        sports["sport_qid"] = (
            sports["sport"]
            .str.extract(r"(Q\d+)$")[0]
        )

    else:

        sports["sport_qid"] = pd.NA

    keep_cols = [
        "entity_qid",
        "entityLabel",
        "sport_qid",
        "sportLabel"
    ]

    for col in keep_cols:

        if col not in sports.columns:
            sports[col] = pd.NA

    sports = (
        sports[
            keep_cols
        ]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    return sports


# ============================================================
# 3. GET LABELS OF ALL ENTITIES
# ============================================================

entity_labels = get_wikidata_labels(
    df["entity_qid"]
)

entity_labels = entity_labels.rename(
    columns={
        "qid": "entity_qid",
        "label": "entityLabel"
    }
)


# ============================================================
# 4. GET LABELS OF SPONSORS / KIT SUPPLIERS
#
# sponsor_qid contains the counterpart:
#
# relationship == sponsor
#     -> sponsor
#
# relationship == kit_supplier
#     -> kit supplier
# ============================================================

partner_labels = get_wikidata_labels(
    df["sponsor_qid"]
)

partner_labels = partner_labels.rename(
    columns={
        "qid": "sponsor_qid",
        "label": "partnerLabel"
    }
)


# ============================================================
# 5. MERGE ENTITY AND SPONSOR/KIT-SUPPLIER LABELS
# ============================================================

df_named = (
    df
    .merge(
        entity_labels,
        on="entity_qid",
        how="left"
    )
    .merge(
        partner_labels,
        on="sponsor_qid",
        how="left"
    )
)


# ============================================================
# 6. CREATE DISTINCT SPONSOR / KIT SUPPLIER NAME COLUMNS
# ============================================================

df_named["sponsorLabel"] = (
    df_named["partnerLabel"]
    .where(
        df_named["relationship"]
        .eq("sponsor")
    )
)

df_named["kit_supplierLabel"] = (
    df_named["partnerLabel"]
    .where(
        df_named["relationship"]
        .eq("kit_supplier")
    )
)


# ============================================================
# 7. SEARCH SPORTS ASSOCIATED WITH EACH ENTITY
# ============================================================

entity_sports = get_entity_sports(
    df_named["entity_qid"]
)


# ============================================================
# 8. MERGE SPORTS BACK INTO SPONSORSHIP DATA
#
# One entity can have several sports, therefore this merge can
# generate several rows for the same sponsorship relationship.
# ============================================================

df_final = (
    df_named
    .drop(
        columns=[
            "sport",
            "sport_qid"
        ],
        errors="ignore"
    )
    .merge(
        entity_sports,
        on=[
            "entity_qid",
            "entityLabel"
        ],
        how="left"
    )
)


# ============================================================
# 9. CLEAN FINAL TABLE
# ============================================================

cols_final = [
    "entityLabel",
    "entity_qid",

    "relationship",

    "partnerLabel",
    "sponsor_qid",

    "sponsorLabel",
    "kit_supplierLabel",

    "sportLabel",
    "sport_qid",

    "startDate",
    "endDate",
    "referenceURL"
]

df_final = df_final[
    [
        col
        for col in cols_final
        if col in df_final.columns
    ]
].drop_duplicates().reset_index(drop=True)


# ============================================================
# 10. DISPLAY
# ============================================================

print(
    df_final.head(30).to_string(
        index=False
    )
)


# ============================================================
# 11. LIONEL MESSI EXAMPLE
# ============================================================

messi = (
    df_final[
        df_final["entity_qid"]
        .eq("Q615")
    ]
    .copy()
)

print(
    "\n"
    "==========================================\n"
    "LIONEL MESSI\n"
    "=========================================="
)

print(
    messi[
        [
            col
            for col in [
                "entityLabel",
                "entity_qid",
                "relationship",
                "partnerLabel",
                "sponsor_qid",
                "sportLabel",
                "sport_qid"
            ]
            if col in messi.columns
        ]
    ].to_string(
        index=False
    )
)


# ============================================================
# 12. OPTIONAL: ONE VERY CLEAN DISPLAY
# ============================================================

messi_clean = (
    messi[
        [
            "entityLabel",
            "entity_qid",
            "partnerLabel",
            "sponsor_qid",
            "relationship",
            "sportLabel",
            "sport_qid"
        ]
    ]
    .drop_duplicates()
)

print(
    "\nClean Ronaldo example:"
)

print(
    messi_clean.to_string(
        index=False
    )
)


# ============================================================
# 13. SAVE
# ============================================================

df_final.to_csv(
    "wikidata_sponsorships_with_names_and_sports.csv",
    index=False,
    encoding="utf-8-sig"
)