"""
Example script demonstrating provider credentialing system usage.

This script shows how to:
1. Create provider objects
2. Extract credentials from web sources
3. Use Claude for intelligent data processing
4. Process results
"""

import asyncio
import json
from credentialing.models import Provider, CredentialingTask, ExtractionStatus
from credentialing.claude_extractor import ClaudeExtractor
from credentialing.scraper import WebScraper, ScraperStatus
from credentialing.orchestrator import CredentialingOrchestrator
from credentialing.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


async def example_1_simple_extraction():
    """Example 1: Extract provider info from HTML using Claude."""
    print("\n" + "="*60)
    print("Example 1: Claude-based Data Extraction")
    print("="*60)

    # Sample HTML from a medical board (simplified)
    sample_html = """
    <html>
        <body>
            <h1>Physician License Information</h1>
            <table>
                <tr>
                    <td>Name:</td>
                    <td>John Michael Doe</td>
                </tr>
                <tr>
                    <td>License Number:</td>
                    <td>MD 123456</td>
                </tr>
                <tr>
                    <td>License Status:</td>
                    <td>Active</td>
                </tr>
                <tr>
                    <td>Specialty:</td>
                    <td>Internal Medicine</td>
                </tr>
                <tr>
                    <td>Issue Date:</td>
                    <td>January 15, 2020</td>
                </tr>
                <tr>
                    <td>Expiration Date:</td>
                    <td>January 15, 2026</td>
                </tr>
            </table>
        </body>
    </html>
    """

    extractor = ClaudeExtractor()

    print("\nInput HTML:", sample_html[:200] + "...")
    print("\nCalling Claude API for extraction...")

    result = extractor.extract_provider_info(sample_html)

    if result.get("success"):
        print("\n✓ Extraction successful!")
        print(json.dumps(result.get("data"), indent=2))
    else:
        print(f"\n✗ Extraction failed: {result.get('error')}")


async def example_2_web_scraping():
    """Example 2: Fetch and parse web content."""
    print("\n" + "="*60)
    print("Example 2: Web Scraping with Resilience")
    print("="*60)

    urls_to_fetch = [
        "https://example.com/provider-search",
        "https://invalid-url-that-will-timeout.local",
        "https://httpbin.org/status/429",  # Rate limit
    ]

    print(f"\nFetching {len(urls_to_fetch)} URLs...")

    async with WebScraper() as scraper:
        for url in urls_to_fetch:
            print(f"\n→ Fetching: {url}")
            result = await scraper.fetch(url)

            print(f"  Status: {result.status.value}")
            print(f"  Response Time: {result.response_time_ms}ms")

            if result.status == ScraperStatus.SUCCESS:
                print(f"  Content Length: {len(result.content)} bytes")
            elif result.error_message:
                print(f"  Error: {result.error_message}")


async def example_3_data_normalization():
    """Example 3: Normalize extracted data using Claude."""
    print("\n" + "="*60)
    print("Example 3: Data Normalization with Claude")
    print("="*60)

    raw_data = {
        "first_name": "John",
        "last_name": "Doe",
        "license_number": "MD 123456",
        "license_status": "VALID",
        "issue_date": "01/15/2020",
        "expiration_date": "01/15/2026",
    }

    extractor = ClaudeExtractor()

    print("\nRaw Data:", json.dumps(raw_data, indent=2))
    print("\nNormalizing with Claude...")

    result = extractor.normalize_credential_data(raw_data, "CA Medical Board")

    if result.get("success"):
        print("\n✓ Normalization successful!")
        print(json.dumps(result.get("data"), indent=2))
    else:
        print(f"\n✗ Normalization failed: {result.get('error')}")


async def example_4_sanctions_detection():
    """Example 4: Detect sanctions and red flags."""
    print("\n" + "="*60)
    print("Example 4: Sanctions and Red Flags Detection")
    print("="*60)

    provider_data = {
        "first_name": "Jane",
        "last_name": "Smith",
        "npi": "9876543210",
        "license_number": "MD555555",
        "state": "CA",
        "license_status": "expired",  # Red flag
    }

    extractor = ClaudeExtractor()

    print("\nProvider Data:", json.dumps(provider_data, indent=2))
    print("\nChecking for sanctions/red flags...")

    result = extractor.detect_sanctions(provider_data)

    if result.get("success"):
        print("\n✓ Sanction detection complete!")
        print(json.dumps(result.get("data"), indent=2))
    else:
        print(f"\n✗ Detection failed: {result.get('error')}")


async def example_5_full_pipeline():
    """Example 5: Complete credentialing pipeline."""
    print("\n" + "="*60)
    print("Example 5: Full Credentialing Pipeline")
    print("="*60)

    # Create provider object
    provider = Provider(
        first_name="Robert",
        last_name="Johnson",
        npi="1111111111",
        state_code="CA",
        specialty="Cardiology",
    )

    print(f"\nProvider: {provider.first_name} {provider.last_name}")
    print(f"NPI: {provider.npi}")
    print(f"State: {provider.state_code}")

    # Process through orchestrator
    orchestrator = CredentialingOrchestrator()

    print("\nProcessing through credentialing pipeline...")
    print("(Note: This will attempt to fetch real data)")

    try:
        task = await orchestrator.process_provider(
            provider,
            sources=["CA Medical Board"],  # Simplified for example
        )

        print(f"\nPipeline Status: {task.status}")
        print(f"Credentials Found: {len(task.credentials)}")
        print(f"Sanctions Found: {len(task.sanctions)}")

        if task.credentials:
            print("\nCredentials:")
            for cred in task.credentials:
                print(f"  - {cred.credential_type} ({cred.credential_number})")

        if task.normalized_data:
            summary = task.normalized_data.get("summary", {})
            print(f"\nSummary:")
            print(f"  Total Credentials: {summary.get('total_credentials', 0)}")
            print(f"  Requires Review: {summary.get('requires_review', False)}")

    except Exception as e:
        print(f"\n✗ Pipeline failed: {str(e)}")
        print("  (This is expected if sources are not accessible)")


async def example_6_batch_processing():
    """Example 6: Process multiple providers."""
    print("\n" + "="*60)
    print("Example 6: Batch Processing Multiple Providers")
    print("="*60)

    providers = [
        Provider(first_name="John", last_name="Doe", npi="1234567890", state_code="CA"),
        Provider(first_name="Jane", last_name="Smith", npi="0987654321", state_code="CA"),
        Provider(first_name="Bob", last_name="Wilson", npi="1111111111", state_code="CA"),
    ]

    print(f"\nProcessing {len(providers)} providers...")

    orchestrator = CredentialingOrchestrator()

    results = []
    for provider in providers:
        print(f"\n→ Processing: {provider.first_name} {provider.last_name}")

        try:
            task = await orchestrator.process_provider(
                provider,
                sources=["CA Medical Board"],
            )
            results.append(task)
            print(f"  Status: {task.status}")

        except Exception as e:
            print(f"  Error: {str(e)}")

    print(f"\n✓ Batch processing complete!")
    print(f"  Processed: {len(results)} providers")
    successful = sum(1 for t in results if t.status == ExtractionStatus.SUCCESS)
    print(f"  Successful: {successful}")


async def main():
    """Run all examples."""
    setup_logging("INFO", "text")

    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  Provider Credentialing System - Usage Examples            ║")
    print("╚════════════════════════════════════════════════════════════╝")

    # Note: Examples 1-4 require valid ANTHROPIC_API_KEY
    # Examples 2, 5-6 require network access

    try:
        # Example 1: Claude extraction (requires API key)
        await example_1_simple_extraction()
    except Exception as e:
        print(f"\nExample 1 skipped: {str(e)}")

    try:
        # Example 2: Web scraping
        await example_2_web_scraping()
    except Exception as e:
        print(f"\nExample 2 skipped: {str(e)}")

    try:
        # Example 3: Data normalization (requires API key)
        await example_3_data_normalization()
    except Exception as e:
        print(f"\nExample 3 skipped: {str(e)}")

    try:
        # Example 4: Sanctions detection (requires API key)
        await example_4_sanctions_detection()
    except Exception as e:
        print(f"\nExample 4 skipped: {str(e)}")

    try:
        # Example 5: Full pipeline
        await example_5_full_pipeline()
    except Exception as e:
        print(f"\nExample 5 skipped: {str(e)}")

    try:
        # Example 6: Batch processing
        await example_6_batch_processing()
    except Exception as e:
        print(f"\nExample 6 skipped: {str(e)}")

    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())