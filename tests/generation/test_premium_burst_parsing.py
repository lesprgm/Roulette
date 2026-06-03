from api import llm_client


def test_extract_completed_premium_burst_sites():
    text = """
    ===NDW_SITE_1_START===
    <thinking>one</thinking>
    <self_review>ok</self_review>
    ```html
    <!doctype html><html><body><main id="ndw-content">One</main></body></html>
    ```
    ===NDW_SITE_1_END===
    ===NDW_SITE_2_START===
    ````html
    <!doctype html><html><body><main id="ndw-content">Two</main></body></html>
    ````
    ===NDW_SITE_2_END===
    """

    sites = llm_client.extract_completed_premium_burst_sites(text)

    assert sites == [
        (1, '<!doctype html><html><body><main id="ndw-content">One</main></body></html>'),
        (2, '<!doctype html><html><body><main id="ndw-content">Two</main></body></html>'),
    ]


def test_premium_burst_rejected_payload_includes_issues():
    issues = [{"severity": "block", "field": "html.scripts[0]", "message": "bad src"}]

    payload = llm_client._premium_burst_rejected_payload(
        index=3,
        reason="preflight blocked",
        doc={"kind": "full_page_html", "html": "<html></html>"},
        issues=issues,
    )

    assert payload["rejected"] is True
    assert payload["premium_burst_index"] == 3
    assert payload["issues"] == issues


def test_summarize_preflight_issues_is_concise():
    issues = [
        {"severity": "block", "field": "html.scripts[0]", "message": "Unsupported script"},
        {"severity": "warn", "field": "html", "message": "Missing #ndw-content"},
    ]

    assert llm_client._summarize_preflight_issues(issues) == (
        "block:html.scripts[0]:Unsupported script | warn:html:Missing #ndw-content"
    )
