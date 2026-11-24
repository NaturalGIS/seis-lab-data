"""Managing survey-related records in the browser

An editor creates, modifies and deletes survey-related records within a survey mission,
selects several records in the listing to update them together or to download the list
of their download links, and switches between listing layouts.
"""

import re
import uuid

import pytest
from playwright.sync_api import (
    Page,
    expect,
)


def _fill_project_form_minimal(page: Page, name: str):
    page.get_by_role("textbox", name="field-name", exact=True).fill(name)


def _fill_survey_mission_form_minimal(page: Page, name: str):
    page.get_by_role("textbox", name="field-name", exact=True).fill(name)


def _fill_survey_related_record_form(page: Page, name: str):
    page.get_by_role("textbox", name="field-name", exact=True).fill(name)
    page.get_by_role("textbox", name="field-description", exact=True).fill(
        "e2e survey-related record description"
    )


def _fill_bounding_box(page: Page):
    # a spatial extent is required for a resource to be valid, and thus published
    for name, value in (
        ("min_lon", "-10"),
        ("max_lon", "-9"),
        ("min_lat", "38"),
        ("max_lat", "39"),
    ):
        page.locator(f"[aria-label='field-bounding_box-{name}']").fill(value)


def _wait_for_thumbnail_and_reload(page: Page):
    """Wait until the thumbnail of the project or survey mission shown in the page
    exists, then reload the page.

    The thumbnail of a resource with a bounding box is generated in the background, and
    storing it reloads the resource's page at an arbitrary moment, which would cancel a
    navigation started meanwhile.
    """
    for _ in range(60):
        if page.request.get(f"{page.url}/thumbnail").ok:
            break
        page.wait_for_timeout(500)
    else:
        raise AssertionError(f"The thumbnail of {page.url} was not generated")
    page.reload()


@pytest.mark.e2e
def test_survey_related_record_lifecycle(authenticated_page: Page):
    """Within a new project and survey mission, an editor creates a survey-related
    record with two links and two assets, each asset with its own link, then renames the
    record and deletes it, followed by the survey mission and the project. The deletion
    confirmation names the record.
    """
    # NOTE: this test is perhaps overly long, but for now it covers the full creation
    # and deletion lifecycle of survey-related records. Let's revise later once
    # search functionality has been implemented.

    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # create the survey mission
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form_minimal(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )

    # create the survey-related record
    record_name_id = uuid.uuid4().hex[:8]
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    record_name = f"e2e test survey-related record {record_name_id}"
    _fill_survey_related_record_form(authenticated_page, record_name)

    authenticated_page.get_by_role(
        "button", name="add-another-link", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-url", exact=True
    ).fill("http://fakelink.com/for/record")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-media_type", exact=True
    ).fill("text/html")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-relation", exact=True
    ).fill("fake-relation")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-0-link_description", exact=True
    ).fill("some link description")

    authenticated_page.get_by_role(
        "button", name="add-another-link", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-url", exact=True
    ).fill("http://fakelink2.com")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-media_type", exact=True
    ).fill("text/html")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-relation", exact=True
    ).fill("fake-relation2")
    authenticated_page.get_by_role(
        "textbox", name="field-link-links-1-link_description", exact=True
    ).fill("some description for link 2")

    authenticated_page.get_by_role(
        "button", name="add-another-asset", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-name", exact=True
    ).fill("Sample e2e asset")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-description", exact=True
    ).fill("This is a sample asset used in e2e tests")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-0-relative_path", exact=True
    ).fill("/asset/relative/path.tif")
    authenticated_page.get_by_role(
        "button", name="asset-0-add-another-link", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-asset-0-link-assets-0-links-0-url", exact=True
    ).fill("http://fakelink.com/for/record")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-0-link-assets-0-links-0-media_type", exact=True
    ).fill("text/html")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-0-link-assets-0-links-0-relation", exact=True
    ).fill("fake-relation")
    authenticated_page.get_by_role(
        "textbox", name="field-link-assets-0-links-0-link_description", exact=True
    ).fill("some link description")

    authenticated_page.get_by_role(
        "button", name="add-another-asset", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-name", exact=True
    ).fill("Sample e2e second asset")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-description", exact=True
    ).fill("This the second sample asset used in e2e tests")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-assets-1-relative_path", exact=True
    ).fill("/asset/relative/second-path.tif")
    authenticated_page.get_by_role(
        "button", name="asset-1-add-another-link", exact=True
    ).click()
    authenticated_page.get_by_role(
        "textbox", name="field-asset-1-link-assets-1-links-0-url", exact=True
    ).fill("http://fakelink.com/for/record")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-1-link-assets-1-links-0-media_type", exact=True
    ).fill("text/html")
    authenticated_page.get_by_role(
        "textbox", name="field-asset-1-link-assets-1-links-0-relation", exact=True
    ).fill("fake-relation")
    authenticated_page.get_by_role(
        "textbox", name="field-link-assets-1-links-0-link_description", exact=True
    ).fill("some link description")

    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
    )

    # now try to modify the record but cancel
    authenticated_page.get_by_role("link", name="update-item", exact=True).click()
    authenticated_page.get_by_role("link", name="cancel-update", exact=True).click()

    # and now actually modify it
    authenticated_page.get_by_role("link", name="update-item", exact=True).click()
    authenticated_page.get_by_role("textbox", name="field-name", exact=True).fill(
        f"The modified name {record_name_id}"
    )
    authenticated_page.get_by_role(
        "button", name="submit-update-form", exact=True
    ).click()

    # clean up: delete record → mission → project
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    # the confirmation dialog names the item about to be deleted
    expect(authenticated_page.get_by_role("dialog")).to_contain_text(
        f"“The modified name {record_name_id}”"
    )
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(
        authenticated_page.get_by_role("link", name="new-item", exact=True)
    ).to_be_visible()

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"))


@pytest.mark.e2e
def test_survey_related_record_bulk_selection(authenticated_page: Page):
    """In the list of records of a survey mission, an editor selects records one by one
    and sees the number selected, clears the selection, and finds that changing the
    search text also clears it.
    """
    # NOTE: this only exercises the selection primitives (checkboxes, count,
    # clear, auto-clear-on-filter-change) on the mission-scoped listing, where
    # the record count is fully controlled by the test. The top-level listing
    # pools records system-wide, so a deterministic "select all N matching"
    # assertion there would depend on how much other data exists in the DB.

    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form_minimal(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    record_urls = []
    for i in range(2):
        authenticated_page.get_by_role("link", name="new-item", exact=True).click()
        record_name = f"e2e bulk selection record {i} {uuid.uuid4().hex[:8]}"
        _fill_survey_related_record_form(authenticated_page, record_name)
        authenticated_page.get_by_role(
            "button", name="submit-create-form", exact=True
        ).click()
        expect(authenticated_page).to_have_url(
            re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
        )
        record_urls.append(authenticated_page.url)
        authenticated_page.goto(mission_detail_url)

    checkboxes = authenticated_page.get_by_role(
        "checkbox", name="select-item", exact=True
    )
    expect(checkboxes).to_have_count(2)
    selected_count = authenticated_page.locator("[aria-label='selected-count']")
    clear_selection_button = authenticated_page.get_by_role(
        "button", name="clear-selection", exact=True
    )

    checkboxes.nth(0).check()
    expect(selected_count).to_contain_text("1 selected")
    expect(clear_selection_button).to_be_visible()

    checkboxes.nth(1).check()
    expect(selected_count).to_contain_text("2 selected")

    clear_selection_button.click()
    expect(selected_count).to_be_hidden()
    expect(clear_selection_button).to_be_hidden()

    # selecting again, then changing the search filter should clear it back out
    checkboxes.nth(0).check()
    expect(selected_count).to_contain_text("1 selected")
    authenticated_page.get_by_placeholder("Search", exact=True).fill(
        "something not matching"
    )
    expect(checkboxes).to_have_count(0)
    authenticated_page.get_by_placeholder("Search", exact=True).fill("")
    expect(selected_count).to_be_hidden()

    # clean up: delete both records, then mission, then project
    for record_url in record_urls:
        authenticated_page.goto(record_url)
        authenticated_page.get_by_role(
            "button", name="show-delete-confirmation-modal", exact=True
        ).click()
        authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
        expect(
            authenticated_page.get_by_role("link", name="new-item", exact=True)
        ).to_be_visible()

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"))


@pytest.mark.e2e
def test_survey_related_record_selectable_after_hovering_thumbnail(
    authenticated_page: Page,
):
    """In the list of records of a survey mission, moving the pointer across a record's
    thumbnail onto its selection box and clicking it selects the record, without opening
    the record.
    """
    # the selection checkbox overlays the record's thumbnail, whose hover effect must
    # not paint the thumbnail over the checkbox, as moving the pointer to the checkbox
    # usually goes through the thumbnail
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form_minimal(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    record_name = f"e2e thumbnail hover record {uuid.uuid4().hex[:8]}"
    _fill_survey_related_record_form(authenticated_page, record_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
    )
    record_detail_url = authenticated_page.url
    authenticated_page.goto(mission_detail_url)

    records_listing = authenticated_page.locator("#survey-mission-records")
    checkbox = records_listing.get_by_role("checkbox", name="select-item", exact=True)
    expect(checkbox).to_have_count(1)

    # the pointer is moved and clicked by coordinates, as the actionability checks of
    # locator actions do not reproduce a pointer moving from the thumbnail to the
    # checkbox
    checkbox.scroll_into_view_if_needed()
    thumbnail_box = records_listing.locator("a.list-item-thumb").bounding_box()
    checkbox_box = checkbox.bounding_box()
    authenticated_page.mouse.move(
        thumbnail_box["x"] + thumbnail_box["width"] / 2,
        thumbnail_box["y"] + thumbnail_box["height"] / 2,
    )
    checkbox_x = checkbox_box["x"] + checkbox_box["width"] / 2
    checkbox_y = checkbox_box["y"] + checkbox_box["height"] / 2
    authenticated_page.mouse.move(checkbox_x, checkbox_y, steps=10)
    authenticated_page.mouse.click(checkbox_x, checkbox_y)
    expect(checkbox).to_be_checked()
    expect(authenticated_page).to_have_url(mission_detail_url)
    expect(authenticated_page.locator("[aria-label='selected-count']")).to_contain_text(
        "1 selected"
    )

    # clean up: delete the record, then the mission, then the project
    authenticated_page.goto(record_detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(
        authenticated_page.get_by_role("link", name="new-item", exact=True)
    ).to_be_visible()

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"))


@pytest.mark.e2e
def test_survey_related_record_listing_layouts(authenticated_page: Page):
    """The list of records of a survey mission shows each draft record with its status,
    its project and a selection box, without edit or delete buttons. The compact layout
    hides the project, is remembered after reloading the page, and the regular layout
    shows it again.
    """
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form_minimal(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    record_name = f"e2e listing layouts record {uuid.uuid4().hex[:8]}"
    _fill_survey_related_record_form(authenticated_page, record_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
    )
    record_detail_url = authenticated_page.url
    authenticated_page.goto(mission_detail_url)

    records_listing = authenticated_page.locator("#survey-mission-records")
    checkboxes = records_listing.get_by_role("checkbox", name="select-item", exact=True)
    project_badge = records_listing.locator("a.badge.bg-project")

    # a new record is a draft, therefore it shows its status. Records are only
    # edited and deleted from their detail page, never from the listing
    expect(checkboxes).to_have_count(1)
    expect(records_listing.locator("[aria-label='item-status']")).to_be_visible()
    expect(project_badge).to_be_visible()
    expect(
        records_listing.get_by_role("link", name="update-list-item", exact=True)
    ).to_have_count(0)
    expect(
        records_listing.get_by_role(
            "button", name="show-delete-list-item-confirmation-modal", exact=True
        )
    ).to_have_count(0)

    authenticated_page.get_by_role("button", name="compact-layout", exact=True).click()
    expect(checkboxes).to_have_count(1)
    expect(project_badge).to_be_hidden()

    # the chosen layout is remembered across page loads
    authenticated_page.reload()
    expect(checkboxes).to_have_count(1)
    expect(project_badge).to_be_hidden()

    authenticated_page.get_by_role("button", name="regular-layout", exact=True).click()
    expect(project_badge).to_be_visible()

    # clean up: delete record, then mission, then project
    authenticated_page.goto(record_detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(mission_detail_url, timeout=15_000)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"))


@pytest.mark.e2e
def test_bulk_update_survey_related_records(authenticated_page: Page):
    """An editor selects two records of a survey mission and opens the bulk update form,
    which shows the number of records concerned and refuses a submission that changes
    nothing. Choosing a new workflow stage then updates both records.
    """
    # NOTE: only exercises the "manually selected" mode - "select all matching"
    # only becomes available when more records match than fit on one page,
    # which a small deterministic fixture like this one won't trigger (same
    # reasoning as test_survey_related_record_bulk_selection above). The
    # filtered/select-all-matching path is already covered at the
    # operation/command layer by integration tests.

    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form_minimal(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    record_urls = []
    for i in range(2):
        authenticated_page.get_by_role("link", name="new-item", exact=True).click()
        record_name = f"e2e bulk update record {i} {uuid.uuid4().hex[:8]}"
        _fill_survey_related_record_form(authenticated_page, record_name)
        authenticated_page.get_by_role(
            "button", name="submit-create-form", exact=True
        ).click()
        expect(authenticated_page).to_have_url(
            re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
        )
        record_urls.append(authenticated_page.url)
        authenticated_page.goto(mission_detail_url)

    checkboxes = authenticated_page.get_by_role(
        "checkbox", name="select-item", exact=True
    )
    expect(checkboxes).to_have_count(2)
    checkboxes.nth(0).check()
    checkboxes.nth(1).check()

    authenticated_page.get_by_role("link", name="bulk-update", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}/records/bulk-update\?"),
        timeout=10_000,
    )
    expect(
        authenticated_page.locator("[aria-label='bulk-update-matched-count']")
    ).to_contain_text("2")

    # submitting with nothing checked should fail validation, not silently no-op
    authenticated_page.get_by_role(
        "button", name="submit-bulk-update-form", exact=True
    ).click()
    expect(
        authenticated_page.locator(
            "#backend-validation-update_dataset_category-feedback"
        )
    ).to_be_visible()

    authenticated_page.get_by_role(
        "checkbox", name="field-update_workflow_stage", exact=True
    ).check()
    workflow_stage_select = authenticated_page.get_by_role(
        "combobox", name="field-workflow_stage_id", exact=True
    )
    # picked by index rather than by (locale-dependent) label text - new records
    # default to whichever stage sorts first, so index 1 is guaranteed different
    target_workflow_stage_id = (
        workflow_stage_select.locator("option").nth(1).get_attribute("value")
    )
    workflow_stage_select.select_option(index=1)
    authenticated_page.get_by_role(
        "button", name="submit-bulk-update-form", exact=True
    ).click()

    expect(authenticated_page).to_have_url(mission_detail_url, timeout=15_000)
    expect(
        authenticated_page.locator('.toast[data-category="success"]')
    ).to_be_visible()

    for record_url in record_urls:
        authenticated_page.goto(record_url)
        authenticated_page.get_by_role("link", name="update-item", exact=True).click()
        expect(
            authenticated_page.get_by_role(
                "combobox", name="field-workflow_stage_id", exact=True
            )
        ).to_have_value(target_workflow_stage_id)

    # clean up: delete both records, then mission, then project
    for record_url in record_urls:
        authenticated_page.goto(record_url)
        authenticated_page.get_by_role(
            "button", name="show-delete-confirmation-modal", exact=True
        ).click()
        authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
        expect(
            authenticated_page.get_by_role("link", name="new-item", exact=True)
        ).to_be_visible()

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"))


@pytest.mark.e2e
def test_survey_related_record_creation_rejects_duplicate_name(
    authenticated_page: Page,
):
    """Creating a survey-related record with the name of an existing record of the same
    survey mission is refused, and the form shows an error next to the name field.
    """
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()

    project_name = f"e2e test project {uuid.uuid4().hex[:8]}"
    _fill_project_form_minimal(authenticated_page, project_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )

    # create the survey mission
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    mission_name = f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    _fill_survey_mission_form_minimal(authenticated_page, mission_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    mission_detail_url = authenticated_page.url

    # create the initial survey-related record
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    record_name = f"e2e duplicate record {uuid.uuid4().hex[:8]}"
    _fill_survey_related_record_form(authenticated_page, record_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
    )
    record_detail_url = authenticated_page.url

    # try to create another record with the same name under the same mission
    authenticated_page.goto(mission_detail_url)
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    _fill_survey_related_record_form(authenticated_page, record_name)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(
        authenticated_page.locator("#backend-validation-name-feedback")
    ).to_be_visible()

    # clean up: navigate to the record detail page and delete it, then mission, then project
    authenticated_page.goto(record_detail_url)
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(
        authenticated_page.get_by_role("link", name="new-item", exact=True)
    ).to_be_visible()

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(
        authenticated_page.get_by_role("link", name="new-project", exact=True)
    ).to_be_visible()


@pytest.mark.e2e
def test_published_survey_related_record_can_be_edited_and_deleted(
    authenticated_page: Page,
):
    """A project, survey mission and survey-related record created with a bounding box
    are valid and published automatically, with no manual publish button. The published
    record stays published after being renamed, and the record, survey mission and
    project can all be deleted.
    """
    # publication is automatic - valid resources are published when saved, there
    # is no manual (un)publishing and published resources remain editable and
    # deletable
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()
    authenticated_page.get_by_role("textbox", name="field-name", exact=True).fill(
        f"e2e test project {uuid.uuid4().hex[:8]}"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-description", exact=True
    ).fill("e2e test description")
    _fill_bounding_box(authenticated_page)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )
    _wait_for_thumbnail_and_reload(authenticated_page)

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    authenticated_page.get_by_role("textbox", name="field-name", exact=True).fill(
        f"e2e test survey mission {uuid.uuid4().hex[:8]}"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-description", exact=True
    ).fill("e2e test description")
    authenticated_page.get_by_role(
        "textbox", name="field-relative_path", exact=True
    ).fill("/somewhere/survey/mission")
    _fill_bounding_box(authenticated_page)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    _wait_for_thumbnail_and_reload(authenticated_page)

    record_name_id = uuid.uuid4().hex[:8]
    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    _fill_survey_related_record_form(
        authenticated_page, f"e2e test survey-related record {record_name_id}"
    )
    _fill_bounding_box(authenticated_page)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
    )
    record_detail_url = authenticated_page.url
    authenticated_page.reload()
    # the info section shows a status row for every status except published
    expect(authenticated_page.locator("[aria-label='info-section']")).to_be_visible()
    expect(authenticated_page.locator("[aria-label='status']")).to_have_count(0)
    expect(
        authenticated_page.get_by_role("button", name="publish-record", exact=True)
    ).to_have_count(0)
    expect(
        authenticated_page.get_by_role("button", name="unpublish-record", exact=True)
    ).to_have_count(0)

    # an edit that keeps the record valid keeps it published
    authenticated_page.get_by_role("link", name="update-item", exact=True).click()
    authenticated_page.get_by_role("textbox", name="field-name", exact=True).fill(
        f"The modified name {record_name_id}"
    )
    authenticated_page.get_by_role(
        "button", name="submit-update-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(record_detail_url, timeout=10_000)
    authenticated_page.reload()
    # the info section shows a status row for every status except published
    expect(authenticated_page.locator("[aria-label='info-section']")).to_be_visible()
    expect(authenticated_page.locator("[aria-label='status']")).to_have_count(0)

    # clean up: published record, mission and project are all deletable
    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"), timeout=15_000)


@pytest.mark.e2e
def test_download_links_of_records_selected_in_the_main_listing(
    authenticated_page: Page,
):
    """In the main list of survey-related records, a user selects two published records
    and downloads the list of their download links, which contains one link for the data
    file of each record, with the file's path in the archive as its destination, even
    when the paths of the survey mission and of the files were entered with a leading
    slash.
    """
    # the main listing is opened afresh with the search already applied, since the
    # selection used to go missing from the download links after the page first loads
    token = uuid.uuid4().hex[:8]
    authenticated_page.goto("/")
    authenticated_page.get_by_role("link", name="list-projects", exact=True).click()
    authenticated_page.get_by_role("link", name="new-project", exact=True).click()
    _fill_project_form_minimal(authenticated_page, f"e2e test project {token}")
    _fill_bounding_box(authenticated_page)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=10_000
    )
    _wait_for_thumbnail_and_reload(authenticated_page)

    authenticated_page.get_by_role("link", name="new-item", exact=True).click()
    _fill_survey_mission_form_minimal(
        authenticated_page, f"e2e test survey mission {token}"
    )
    authenticated_page.get_by_role(
        "textbox", name="field-relative_path", exact=True
    ).fill("/somewhere/survey/mission")
    _fill_bounding_box(authenticated_page)
    authenticated_page.get_by_role(
        "button", name="submit-create-form", exact=True
    ).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/survey-missions/[0-9a-f-]{36}$"), timeout=10_000
    )
    _wait_for_thumbnail_and_reload(authenticated_page)
    mission_detail_url = authenticated_page.url

    record_urls = []
    for i in range(2):
        authenticated_page.get_by_role("link", name="new-item", exact=True).click()
        _fill_survey_related_record_form(
            authenticated_page, f"e2e download links record {i} {token}"
        )
        _fill_bounding_box(authenticated_page)
        authenticated_page.get_by_role(
            "button", name="add-another-asset", exact=True
        ).click()
        authenticated_page.get_by_role(
            "textbox", name="field-asset-assets-0-name", exact=True
        ).fill(f"e2e data file {i}")
        authenticated_page.get_by_role(
            "textbox", name="field-asset-assets-0-relative_path", exact=True
        ).fill(f"/{token}/file-{i}.tif")
        authenticated_page.get_by_role(
            "button", name="submit-create-form", exact=True
        ).click()
        expect(authenticated_page).to_have_url(
            re.compile(r"/survey-related-records/[0-9a-f-]{36}$"), timeout=10_000
        )
        # the record is published in the background, and only published records are
        # included in the download links
        expect(
            authenticated_page.locator("[aria-label='info-section']")
        ).to_be_visible()
        expect(authenticated_page.locator("[aria-label='status']")).to_have_count(
            0, timeout=15_000
        )
        record_urls.append(authenticated_page.url)
        authenticated_page.goto(mission_detail_url)

    authenticated_page.goto(f"/survey-related-records/?search={token}")
    checkboxes = authenticated_page.get_by_role(
        "checkbox", name="select-item", exact=True
    )
    expect(checkboxes).to_have_count(2)
    checkboxes.nth(0).check()
    checkboxes.nth(1).check()
    expect(authenticated_page.locator("[aria-label='selected-count']")).to_contain_text(
        "2 selected"
    )
    with authenticated_page.expect_download() as download_info:
        authenticated_page.get_by_role(
            "link", name="download-links", exact=True
        ).click()
    with open(download_info.value.path(), encoding="utf-8") as download_file:
        lines = [
            line
            for line in download_file.read().splitlines()
            if not line.startswith("#")
        ]
    urls, outputs = lines[::2], lines[1::2]
    assert len(urls) == 2
    assert all(
        re.search(
            r"/survey-related-records/[0-9a-f-]{36}/assets/[0-9a-f-]{36}/download$", url
        )
        for url in urls
    )
    assert sorted(outputs) == [
        f"  out=somewhere/survey/mission/{token}/file-{i}.tif" for i in range(2)
    ]

    # clean up: delete both records, then mission, then project
    for record_url in record_urls:
        authenticated_page.goto(record_url)
        authenticated_page.get_by_role(
            "button", name="show-delete-confirmation-modal", exact=True
        ).click()
        authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
        expect(
            authenticated_page.get_by_role("link", name="new-item", exact=True)
        ).to_be_visible()

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(
        re.compile(r"/projects/[0-9a-f-]{36}$"), timeout=15_000
    )

    authenticated_page.get_by_role(
        "button", name="show-delete-confirmation-modal", exact=True
    ).click()
    authenticated_page.get_by_role("button", name="delete-item", exact=True).click()
    expect(authenticated_page).to_have_url(re.compile(r"/projects/?$"), timeout=15_000)
