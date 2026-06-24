from __future__ import annotations

from ...experiment import FAIL, RoundEvalDecision, RoundEvalInput


def mkp_base_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    return RoundEvalDecision(
        passed=False,
        verdict=FAIL,
        message="mkp_base requires a Pdev baseline, which is not supported by the eval/value baseline schema.",
    )


def mkp_bsca_base_margin_2_evaluator(input_data: RoundEvalInput) -> RoundEvalDecision:
    return RoundEvalDecision(
        passed=False,
        verdict=FAIL,
        message=(
            "mkp_bsca_base_margin_2 requires a Pdev baseline, "
            "which is not supported by the eval/value baseline schema."
        ),
    )
