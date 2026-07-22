import re
import uuid
from urllib.parse import urlencode

import pytest
from playwright.sync_api import (
    Locator,
    Page,
    expect,
)


def _fill_asset_discovery_configuration_form(
    page: Page, name: str, relative_path_regexp: str, media_type: str = "image/tiff"
):
    # unlike dataset categories / workflow stages, the name here is a plain (not
    # localizable) field, and there are two additional required associations
    page.get_by_role("textbox", name="field-name").fill(name)
    page.get_by_role("textbox", name="field-relative_path_regexp").fill(
        relative_path_regexp
    )
    page.get_by_role("textbox", name="field-media_type").fill(media_type)
    # pick whatever the first available option is for each association — the test
    # only cares that some valid dataset category / workflow stage gets linked,
    # not which one, so it doesn't need to hardcode sample data names
    page.get_by_role("combobox", name="field-dataset_category_id").select_option(
        index=0
    )
    page.get_by_role("combobox", name="field-workflow_stage_id").select_option(index=0)


def _find_asset_discovery_configuration_card(page: Page, name: str) -> Locator:
    """Locate the listing-page card for a given asset discovery configuration.

    Asset discovery configurations have no dedicated detail page, same as dataset
    categories / workflow stages. However, unlike those two, the in-page search
    box here doesn't actually filter anything: it sends a `search` signal, but the
    server-side filter for this resource only ever looks for a `name` query
    parameter (see `AssetDiscoveryConfigurationListFilters`/`NameFilter` in
    `webapp/filters.py`), so the search input is a no-op for this resource. The
    reliable way to isolate a single item regardless of pagination/sort order is
    to navigate directly with that `name` query parameter instead, which the
    initial listing GET endpoint does honor (as an `ilike` substring match).
    """
    page.goto(f"/asset-discovery-configurations/?{urlencode({'name': name})}")
    card = page.locator(".card", has_text=name)
    expect(card).to_be_visible(timeout=10_000)
    return card


@pytest.mark.e2e
def test_asset_discovery_configuration_lifecycle(authenticated_page: Page):
    # start from the landing page
    authenticated_page.goto("/")

    resource_name_id = uuid.uuid4().hex[:8]

    # navigate to the asset discovery configurations page and click the create new button
    authenticated_page.get_by_role("button", name="settings").click()
    authenticated_page.get_by_role(
        "link", name="list-asset-discovery-configurations"
    ).click()
    authenticated_page.get_by_role(
        "link", name="new-asset-discovery-configuration"
    ).click()

    # hit the cancel button and verify we are brought back to the listing page
    authenticated_page.get_by_role("link", name="cancel-creation").click()

    authenticated_page.get_by_role(
        "link", name="new-asset-discovery-configuration"
    ).click()

    # fill out the form and submit it — use a unique suffix to avoid collisions across runs
    config_name = f"e2e test asset discovery configuration {resource_name_id}"
    _fill_asset_discovery_configuration_form(
        authenticated_page, config_name, r".*\.tif$"
    )

    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # expect to be redirected to the listing page upon successful creation
    expect(authenticated_page).to_have_url(
        re.compile(r"/asset-discovery-configurations/$"), timeout=10_000
    )

    # find the newly-created configuration and open its edit form
    card = _find_asset_discovery_configuration_card(authenticated_page, config_name)
    card.get_by_role("link").click()

    updated_config_name = f"{config_name} (updated)"
    _fill_asset_discovery_configuration_form(
        authenticated_page, updated_config_name, r".*\.jp2$"
    )
    authenticated_page.get_by_role("button", name="submit-update-form").click()

    # expect to be redirected to the listing page upon successful modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/asset-discovery-configurations/$"), timeout=10_000
    )
    card = _find_asset_discovery_configuration_card(
        authenticated_page, updated_config_name
    )

    # now try to modify the configuration again, but this time hit the cancel button
    card.get_by_role("link").click()
    authenticated_page.get_by_role("link", name="cancel-update").click()

    # expect to be redirected to the listing page upon cancelling the modification
    expect(authenticated_page).to_have_url(
        re.compile(r"/asset-discovery-configurations/$"), timeout=10_000
    )

    # clean up by deleting the newly-created configuration
    card = _find_asset_discovery_configuration_card(
        authenticated_page, updated_config_name
    )
    card.get_by_role("button", name="show-delete-confirmation-modal").click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(card).not_to_be_visible()


@pytest.mark.e2e
def test_asset_discovery_configuration_creation_rejects_duplicate_name(
    authenticated_page: Page,
):
    authenticated_page.goto("/")
    authenticated_page.get_by_role("button", name="settings").click()
    authenticated_page.get_by_role(
        "link", name="list-asset-discovery-configurations"
    ).click()

    # create an initial configuration
    resource_name_id = uuid.uuid4().hex[:8]
    config_name = f"e2e duplicate test {resource_name_id}"
    authenticated_page.get_by_role(
        "link", name="new-asset-discovery-configuration"
    ).click()
    _fill_asset_discovery_configuration_form(
        authenticated_page, config_name, r".*\.tif$"
    )
    authenticated_page.get_by_role("button", name="submit-create-form").click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/asset-discovery-configurations/$"), timeout=10_000
    )

    # navigate to the create form and submit with the same (globally unique) name
    authenticated_page.get_by_role(
        "link", name="new-asset-discovery-configuration"
    ).click()
    _fill_asset_discovery_configuration_form(
        authenticated_page, config_name, r".*\.jp2$"
    )
    authenticated_page.get_by_role("button", name="submit-create-form").click()

    # unlike dataset categories / workflow stages, name uniqueness here is only
    # enforced at the database level and discovered asynchronously by the
    # background worker — the app redirects to the listing page regardless of
    # outcome, and reports the failure via a flash notification rather than an
    # inline field error
    expect(authenticated_page).to_have_url(
        re.compile(r"/asset-discovery-configurations/$"), timeout=10_000
    )
    expect(authenticated_page.locator(".toast.text-bg-danger")).to_be_visible(
        timeout=10_000
    )

    # clean up the single (successfully-created) configuration
    card = _find_asset_discovery_configuration_card(authenticated_page, config_name)
    card.get_by_role("button", name="show-delete-confirmation-modal").click()
    authenticated_page.get_by_role("button", name="delete-item").click()
    expect(card).not_to_be_visible()
