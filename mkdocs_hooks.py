"""Custom mkdocs hooks for generating PDF documents"""

import dataclasses
from pathlib import Path
import os
import shlex
import shutil
import subprocess

from mkdocs.structure.files import File


@dataclasses.dataclass(frozen=True)
class PdfResourceConfig:
    pdf_name: str
    mkdocs_conf: str
    build_dir_name: str


PDF_RESOURCES = (
    PdfResourceConfig(
        pdf_name="seis-lab-data-development-guide.pdf",
        mkdocs_conf="mkdocs-pdf-dev-guide.yml",
        build_dir_name="site-dev-guide-pdf",
    ),
    PdfResourceConfig(
        pdf_name="seis-lab-data-administration-guide.pdf",
        mkdocs_conf="mkdocs-pdf-admin-guide.yml",
        build_dir_name="site-admin-guide-pdf",
    ),
)


_DESTINATION_RELATIVE_PATH = "assets/documents"
_pdfs_already_generated = False


def on_config(config):
    if not os.getenv("BUILD_PDFS"):
        return config

    global _pdfs_already_generated
    global _DESTINATION_RELATIVE_PATH

    if _pdfs_already_generated:
        print("PDFs already generated")
        return config

    print("Generating PDFs...")
    for pdf_resource_conf in PDF_RESOURCES:
        build_dir = Path(__file__).parent / pdf_resource_conf.build_dir_name
        try:
            subprocess.run(
                shlex.split(
                    f"mkdocs build "
                    f"--config-file {pdf_resource_conf.mkdocs_conf} "
                    f"--site-dir {build_dir}"
                ),
                check=True,
            )
        except subprocess.CalledProcessError as err:
            print(f"Error generating PDF {pdf_resource_conf.pdf_name}: {str(err)}")
        else:
            src_pdf_path = build_dir / f"pdf/{pdf_resource_conf.pdf_name}"
            dest_dir = Path(__file__).parent / f"docs/{_DESTINATION_RELATIVE_PATH}"
            dest_pdf_path = dest_dir / pdf_resource_conf.pdf_name

            dest_dir.mkdir(parents=True, exist_ok=True)
            if src_pdf_path.is_file():
                shutil.copy(src_pdf_path, dest_pdf_path)
                print(f"PDF successfully moved to {dest_pdf_path}")
                shutil.rmtree(build_dir, ignore_errors=True)
            else:
                print(f"Could not move PDF to {dest_pdf_path}")
    else:
        _pdfs_already_generated = True
    return config


def on_files(files, config):
    """
    Explicitly add the generated PDF to the MkDocs file list
    so the i18n plugin and link validator can see it.
    """
    global _DESTINATION_RELATIVE_PATH

    for pdf_resource in PDF_RESOURCES:
        path = "/".join((_DESTINATION_RELATIVE_PATH, pdf_resource.pdf_name))
        # Only add it if it's not already in the files list
        if not any(f.src_path == path for f in files):
            new_file = File(
                path=path,
                src_dir=config["docs_dir"],
                dest_dir=config["site_dir"],
                use_directory_urls=config["use_directory_urls"],
            )
            files.append(new_file)

    return files
