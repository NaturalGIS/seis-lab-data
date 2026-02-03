"""Custom mkdocs hooks for generating PDF documents"""

from pathlib import Path
import os
import shlex
import shutil
import subprocess

from mkdocs.structure.files import File


_destination_relative_path = "assets/documents"
_pdf_already_generated = False
_pdf_name = "seis-lab-data-development-guide.pdf"


def on_config(config):
    if not os.getenv("BUILD_PDF"):
        return config

    global _pdf_already_generated
    global _pdf_name
    global _destination_relative_path

    if _pdf_already_generated:
        print("PDF already generated")
        return config

    print("Generating PDF...")
    build_dir = Path(__file__).parent / "site-temp-pdf"
    try:
        subprocess.run(
            shlex.split(
                f"mkdocs build "
                f"--config-file mkdocs-pdf-dev-guide.yml "
                f"--site-dir {build_dir}"
            ),
            check=True,
        )
    except subprocess.CalledProcessError as err:
        print(f"Error generating PDF: {str(err)}")
    else:
        src_pdf_path = build_dir / f"pdf/{_pdf_name}"
        dest_dir = Path(__file__).parent / f"docs/{_destination_relative_path}"
        dest_pdf_path = dest_dir / _pdf_name

        dest_dir.mkdir(parents=True, exist_ok=True)
        if src_pdf_path.is_file():
            shutil.copy(src_pdf_path, dest_pdf_path)
            print(f"PDF successfully moved to {dest_pdf_path}")
            shutil.rmtree(build_dir, ignore_errors=True)
        else:
            print(f"Could not move PDF to {dest_pdf_path}")
    return config


def on_files(files, config):
    """
    Explicitly add the generated PDF to the MkDocs file list
    so the i18n plugin and link validator can see it.
    """
    global _destination_relative_path
    global _pdf_name
    path = "/".join((_destination_relative_path, _pdf_name))

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
