"""Deploy DAX measures to Power BI via the XMLA endpoint (Tabular Editor script)."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from ..dax.measures import DAXMeasureSet

log = logging.getLogger(__name__)


class MeasureDeployer:
    """Deploy measures using Tabular Editor 2 CLI.

    Tabular Editor 2 is free and can be invoked from the command line:
      TabularEditor.exe <server> <database> -S <script.cs>

    For automated environments, install TE2 via chocolatey or direct download.
    """

    def __init__(self, tabular_editor_path: str = "TabularEditor") -> None:
        self.te_path = tabular_editor_path

    def deploy(
        self,
        measure_set: DAXMeasureSet,
        xmla_endpoint: str,
        database_name: str,
    ) -> bool:
        """Write the C# script and invoke Tabular Editor CLI.

        Returns True on success, False otherwise.
        """
        script = measure_set.to_script()

        with tempfile.NamedTemporaryFile(
            suffix=".cs", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(script)
            script_path = Path(tmp.name)

        log.info("Deploying %d measures to %s / %s", len(measure_set.measures), xmla_endpoint, database_name)

        try:
            result = subprocess.run(
                [self.te_path, xmla_endpoint, database_name, "-S", str(script_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                log.error("Tabular Editor error:\n%s", result.stderr)
                return False
            log.info("Measure deployment successful")
            return True
        except FileNotFoundError:
            log.error(
                "Tabular Editor not found at '%s'. "
                "Install from https://github.com/TabularEditor/TabularEditor",
                self.te_path,
            )
            return False
        except subprocess.TimeoutExpired:
            log.error("Tabular Editor timed out after 120s")
            return False
        finally:
            script_path.unlink(missing_ok=True)

    def export_script(self, measure_set: DAXMeasureSet, output_path: Path) -> None:
        """Save the deployment script to disk without executing it."""
        output_path.write_text(measure_set.to_script(), encoding="utf-8")
        log.info("Tabular Editor script written to %s", output_path)

    def export_dax_file(self, measure_set: DAXMeasureSet, output_path: Path) -> None:
        """Save a plain DAX measure file for DAX Studio."""
        output_path.write_text(measure_set.to_dax_file(), encoding="utf-8")
        log.info("DAX file written to %s", output_path)
