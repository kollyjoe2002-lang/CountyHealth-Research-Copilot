from __future__ import annotations

import os
from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PAGE_PATH = (
    PROJECT_ROOT
    / "app"
    / "pages"
    / "Research_Report.py"
)


VALID_QUESTION = (
    "Show the trend in ischemic heart disease "
    "in Albany County, Wyoming from 2000 to 2019."
)

INVALID_COUNTY_QUESTION = (
    "Tell me about Atlantis County, Wyoming."
)


def assert_no_uncaught_exception(
    app: AppTest,
    case_name: str,
) -> None:
    if len(app.exception) > 0:
        messages = [
            str(item.value)
            for item in app.exception
        ]

        raise AssertionError(
            f"{case_name} produced uncaught "
            f"Streamlit exception(s): {messages}"
        )


def find_button(
    app: AppTest,
    label: str,
):
    matches = [
        button
        for button in app.button
        if button.label == label
    ]

    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one button labelled "
            f"{label!r}, found {len(matches)}."
        )

    return matches[0]


def find_text_area(
    app: AppTest,
    label: str,
):
    matches = [
        item
        for item in app.text_area
        if item.label == label
    ]

    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one text area labelled "
            f"{label!r}, found {len(matches)}."
        )

    return matches[0]


def set_question(
    app: AppTest,
    question: str,
) -> AppTest:
    text_area = find_text_area(
        app,
        "Research question",
    )

    text_area.set_value(
        question
    )

    app.run(
        timeout=240
    )

    return app


def generate_report(
    app: AppTest,
) -> AppTest:
    button = find_button(
        app,
        "Generate validated report",
    )

    button.click()

    app.run(
        timeout=300
    )

    return app


def test_initial_page() -> None:
    print("\n" + "=" * 88)
    print("CASE 1: Initial Research Report page")
    print("=" * 88)

    app = AppTest.from_file(
        str(PAGE_PATH),
        default_timeout=120,
    )

    app.run()

    assert_no_uncaught_exception(
        app,
        "Initial page",
    )

    titles = [
        item.value
        for item in app.title
    ]

    if "AI Research Assistant" not in titles:
        raise AssertionError(
            "Research Report page title was not found."
        )

    find_text_area(
        app,
        "Research question",
    )

    find_button(
        app,
        "Generate validated report",
    )

    find_button(
        app,
        "Clear",
    )

    print("Initial page rendering: PASS")


def test_ai_enabled_success() -> None:
    print("\n" + "=" * 88)
    print("CASE 2: AI-enabled validated report")
    print("=" * 88)

    if not os.getenv(
        "OPENAI_API_KEY"
    ):
        raise AssertionError(
            "OPENAI_API_KEY must be available "
            "for the AI-enabled integration case."
        )

    app = AppTest.from_file(
        str(PAGE_PATH),
        default_timeout=300,
    )

    app.run()

    set_question(
        app,
        VALID_QUESTION,
    )

    generate_report(
        app
    )

    assert_no_uncaught_exception(
        app,
        "AI-enabled report",
    )

    report = app.session_state[
        "research_report_report"
    ]

    evidence = app.session_state[
        "research_report_evidence"
    ]

    interpretation_input = (
        app.session_state[
            "research_report_interpretation_input"
        ]
    )

    interpretation = (
        app.session_state[
            "research_report_interpretation"
        ]
    )

    ai_error = app.session_state[
        "research_report_ai_error"
    ]

    pipeline_error = app.session_state[
        "research_report_error"
    ]

    if pipeline_error is not None:
        raise AssertionError(
            "Successful question produced a pipeline "
            f"error: {pipeline_error}"
        )

    if report is None:
        raise AssertionError(
            "Research report was not stored "
            "in session state."
        )

    if evidence is None:
        raise AssertionError(
            "Evidence bundle was not stored "
            "in session state."
        )

    if interpretation_input is None:
        raise AssertionError(
            "Interpretation input was not stored "
            "in session state."
        )

    if interpretation is None:
        raise AssertionError(
            "Validated AI interpretation was not stored "
            "in session state."
        )

    if ai_error is not None:
        raise AssertionError(
            "AI-enabled successful run produced "
            f"an AI error: {ai_error}"
        )

    if not (
        interpretation
        .direct_answer
        .text
        .strip()
    ):
        raise AssertionError(
            "Validated direct answer was empty."
        )

    if not (
        interpretation
        .direct_answer
        .supporting_claim_ids
    ):
        raise AssertionError(
            "Validated direct answer had no "
            "supporting evidence claims."
        )

    if not interpretation.interpretation:
        raise AssertionError(
            "Validated interpretation contained "
            "no narrative statements."
        )

    if len(evidence.items) == 0:
        raise AssertionError(
            "Evidence bundle contained no evidence items."
        )

    print(
        "Intent:",
        interpretation_input.intent.value,
    )

    print(
        "Evidence claims:",
        len(
            interpretation_input.claims
        ),
    )

    print(
        "Direct answer:",
        interpretation.direct_answer.text,
    )

    print(
        "Supporting claims:",
        interpretation
        .direct_answer
        .supporting_claim_ids,
    )

    print(
        "Narrative statements:",
        len(
            interpretation.interpretation
        ),
    )

    print(
        "AI-enabled application flow: PASS"
    )


def test_invalid_county_rejection() -> None:
    print("\n" + "=" * 88)
    print("CASE 3: Invalid county safe rejection")
    print("=" * 88)

    app = AppTest.from_file(
        str(PAGE_PATH),
        default_timeout=120,
    )

    app.run()

    set_question(
        app,
        INVALID_COUNTY_QUESTION,
    )

    generate_report(
        app
    )

    assert_no_uncaught_exception(
        app,
        "Invalid county",
    )

    error_message = (
        app.session_state[
            "research_report_error"
        ]
    )

    report = app.session_state[
        "research_report_report"
    ]

    interpretation = (
        app.session_state[
            "research_report_interpretation"
        ]
    )

    if not error_message:
        raise AssertionError(
            "Invalid county did not produce "
            "a controlled error."
        )

    if (
        "No current county could be resolved"
        not in error_message
    ):
        raise AssertionError(
            "Invalid county produced an unexpected "
            f"error message: {error_message}"
        )

    if report is not None:
        raise AssertionError(
            "Invalid county unexpectedly produced "
            "a research report."
        )

    if interpretation is not None:
        raise AssertionError(
            "Invalid county unexpectedly produced "
            "an AI interpretation."
        )

    print(
        "Controlled error:",
        error_message,
    )

    print(
        "Invalid county safe rejection: PASS"
    )


def test_missing_api_key_degradation() -> None:
    print("\n" + "=" * 88)
    print("CASE 4: Missing API key graceful degradation")
    print("=" * 88)

    original_key = os.environ.pop(
        "OPENAI_API_KEY",
        None,
    )

    try:
        app = AppTest.from_file(
            str(PAGE_PATH),
            default_timeout=180,
        )

        app.run()

        set_question(
            app,
            VALID_QUESTION,
        )

        generate_report(
            app
        )

        assert_no_uncaught_exception(
            app,
            "Missing API key",
        )

        report = app.session_state[
            "research_report_report"
        ]

        evidence = app.session_state[
            "research_report_evidence"
        ]

        interpretation = (
            app.session_state[
                "research_report_interpretation"
            ]
        )

        ai_error = app.session_state[
            "research_report_ai_error"
        ]

        pipeline_error = app.session_state[
            "research_report_error"
        ]

        if pipeline_error is not None:
            raise AssertionError(
                "Missing API key should not destroy "
                "the deterministic research pipeline. "
                f"Pipeline error: {pipeline_error}"
            )

        if report is None:
            raise AssertionError(
                "Deterministic report was unavailable "
                "when the API key was missing."
            )

        if evidence is None:
            raise AssertionError(
                "Deterministic evidence was unavailable "
                "when the API key was missing."
            )

        if interpretation is not None:
            raise AssertionError(
                "AI interpretation unexpectedly succeeded "
                "without an API key."
            )

        if not ai_error:
            raise AssertionError(
                "Missing API key did not produce "
                "a controlled AI error."
            )

        print(
            "Deterministic report preserved: YES"
        )

        print(
            "Evidence preserved: YES"
        )

        print(
            "AI interpretation withheld: YES"
        )

        print(
            "Controlled AI error:",
            ai_error,
        )

        print(
            "Graceful AI degradation: PASS"
        )

    finally:
        if original_key is not None:
            os.environ[
                "OPENAI_API_KEY"
            ] = original_key


def test_clear_session_state() -> None:
    print("\n" + "=" * 88)
    print("CASE 5: Clear/reset behavior")
    print("=" * 88)

    app = AppTest.from_file(
        str(PAGE_PATH),
        default_timeout=300,
    )

    app.run()

    set_question(
        app,
        VALID_QUESTION,
    )

    generate_report(
        app
    )

    if (
        app.session_state[
            "research_report_report"
        ]
        is None
    ):
        raise AssertionError(
            "Precondition failed: report was "
            "not generated before clear test."
        )

    clear_button = find_button(
        app,
        "Clear",
    )

    clear_button.click()

    app.run(
        timeout=120
    )

    assert_no_uncaught_exception(
        app,
        "Clear/reset",
    )

    keys_expected_none = [
        "research_report_classified",
        "research_report_plan",
        "research_report_evidence",
        "research_report_report",
        "research_report_interpretation_input",
        "research_report_interpretation",
        "research_report_error",
        "research_report_ai_error",
    ]

    for key in keys_expected_none:
        value = app.session_state[
            key
        ]

        if value is not None:
            raise AssertionError(
                f"Clear did not reset {key!r}. "
                f"Value: {value!r}"
            )

    question_value = (
        app.session_state[
            "research_report_question"
        ]
    )

    if question_value != "":
        raise AssertionError(
            "Clear did not reset the research "
            f"question. Value: {question_value!r}"
        )

    print(
        "Session-state reset: PASS"
    )


def main() -> None:
    print("=" * 88)
    print("EpiCounty V1 Tier 3.1 Streamlit Integration Validation")
    print("=" * 88)

    print(
        "Page:",
        PAGE_PATH,
    )

    print(
        "OpenAI key available:",
        bool(
            os.getenv(
                "OPENAI_API_KEY"
            )
        ),
    )

    test_initial_page()
    test_ai_enabled_success()
    test_invalid_county_rejection()
    test_missing_api_key_degradation()
    test_clear_session_state()

    print("\n" + "=" * 88)
    print(
        "TIER 3.1 STREAMLIT INTEGRATION: ALL CASES PASSED"
    )
    print("=" * 88)


if __name__ == "__main__":
    main()