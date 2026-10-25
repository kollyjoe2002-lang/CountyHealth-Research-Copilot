"""Live-model V1.3 forms. No prepared responses or fixture execution permitted."""
import os
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from ai.openai_semantic_parser import OpenAISemanticParser
from ai.models import ResearchQuestion
from ai.request_policy import apply_request_policy
from ai.conversation_state import run_research_turn
from ai.conversation_contracts import FailureReason


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--warehouse',type=Path,help='Explicit actual development warehouse only')
    args=args.parse_args()
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('BLOCKED: actual live semantic API credentials unavailable; no prepared parser responses used')
    import tempfile
    import app.data_access as data
    import ai.research_assistant as assistant
    assistant.persist_research_telemetry=lambda *a,**k: None
    no_data=tempfile.TemporaryDirectory()
    try:
        data.DB_FILE=args.warehouse.resolve() if args.warehouse else Path(no_data.name)/'explicit_warehouse_required.duckdb'
        return run_checks(args)
    finally:
        no_data.cleanup()


def run_checks(args):
    parser=OpenAISemanticParser()
    positives=(
        ('Compare ischemic heart disease among women ages 40 to 44 and 60 to 64 in 2019.','sex_age'),
        ('Compare women and men aged 60 to 64 for stroke in 2019.','sex_age'),
        ('Compare stroke burden among women across rural and metropolitan counties in 2019.','sex_rurality'),
    )
    for text,key in positives:
        result=apply_request_policy(parser.parse(ResearchQuestion(text)))
        assert result.normalized_multidimensional is not None, result.reason
        assert result.normalized_multidimensional.capability_key==key
        assert result.decision.value=='planned'
    for text in ('Compare Black women and White men for stroke in 2019.',
                 'Show IHME stroke in 2024.', 'Forecast stroke to 2035.'):
        result=apply_request_policy(parser.parse(ResearchQuestion(text)))
        assert result.decision.value=='reject', result.reason
    first=run_research_turn('Compare diabetes in Milwaukee County.',semantic_parser=parser)
    assert first.response and first.response.reason is FailureReason.SOURCE_REQUIRED
    second=run_research_turn('Both',state=first.state,semantic_parser=parser)
    assert second.state is not None
    first=run_research_turn('Compare women and men for IHME stroke.',semantic_parser=parser)
    assert first.response and first.response.reason is FailureReason.YEAR_REQUIRED
    # A real execution follow-up/disease absence requires actual catalogs as well.
    guidance=run_research_turn('What can you do?',semantic_parser=parser)
    assert guidance.outcome.status=='capability_summary'
    if args.warehouse is None or not args.warehouse.is_file():
        raise SystemExit('BLOCKED: live parse samples passed, but actual warehouse follow-up/unavailable-disease tests remain unverified')
    import app.data_access as data
    data.DB_FILE=args.warehouse.resolve()
    second=run_research_turn('2019',state=first.state,semantic_parser=parser)
    assert second.outcome and second.outcome.status=='answer' and second.outcome.interpretation_result is not None
    missing=run_research_turn('Show IHME CountyConditionNotInCatalogXYZ in Milwaukee County in 2019.',semantic_parser=parser)
    assert missing.outcome is None or missing.outcome.evidence_bundle is None
    guidance=run_research_turn('What can you do?',semantic_parser=parser)
    assert guidance.outcome.status=='capability_summary'
    print('PASS: real-model V1.3 parses, policy, conversation, catalogue absence and capability guidance')


if __name__=='__main__': main()
