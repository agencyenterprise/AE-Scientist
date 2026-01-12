from ..codex.node_result_contract import (
    NodeResultContractContext,
    codex_node_result_contract_prompt_lines_common,
    validate_common_node_result_contract,
)
from ..codex.seed_aggregation import validate_node_result_contract as validate_seed_agg_contract
from ..stage_identifiers import StageIdentifier
from . import stage1_baseline, stage2_tuning, stage3_plotting, stage4_ablation


def codex_node_result_contract_prompt_lines_for_stage(
    *, stage_identifier: StageIdentifier
) -> list[str]:
    common = codex_node_result_contract_prompt_lines_common()
    # Seed aggregation is orthogonal to the main stages. We still include the common section,
    # but the seed-aggregation task adds additional requirements.
    # (The harness decides whether this is a seed-aggregation run via JSON context in codex_task.md.)
    if stage_identifier is StageIdentifier.STAGE1:
        return common + stage1_baseline.codex_node_result_contract_prompt_lines()
    if stage_identifier is StageIdentifier.STAGE2:
        return common + stage2_tuning.codex_node_result_contract_prompt_lines()
    if stage_identifier is StageIdentifier.STAGE3:
        return common + stage3_plotting.codex_node_result_contract_prompt_lines()
    if stage_identifier is StageIdentifier.STAGE4:
        return common + stage4_ablation.codex_node_result_contract_prompt_lines()
    return common


def validate_node_result_contract_for_stage(
    *, node_result: dict[str, object], ctx: NodeResultContractContext
) -> list[str]:
    errors = validate_common_node_result_contract(node_result=node_result, ctx=ctx)
    if ctx.is_seed_aggregation:
        errors.extend(validate_seed_agg_contract(node_result=node_result, ctx=ctx))
        return errors

    stage_identifier = ctx.stage_identifier
    if stage_identifier is StageIdentifier.STAGE1:
        errors.extend(
            stage1_baseline.validate_node_result_contract(node_result=node_result, ctx=ctx)
        )
        return errors
    if stage_identifier is StageIdentifier.STAGE2:
        errors.extend(stage2_tuning.validate_node_result_contract(node_result=node_result, ctx=ctx))
        return errors
    if stage_identifier is StageIdentifier.STAGE3:
        errors.extend(
            stage3_plotting.validate_node_result_contract(node_result=node_result, ctx=ctx)
        )
        return errors
    if stage_identifier is StageIdentifier.STAGE4:
        errors.extend(
            stage4_ablation.validate_node_result_contract(node_result=node_result, ctx=ctx)
        )
        return errors

    return errors
