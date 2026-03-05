"""Command-line interface for provider credentialing system."""

import asyncio
import json
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from credentialing.models import Provider, ExtractionStatus
from credentialing.orchestrator import CredentialingOrchestrator
from credentialing.logging_config import setup_logging, get_logger
from credentialing.config import settings

app = typer.Typer(help="Provider Credentialing Automation System")
console = Console()
logger = get_logger(__name__)


@app.command()
def credentialize(
        first_name: str = typer.Option(..., help="Provider first name"),
        last_name: str = typer.Option(..., help="Provider last name"),
        npi: Optional[str] = typer.Option(None, help="NPI number"),
        state: str = typer.Option("CA", help="State code"),
        sources: Optional[str] = typer.Option(
            None,
            help="Comma-separated list of sources to check (e.g., 'CA Medical Board,OIG,NPDB')",
        ),
        output_format: str = typer.Option(
            "table",
            help="Output format: table, json",
        ),
) -> None:
    """
    Run credentialing process for a provider.

    Example:
        provider-credentialing credentialize \
            --first-name John \
            --last-name Doe \
            --npi 1234567890 \
            --state CA
    """
    setup_logging(settings.log_level, settings.log_format)

    console.print(
        f"[bold blue]Provider Credentialing System[/bold blue]\n"
        f"Checking: {first_name} {last_name} (NPI: {npi})\n"
    )

    # Parse sources
    source_list = []
    if sources:
        source_list = [s.strip() for s in sources.split(",")]
    else:
        source_list = ["CA Medical Board", "OIG", "NPDB"]

    # Create provider object
    provider = Provider(
        first_name=first_name,
        last_name=last_name,
        npi=npi,
        state_code=state,
    )

    # Run credentialing process
    try:
        orchestrator = CredentialingOrchestrator()
        task = asyncio.run(orchestrator.process_provider(provider, source_list))

        # Display results
        if output_format == "json":
            _display_json_results(task)
        else:
            _display_table_results(task)

        logger.info("credentialing_complete", provider=f"{first_name} {last_name}")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        logger.error("credentialing_error", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def verify_license(
        license_number: str = typer.Option(..., help="License number"),
        state: str = typer.Option("CA", help="State code"),
) -> None:
    """
    Verify a specific license number.

    Example:
        provider-credentialing verify-license \
            --license-number MD123456 \
            --state CA
    """
    setup_logging(settings.log_level, settings.log_format)

    console.print(
        f"[bold blue]License Verification[/bold blue]\n"
        f"License: {license_number} ({state})\n"
    )

    # This would call specific verification APIs
    console.print(
        "[yellow]License verification - feature to be implemented[/yellow]"
    )


@app.command()
def check_exclusions(
        first_name: str = typer.Option(..., help="Provider first name"),
        last_name: str = typer.Option(..., help="Provider last name"),
        npi: Optional[str] = typer.Option(None, help="NPI number"),
) -> None:
    """
    Check OIG exclusion and sanction lists.

    Example:
        provider-credentialing check-exclusions \
            --first-name John \
            --last-name Doe
    """
    setup_logging(settings.log_level, settings.log_format)

    console.print(
        f"[bold blue]Exclusion Check[/bold blue]\n"
        f"Checking: {first_name} {last_name}\n"
    )

    console.print(
        "[yellow]Exclusion check - feature to be implemented[/yellow]"
    )


@app.command()
def batch_process(
        input_file: str = typer.Argument(..., help="CSV file with provider data"),
        sources: Optional[str] = typer.Option(
            None,
            help="Comma-separated list of sources",
        ),
) -> None:
    """
    Process multiple providers from CSV file.

    CSV format should include: first_name, last_name, npi, state

    Example:
        provider-credentialing batch-process providers.csv
    """
    setup_logging(settings.log_level, settings.log_format)

    console.print(
        f"[bold blue]Batch Processing[/bold blue]\n"
        f"Input file: {input_file}\n"
    )

    try:
        import csv

        with open(input_file, "r") as f:
            reader = csv.DictReader(f)
            providers = list(reader)

        console.print(f"Found {len(providers)} providers to process")

        # Process each provider
        orchestrator = CredentialingOrchestrator()
        results = []

        for idx, provider_data in enumerate(providers, 1):
            console.print(
                f"[bold]Processing {idx}/{len(providers)}: "
                f"{provider_data.get('first_name')} {provider_data.get('last_name')}[/bold]"
            )

            provider = Provider(
                first_name=provider_data.get("first_name", ""),
                last_name=provider_data.get("last_name", ""),
                npi=provider_data.get("npi"),
                state_code=provider_data.get("state", "CA"),
            )

            source_list = (
                [s.strip() for s in sources.split(",")]
                if sources
                else ["CA Medical Board", "OIG", "NPDB"]
            )

            task = asyncio.run(
                orchestrator.process_provider(provider, source_list)
            )
            results.append(task)

        # Display summary
        console.print("\n[bold blue]Batch Processing Complete[/bold blue]\n")
        successful = sum(
            1
            for task in results
            if task.status == ExtractionStatus.SUCCESS
        )
        console.print(f"Successful: {successful}/{len(results)}")

        # Save results
        output_file = input_file.replace(".csv", "_results.json")
        with open(output_file, "w") as f:
            json.dump(
                [json.loads(task.model_dump_json()) for task in results],
                f,
                indent=2,
            )
        console.print(f"Results saved to: {output_file}")

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        logger.error("batch_processing_error", error=str(e))
        raise typer.Exit(code=1)


@app.command()
def config_show() -> None:
    """Show current configuration."""
    setup_logging(settings.log_level, settings.log_format)

    console.print("[bold blue]Current Configuration[/bold blue]\n")

    config_table = Table(title="Settings")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="green")

    for key, value in settings.model_dump().items():
        if "api_key" in key:
            value = "***" if value else "Not set"
        config_table.add_row(key, str(value))

    console.print(config_table)


def _display_table_results(task) -> None:
    """Display credentialing results in table format."""
    # Provider info
    console.print("[bold blue]Provider Information[/bold blue]")
    provider_table = Table()
    provider_table.add_column("Field", style="cyan")
    provider_table.add_column("Value", style="green")

    provider = task.provider
    provider_table.add_row("Name", f"{provider.first_name} {provider.last_name}")
    provider_table.add_row("NPI", provider.npi or "Not provided")
    provider_table.add_row("State", provider.state_code)
    console.print(provider_table)

    # Credentials
    if task.credentials:
        console.print("\n[bold blue]Credentials Found[/bold blue]")
        cred_table = Table()
        cred_table.add_column("Type", style="cyan")
        cred_table.add_column("Authority", style="yellow")
        cred_table.add_column("Number", style="green")
        cred_table.add_column("Status", style="magenta")
        cred_table.add_column("Expiration", style="blue")

        for cred in task.credentials:
            cred_table.add_row(
                cred.credential_type,
                cred.issuing_authority,
                cred.credential_number or "N/A",
                str(cred.status.value),
                cred.expiration_date or "N/A",
                )

        console.print(cred_table)
    else:
        console.print("[yellow]No credentials found[/yellow]")

    # Sanctions
    if task.sanctions:
        console.print("\n[bold red]Sanctions/Red Flags[/bold red]")
        sanction_table = Table()
        sanction_table.add_column("Type", style="red")
        sanction_table.add_column("Description", style="yellow")
        sanction_table.add_column("Source", style="cyan")

        for sanction in task.sanctions:
            sanction_table.add_row(
                sanction.sanction_type,
                sanction.description or "N/A",
                sanction.source,
                )

        console.print(sanction_table)

    # Summary
    console.print("\n[bold blue]Summary[/bold blue]")
    summary_table = Table()
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="green")

    if task.normalized_data:
        summary = task.normalized_data.get("summary", {})
        summary_table.add_row("Total Credentials", str(summary.get("total_credentials", 0)))
        summary_table.add_row("Active Credentials", str(summary.get("active_credentials", 0)))
        summary_table.add_row("Expired Credentials", str(summary.get("expired_credentials", 0)))
        summary_table.add_row("Sanctions Found", str(summary.get("sanctions_found", 0)))
        summary_table.add_row(
            "Requires Review",
            "Yes" if summary.get("requires_review") else "No",
        )

    console.print(summary_table)


def _display_json_results(task) -> None:
    """Display credentialing results in JSON format."""

    result = {
        "status": str(task.status),
        "provider": task.provider.model_dump(),
        "credentials": [c.model_dump() for c in task.credentials],
        "sanctions": [s.model_dump() for s in task.sanctions],
        "normalized_data": task.normalized_data,
    }

    console.print_json(data=result)


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()