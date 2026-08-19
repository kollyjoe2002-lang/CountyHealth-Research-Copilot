from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PAGE_PATH = (
    PROJECT_ROOT
    / "app"
    / "pages"
    / "Research_Report.py"
)


CASES = [
    {
        "name": "empty_question",
        "question": "",
        "expected_fragment": (
            "Enter a research question before "
            "generating a report."
        ),
    },
    {
        "name": "invalid_county",
        "question": (
            "Tell me about Atlantis County, Wyoming."
        ),
        "expected_fragment": (
            "No current county could be resolved"
        ),
    },
    {
        "name": "unsupported_disease",
        "question": (
            "Show the trend in malaria in Albany County, "
            "Wyoming."
        ),
        "expected_fragment": (
            "requested disease or cause could not "
            "be matched"
        ),
    },
    {
        "name": "unsupported_year",
        "question": (
            "Show the trend in ischemic heart disease "
            "in Albany County, Wyoming from 2000 to 2035."
        ),
        "expected_fragment": (
            "fall outside the available CountyHealth "
            "analytical period"
        ),
    },
    {
        "name": "unsupported_inference",
        "question": (
            "Tell me the statistically significant "
            "difference between Black and White "
            "diabetes rates in 2019."
        ),
        "expected_fragment": (
            "does not perform statistical significance"
        ),
    },
]


VALID_TREND_QUESTION = (
    "Show the trend in ischemic heart disease "
    "in Albany County, Wyoming from 2000 to 2019."
)

VALID_RANKING_QUESTION = (
    "Which counties had the highest diabetes "
    "YLL rates in 2019?"
)


def new_app() -> AppTest:
    app = AppTest.from_file(
        str(PAGE_PATH),
        default_timeout=300,
    )

    app.run()

    return app


def find_text_area(
    app: AppTest,
):
    matches = [
        item
        for item in app.text_area
        if item.label == "Research question"
    ]

    if len(matches) != 1:
        raise AssertionError(
            "Expected exactly one Research question "
            f"text area, found {len(matches)}."
        )

    return matches[0]


def find_button(
    app: AppTest,
    label: str,
):
    matches = [
        item
        for item in app.button
        if item.label == label
    ]

    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one button {label!r}, "
            f"found {len(matches)}."
        )

    return matches[0]


def set_question(
    app: AppTest,
    question: str,
) -> None:
    text_area = find_text_area(
        app
    )

    text_area.set_value(
        question
    )

    app.run(
        timeout=120
    )


def click_generate(
    app: AppTest,
) -> None:
    button = find_button(
        app,
        "Generate validated report",
    )

    button.click()

    app.run(
        timeout=300
    )


def all_visible_messages(
    app: AppTest,
) -> list[str]:
    values: list[str] = []

    element_groups = [
        app.error,
        app.warning,
        app.info,
        app.success,
        app.markdown,
        app.caption,
        app.code,
    ]

    for group in element_groups:
        for item in group:
            value = getattr(
                item,
                "value",
                None,
            )

            if value is not None:
                values.append(
                    str(value)
                )

    return values


def assert_visible_fragment(
    app: AppTest,
    fragment: str,
    case_name: str,
) -> None:
    messages = all_visible_messages(
        app
    )

    if not any(
        fragment.casefold()
        in message.casefold()
        for message in messages
    ):
        raise AssertionError(
            f"{case_name}: expected visible fragment "
            f"{fragment!r} was not found.\n"
            f"Visible messages: {messages}"
        )


def assert_no_uncaught_exception(
    app: AppTest,
    case_name: str,
) -> None:
    if len(app.exception) > 0:
        exceptions = [
            str(item.value)
            for item in app.exception
        ]

        raise AssertionError(
            f"{case_name}: uncaught Streamlit "
            f"exception(s): {exceptions}"
        )


def test_error_cases() -> None:
    print("\n" + "=" * 88)
    print("CASE GROUP 1: Controlled UI error states")
    print("=" * 88)

    for case in CASES:
        print(
            f"\nTesting: {case['name']}"
        )

        app = new_app()

        set_question(
            app,
            case["question"],
        )

        click_generate(
            app
        )

        assert_no_uncaught_exception(
            app,
            case["name"],
        )

        assert_visible_fragment(
            app,
            case["expected_fragment"],
            case["name"],
        )

        report = app.session_state[
            "research_report_report"
        ]

        interpretation = app.session_state[
            "research_report_interpretation"
        ]

        if case["name"] != "empty_question":
            if report is not None:
                raise AssertionError(
                    f"{case['name']}: invalid input "
                    "unexpectedly produced a report."
                )

            if interpretation is not None:
                raise AssertionError(
                    f"{case['name']}: invalid input "
                    "unexpectedly produced an "
                    "AI interpretation."
                )

        print(
            f"{case['name']}: PASS"
        )


def test_intent_switching() -> None:
    print("\n" + "=" * 88)
    print("CASE GROUP 2: Intent switching / stale-state prevention")
    print("=" * 88)

    app = new_app()

    set_question(
        app,
        VALID_TREND_QUESTION,
    )

    click_generate(
        app
    )

    assert_no_uncaught_exception(
        app,
        "Trend generation",
    )

    trend_input = app.session_state[
        "research_report_interpretation_input"
    ]

    trend_report = app.session_state[
        "research_report_report"
    ]

    if trend_input is None:
        raise AssertionError(
            "Trend generation did not create "
            "interpretation input."
        )

    if (
        trend_input.intent.value
        != "trend_comparison"
    ):
        raise AssertionError(
            "Trend generation produced wrong intent: "
            f"{trend_input.intent.value}"
        )

    if trend_report is None:
        raise AssertionError(
            "Trend generation produced no report."
        )

    first_report_question = (
        trend_report.question
    )

    set_question(
        app,
        VALID_RANKING_QUESTION,
    )

    click_generate(
        app
    )

    assert_no_uncaught_exception(
        app,
        "Ranking generation",
    )

    ranking_input = app.session_state[
        "research_report_interpretation_input"
    ]

    ranking_report = app.session_state[
        "research_report_report"
    ]

    if ranking_input is None:
        raise AssertionError(
            "Ranking generation did not create "
            "interpretation input."
        )

    if (
        ranking_input.intent.value
        != "county_ranking"
    ):
        raise AssertionError(
            "Ranking generation produced wrong intent: "
            f"{ranking_input.intent.value}"
        )

    if ranking_report is None:
        raise AssertionError(
            "Ranking generation produced no report."
        )

    if (
        ranking_report.question
        != VALID_RANKING_QUESTION
    ):
        raise AssertionError(
            "Ranking report retained stale question "
            "content."
        )

    if (
        ranking_report.question
        == first_report_question
    ):
        raise AssertionError(
            "Report question did not change after "
            "intent switch."
        )

    evidence = app.session_state[
        "research_report_evidence"
    ]

    if evidence is None:
        raise AssertionError(
            "Ranking generation produced no evidence."
        )

    if (
        evidence.intent.value
        != "county_ranking"
    ):
        raise AssertionError(
            "Evidence bundle retained stale intent: "
            f"{evidence.intent.value}"
        )

    print(
        "Trend -> ranking state transition: PASS"
    )


def test_clear_then_regenerate() -> None:
    print("\n" + "=" * 88)
    print("CASE GROUP 3: Clear then regenerate")
    print("=" * 88)

    app = new_app()

    set_question(
        app,
        VALID_TREND_QUESTION,
    )

    click_generate(
        app
    )

    if (
        app.session_state[
            "research_report_report"
        ]
        is None
    ):
        raise AssertionError(
            "Precondition failed: no report before clear."
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
        "Clear",
    )

    if (
        app.session_state[
            "research_report_report"
        ]
        is not None
    ):
        raise AssertionError(
            "Clear did not remove prior report."
        )

    set_question(
        app,
        VALID_RANKING_QUESTION,
    )

    click_generate(
        app
    )

    assert_no_uncaught_exception(
        app,
        "Post-clear regeneration",
    )

    report = app.session_state[
        "research_report_report"
    ]

    interpretation_input = app.session_state[
        "research_report_interpretation_input"
    ]

    if report is None:
        raise AssertionError(
            "Post-clear regeneration produced "
            "no report."
        )

    if interpretation_input is None:
        raise AssertionError(
            "Post-clear regeneration produced "
            "no interpretation input."
        )

    if (
        interpretation_input.intent.value
        != "county_ranking"
    ):
        raise AssertionError(
            "Post-clear regeneration retained "
            "stale intent."
        )

    if (
        report.question
        != VALID_RANKING_QUESTION
    ):
        raise AssertionError(
            "Post-clear report retained stale "
            "question."
        )

    print(
        "Clear -> regenerate behavior: PASS"
    )


def test_supporting_claims_visible() -> None:
    print("\n" + "=" * 88)
    print("CASE GROUP 4: Grounding visibility")
    print("=" * 88)

    app = new_app()

    set_question(
        app,
        VALID_TREND_QUESTION,
    )

    click_generate(
        app
    )

    assert_no_uncaught_exception(
        app,
        "Grounding visibility",
    )

    interpretation = app.session_state[
        "research_report_interpretation"
    ]

    if interpretation is None:
        raise AssertionError(
            "No AI interpretation available "
            "for grounding visibility test."
        )

    direct_claim_ids = (
        interpretation
        .direct_answer
        .supporting_claim_ids
    )

    if not direct_claim_ids:
        raise AssertionError(
            "Direct answer had no supporting claims."
        )

    visible_messages = (
        "\n".join(
            all_visible_messages(
                app
            )
        )
    )

    visible_claim_count = 0

    for claim_id in direct_claim_ids:
        if claim_id in visible_messages:
            visible_claim_count += 1

    if visible_claim_count == 0:
        raise AssertionError(
            "No direct-answer supporting claim IDs "
            "were visible in the Streamlit UI."
        )

    print(
        "Visible supporting claim IDs:",
        visible_claim_count,
    )

    print(
        "Grounding visibility: PASS"
    )


def main() -> None:
    print("=" * 88)
    print(
        "EpiCounty V1 Tier 3.3 "
        "UI and Error-State Validation"
    )
    print("=" * 88)

    test_error_cases()
    test_intent_switching()
    test_clear_then_regenerate()
    test_supporting_claims_visible()

    print("\n" + "=" * 88)
    print(
        "TIER 3.3 UI/ERROR-STATE VALIDATION: "
        "ALL CASES PASSED"
    )
    print("=" * 88)


if __name__ == "__main__":
    main()