from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAlexIngestionResult:
    """Summary of one OpenAlex ingestion run.

    Attributes:
        query: Search query used to fetch OpenAlex records.
        staged_records: Number of raw records staged with dlt.
        inserted_articles: Number of articles inserted into application stores.
        dlt_output_dir: Local directory used by the dlt filesystem destination.
        dlt_load_info: String representation of dlt load metadata.
    """

    query: str
    staged_records: int
    inserted_articles: int
    dlt_output_dir: str
    dlt_load_info: str
