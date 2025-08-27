"""Discovery SEC - Fetch financial facts from the SEC EDGAR database."""

import logging
from typing import Any

import requests

# --- IMPORTANT: REPLACE WITH YOUR USER AGENT ---
# Example: "John Doe MyAxiomNode/1.0 (john.doe@email.com)"
USER_AGENT = (
    "AxiomNetwork Research AxiomServer/0.5 (victornevarez88@gmail.com)"
)

logger = logging.getLogger(__name__)


def get_financial_facts_from_edgar(
    max_filings: int = 10,
) -> list[dict[str, Any]]:
    """Fetch the latest 10-Q filings from the SEC EDGAR database.

    This function extracts key financial data (Revenue, Net Income) as
    objective facts.
    """
    if not USER_AGENT or "YourName" in USER_AGENT:
        logger.warning(
            "SEC EDGAR agent is not configured with a proper User-Agent. Skipping.",
        )
        return []

    logger.info("Discovering financial facts from SEC EDGAR...")

    try:
        # Try the modern approach first
        facts = get_facts_modern_approach(max_filings)
        if facts:
            return facts

        # Fallback to basic approach
        logger.info("Modern approach failed, trying basic SEC EDGAR access...")
        return get_facts_basic_approach(max_filings)

    except Exception as e:
        logger.error(f"Failed to fetch financial facts from SEC EDGAR: {e}")
        return []


def get_facts_modern_approach(max_filings: int) -> list[dict[str, Any]]:
    """Try to use the modern sec_edgar_api approach."""
    try:
        from sec_edgar_api import EdgarClient

        edgar_client = EdgarClient(user_agent=USER_AGENT)

        # Check what methods are available
        available_methods = [
            method
            for method in dir(edgar_client)
            if not method.startswith("_")
        ]
        logger.info(f"Available SEC EDGAR methods: {available_methods}")

        # Try different approaches based on available methods
        if hasattr(edgar_client, "get_company_facts"):
            return get_facts_with_company_facts(edgar_client, max_filings)
        if hasattr(edgar_client, "get_company_concept"):
            return get_facts_with_company_concept(edgar_client, max_filings)
        if hasattr(edgar_client, "get_filings"):
            return get_facts_with_get_filings(edgar_client, max_filings)
        if hasattr(edgar_client, "get_facts"):
            return get_facts_with_get_facts(edgar_client, max_filings)
        logger.warning(
            "SEC EDGAR client has no known fact retrieval methods.",
        )
        return []

    except ImportError:
        logger.warning(
            "sec_edgar_api not available. Install with: pip install sec-edgar-api",
        )
        return []
    except Exception as e:
        logger.error(f"Modern SEC EDGAR approach failed: {e}")
        return []


def get_facts_with_get_filings(
    edgar_client: Any,
    max_filings: int,
) -> list[dict[str, Any]]:
    """Use get_filings() method if available."""
    try:
        recent_filings = edgar_client.get_filings(form_type="10-Q")
        return process_filings(recent_filings, max_filings)
    except Exception as e:
        logger.error(f"get_filings() approach failed: {e}")
        return []


def get_facts_with_company_facts(
    edgar_client: Any,
    max_filings: int,
) -> list[dict[str, Any]]:
    """Use get_company_facts() method if available."""
    try:
        # Get facts for major companies
        major_companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        facts = []

        for ticker in major_companies[: max_filings // 2]:
            try:
                logger.info(f"Fetching company facts for {ticker}...")
                company_facts = edgar_client.get_company_facts(ticker)
                if company_facts:
                    extracted = extract_financial_facts_from_company(
                        ticker,
                        company_facts,
                    )
                    facts.extend(extracted)
                    logger.info(
                        f"Successfully extracted {len(extracted)} facts for {ticker}",
                    )
                else:
                    logger.debug(f"No company facts returned for {ticker}")
            except Exception as e:
                logger.debug(f"Could not get facts for {ticker}: {e}")
                continue

        return facts
    except Exception as e:
        logger.error(f"get_company_facts() approach failed: {e}")
        return []


def get_facts_with_company_concept(
    edgar_client: Any,
    max_filings: int,
) -> list[dict[str, Any]]:
    """Use get_company_concept() method to get specific financial metrics."""
    try:
        # Get facts for major companies with specific financial concepts
        major_companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        financial_concepts = [
            "Revenues",
            "NetIncomeLoss",
            "Assets",
            "Liabilities",
        ]
        facts = []

        for ticker in major_companies[: max_filings // 2]:
            for concept in financial_concepts:
                try:
                    logger.info(f"Fetching {concept} for {ticker}...")
                    concept_data = edgar_client.get_company_concept(
                        ticker,
                        concept,
                    )
                    if concept_data and concept_data.get("units"):
                        extracted = extract_concept_facts(
                            ticker,
                            concept,
                            concept_data,
                        )
                        facts.extend(extracted)
                        logger.info(
                            f"Successfully extracted {concept} data for {ticker}",
                        )
                except Exception as e:
                    logger.debug(f"Could not get {concept} for {ticker}: {e}")
                    continue

        return facts
    except Exception as e:
        logger.error(f"get_company_concept() approach failed: {e}")
        return []


def get_facts_with_get_facts(
    edgar_client: Any,
    max_filings: int,
) -> list[dict[str, Any]]:
    """Use get_facts() method if available."""
    try:
        # Get facts for major companies
        major_companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        facts = []

        for ticker in major_companies[: max_filings // 2]:
            try:
                company_facts = edgar_client.get_facts(ticker=ticker)
                if company_facts:
                    extracted = extract_financial_facts_from_company(
                        ticker,
                        company_facts,
                    )
                    facts.extend(extracted)
            except Exception as e:
                logger.debug(f"Could not get facts for {ticker}: {e}")
                continue

        return facts
    except Exception as e:
        logger.error(f"get_facts() approach failed: {e}")
        return []


def get_facts_basic_approach(max_filings: int) -> list[dict[str, Any]]:
    """Fallback approach using direct SEC EDGAR API calls."""
    try:
        # Use direct SEC EDGAR API
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        # Get recent submissions for major companies
        major_companies = [
            ("0000320193", "Apple Inc."),
            ("0001018724", "Amazon.com Inc."),
            ("0001652044", "Alphabet Inc."),
            ("0000789019", "Microsoft Corporation"),
            ("0001318605", "Tesla Inc."),
        ]

        facts = []

        for cik, company_name in major_companies[: max_filings // 2]:
            try:
                url = f"https://data.sec.gov/submissions/CIK{cik}.json"
                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    response.json()

                    # Create basic fact about the company
                    fact = {
                        "content": f"{company_name} (CIK: {cik}) is a publicly traded company registered with the SEC.",
                        "source_url": f"https://www.sec.gov/edgar/browse/?CIK={cik}",
                    }
                    facts.append(fact)

                    logger.info(f"Extracted basic fact for {company_name}")

                    if len(facts) >= max_filings:
                        break

            except Exception as e:
                logger.debug(f"Could not get data for CIK {cik}: {e}")
                continue

        return facts

    except Exception as e:
        logger.error(f"Basic SEC EDGAR approach failed: {e}")
        return []


def process_filings(
    filings: list[dict[str, Any]],
    max_filings: int,
) -> list[dict[str, Any]]:
    """Process filings to extract financial facts."""
    extracted_facts: list[dict[str, Any]] = []
    processed_tickers = set()

    for filing in filings[: max_filings * 5]:
        if len(extracted_facts) >= max_filings:
            break

        ticker = filing.get("ticker")
        if not ticker or ticker in processed_tickers:
            continue

        try:
            # Extract basic filing information
            company_name = filing.get("companyName", ticker)
            form_type = filing.get("formType", "Unknown")
            filing_date = filing.get("filingDate", "Unknown")

            # Create fact about the filing
            filing_fact = {
                "content": f"{company_name} ({ticker}) filed a {form_type} report with the SEC on {filing_date}.",
                "source_url": f"https://www.sec.gov/edgar/browse/?CIK={filing.get('cik', '')}",
            }
            extracted_facts.append(filing_fact)

            processed_tickers.add(ticker)
            logger.info(f"Extracted filing fact for {ticker}.")

        except Exception as e:
            logger.debug(f"Could not process filing for {ticker}: {e}")
            continue

    return extracted_facts


def extract_financial_facts_from_company(
    ticker: str,
    facts: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract financial facts from company data."""
    extracted_facts: list[dict[str, Any]] = []

    try:
        company_name = facts.get("entityName", ticker)

        # Look for financial data in different possible locations
        financial_data = facts.get("us-gaap", {})
        if not financial_data:
            financial_data = facts.get("dei", {})

        if financial_data:
            # Extract revenue if available
            revenue_data = financial_data.get("Revenues", [{}])[0]
            if revenue_data and "val" in revenue_data:
                revenue_value = int(revenue_data["val"])
                period_end = revenue_data.get("end", "recent period")

                revenue_fact = {
                    "content": f"{company_name} ({ticker}) reported revenue of ${revenue_value:,} for {period_end}.",
                    "source_url": f"https://www.sec.gov/edgar/browse/?CIK={facts.get('cik', '')}",
                }
                extracted_facts.append(revenue_fact)

            # Extract net income if available
            net_income_data = financial_data.get("NetIncomeLoss", [{}])[0]
            if net_income_data and "val" in net_income_data:
                net_income_value = int(net_income_data["val"])
                period_end = net_income_data.get("end", "recent period")

                net_income_fact = {
                    "content": f"{company_name} ({ticker}) reported net income of ${net_income_value:,} for {period_end}.",
                    "source_url": f"https://www.sec.gov/edgar/browse/?CIK={facts.get('cik', '')}",
                }
                extracted_facts.append(net_income_fact)

        # If no financial data, create basic company fact
        if not extracted_facts:
            basic_fact = {
                "content": f"{company_name} ({ticker}) is a publicly traded company with SEC filings available.",
                "source_url": f"https://www.sec.gov/edgar/browse/?CIK={facts.get('cik', '')}",
            }
            extracted_facts.append(basic_fact)

    except Exception as e:
        logger.debug(f"Could not extract financial facts for {ticker}: {e}")
        # Create basic fact as fallback
        basic_fact = {
            "content": f"{ticker} is a publicly traded company with SEC filings.",
            "source_url": f"https://www.sec.gov/edgar/search/?entityName={ticker}",
        }
        extracted_facts.append(basic_fact)

    return extracted_facts


def extract_concept_facts(
    ticker: str,
    concept: str,
    concept_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract facts from company concept data."""
    extracted_facts: list[dict[str, Any]] = []

    try:
        # Get the most recent value from the concept data
        units = concept_data.get("units", {})
        if not units:
            return extracted_facts

        # Look for USD values first, then any other unit
        usd_values = units.get("USD", [])
        if not usd_values:
            # Try to find any unit with values
            for _unit, values in units.items():
                if values and len(values) > 0:
                    usd_values = values
                    break

        if usd_values:
            # Get the most recent value
            latest_value = usd_values[0]
            value = latest_value.get("val", 0)
            end_date = latest_value.get("end", "recent period")
            form = latest_value.get("form", "10-K")

            # Format the fact based on the concept
            if concept == "Revenues":
                fact_content = f"{ticker} reported revenue of ${value:,} for {end_date} (filed in {form})."
            elif concept == "NetIncomeLoss":
                fact_content = f"{ticker} reported net income of ${value:,} for {end_date} (filed in {form})."
            elif concept == "Assets":
                fact_content = f"{ticker} reported total assets of ${value:,} for {end_date} (filed in {form})."
            elif concept == "Liabilities":
                fact_content = f"{ticker} reported total liabilities of ${value:,} for {end_date} (filed in {form})."
            else:
                fact_content = f"{ticker} reported {concept} of ${value:,} for {end_date} (filed in {form})."

            fact = {
                "content": fact_content,
                "source_url": f"https://www.sec.gov/edgar/search/?entityName={ticker}",
            }
            extracted_facts.append(fact)

    except Exception as e:
        logger.debug(
            f"Could not extract concept facts for {ticker} {concept}: {e}",
        )

    return extracted_facts


def get_sec_edgar_status() -> dict[str, Any]:
    """Check the status of SEC EDGAR integration."""
    try:
        from sec_edgar_api import EdgarClient

        edgar_client = EdgarClient(user_agent=USER_AGENT)
        available_methods = [
            method
            for method in dir(edgar_client)
            if not method.startswith("_")
        ]

        return {
            "status": "available",
            "available_methods": available_methods,
            "user_agent": USER_AGENT,
        }
    except ImportError:
        return {
            "status": "not_installed",
            "message": "sec_edgar_api package not installed",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
