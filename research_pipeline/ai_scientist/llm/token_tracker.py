import csv
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import psycopg2
from langchain.chat_models import BaseChatModel
from langchain.chat_models.base import _parse_model
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from ai_scientist.telemetry.event_persistence import _parse_database_url

database_url = os.environ.get("DATABASE_PUBLIC_URL")
RUN_ID = os.environ.get("RUN_ID")
pg_config = _parse_database_url(database_url) if database_url else None


def _should_use_db_tracking(run_id: str | None) -> bool:
    return run_id is not None and pg_config is not None


def _usage_value_to_int(*, value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    try:
        return int(cast(Any, value))
    except Exception:
        return 0


def save_cost_track(
    model: str,
    *,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
) -> None:
    run_id = RUN_ID
    model_name, provider = extract_model_name_and_provider(model)
    now = datetime.now()
    if _should_use_db_tracking(run_id):
        save_db_cost_track(
            run_id=str(run_id),
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            now=now,
        )
    else:
        save_file_cost_track(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            now=now,
        )


def save_db_cost_track(
    *,
    run_id: str,
    provider: str,
    model_name: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    now: datetime,
) -> None:
    if pg_config is None:
        raise ValueError("Database configuration missing; cannot save cost track to DB")
    with psycopg2.connect(**pg_config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO llm_token_usages (
                    conversation_id,
                    run_id,
                    provider,
                    model,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                    created_at,
                    updated_at
                )
                SELECT
                    i.conversation_id, 
                    rpr.run_id,
                    %s AS provider,
                    %s AS model,
                    %s AS input_tokens,
                    %s AS cached_input_tokens,
                    %s AS output_tokens,
                    %s AS created_at,
                    %s AS updated_at
                FROM research_pipeline_runs rpr 
                INNER JOIN ideas i 
                    ON i.id=rpr.idea_id 
                WHERE rpr.run_id = %s 
                LIMIT 1
                RETURNING id
                """,
                (
                    provider,
                    model_name,
                    input_tokens,
                    cached_input_tokens,
                    output_tokens,
                    now,
                    now,
                    run_id,
                ),
            )
            result = cursor.fetchone()
            if not result:
                raise ValueError("Failed to save cost track to database")
            conn.commit()


def save_file_cost_track(
    *,
    provider: str,
    model_name: str,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    now: datetime,
) -> None:
    file_path = Path(os.environ.get("WORKSPACE_DIR") or "") / "cost_track.csv"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        with file_path.open(mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "provider",
                    "model_name",
                    "input_tokens",
                    "cached_input_tokens",
                    "output_tokens",
                    "created_at",
                ]
            )
    with file_path.open(mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                provider,
                model_name,
                input_tokens,
                cached_input_tokens,
                output_tokens,
                now,
            ]
        )


class TrackCostCallbackHandler(BaseCallbackHandler):
    def __init__(self, model: str | None = None):
        self.model = model

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,  # noqa: ARG002
        parent_run_id: UUID | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> Any:  # noqa: ANN401
        try:
            if not response.generations:
                return
            generation = response.generations[0]
            if not generation:
                return
            last_generation = generation[0]
            if not last_generation:
                return
            if not isinstance(last_generation, ChatGeneration):
                return
            message = last_generation.message
            if isinstance(message, AIMessage):
                model_name = self.model or message.response_metadata.get("model_name")
                if not model_name:
                    raise ValueError(
                        "Model name not found in response metadata or provided in constructor"
                    )
                usage_metadata_raw = message.usage_metadata
                usage_metadata: dict[str, object] = (
                    cast(dict[str, object], usage_metadata_raw) if usage_metadata_raw else {}
                )
                input_tokens = _usage_value_to_int(value=usage_metadata.get("input_tokens"))
                cached_input_tokens = _usage_value_to_int(
                    value=usage_metadata.get("cached_input_tokens")
                )
                output_tokens = _usage_value_to_int(value=usage_metadata.get("output_tokens"))
                save_cost_track(
                    model=model_name,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    output_tokens=output_tokens,
                )
        except Exception:
            traceback.print_exc()
            logging.warning("Token tracking failed; continuing without tracking")


def extract_model_name_and_provider(model: str | BaseChatModel) -> tuple[str, str]:
    """Extract the model name and provider from a model."""
    if isinstance(model, BaseChatModel):
        model_attr = getattr(model, "model", None)
        if model_attr is None:
            model_attr = getattr(model, "model_name", None)
        if model_attr is None:
            raise ValueError(f"Model {model} has no model or model_name attribute")
        model_name = str(model_attr)
    else:
        model_name = model
    return _parse_model(model_name, None)
