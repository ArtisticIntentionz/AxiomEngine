"""Discovery SEC - Fetch financial facts from the SEC EDGAR database."""

import logging

from sec_edgar_api import EdgarClient

# --- IMPORTANT: REPLACE WITH YOUR USER AGENT ---
# Example: "John Doe MyAxiomNode/1.0 (john.doe@email.com)"
USER_AGENT = (
    "AxiomNetwork Research AxiomServer/0.5 (victornevarez88@gmail.com)"
)

logger = logging.getLogger(__name__)


def get_financial_facts_from_edgar(max_filings: int = 10) -> list[dict]:
    """Fetches the latest 10-Q filings from the SEC EDGAR database and extracts
    key financial data (Revenue, Net Income) as objective facts.
    """
    if not USER_AGENT or "YourName" in USER_AGENT:
        logger.warning(
            "SEC EDGAR agent is not configured with a proper User-Agent. Skipping.",
        )
        return []

    logger.info("Discovering financial facts from SEC EDGAR...")
    try:
        edgar_client = EdgarClient(user_agent=USER_AGENT)
        # Some versions of sec_edgar_api do not expose get_filings().
        # Gracefully detect and skip if unavailable rather than erroring every cycle.
        if not hasattr(edgar_client, "get_filings"):
            logger.warning(
                "SEC EDGAR client does not support get_filings(). Skipping SEC ingestion.",
            )
            return []
        # Use the get_filings() method to get recent filings of a specific type
        recent_filings = edgar_client.get_filings(form_type="10-Q")
    except Exception as e:
        logger.error(f"Failed to fetch recent filings from SEC EDGAR: {e}")
        return []

    extracted_facts = []
    processed_tickers = set()

    for filing in recent_filings[
        : max_filings * 5
    ]:  # Fetch more to find enough with data
        if len(extracted_facts) >= max_filings:
            break

        ticker = filing.get("ticker")
        if not ticker or ticker in processed_tickers:
            continue

        try:
            # Get the specific facts from the filing's XBRL data
            if not hasattr(edgar_client, "get_facts"):
                logger.debug(
                    "SEC EDGAR client has no get_facts(); skipping details for %s",
                    ticker,
                )
                continue
            facts = edgar_client.get_facts(ticker=ticker)
            company_name = facts.get("entityName", ticker)

            # Look for US GAAP standard fields for Revenue and Net Income
            revenue_data = facts["us-gaap"].get("Revenues", [{}])[0]
            net_income_data = facts["us-gaap"].get("NetIncomeLoss", [{}])[0]

            if "val" in revenue_data and "val" in net_income_data:
                # Find the most recent value for the quarter
                revenue_value = int(revenue_data["val"])
                net_income_value = int(net_income_data["val"])
                period_end_date = revenue_data.get("end")

                if not period_end_date:
                    continue

                # Format the extracted data into objective, verifiable fact statements
                revenue_fact = (
                    f"{company_name} ({ticker}) reported total revenue of ${revenue_value:,} "
                    f"for the quarter ending {period_end_date}."
                )
                net_income_fact = (
                    f"{company_name} ({ticker}) reported a net income of ${net_income_value:,} "
                    f"for the quarter ending {period_end_date}."
                )

                source_url = (
                    f"https://www.sec.gov/edgar/browse/?CIK={filing['cik']}"
                )

                extracted_facts.append(
                    {"content": revenue_fact, "source_url": source_url},
                )
                extracted_facts.append(
                    {"content": net_income_fact, "source_url": source_url},
                )

                processed_tickers.add(ticker)
                logger.info(f"Extracted financial facts for {ticker}.")

        except Exception:
            # This is common if a filing doesn't use standard GAAP tags
            logger.debug(
                f"Could not extract standard financial facts for {ticker}. Skipping.",
            )
            continue

    logger.info(
        f"Successfully extracted {len(extracted_facts)} financial facts from SEC EDGAR.",
    )
    return extracted_facts
