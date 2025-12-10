import csv
import logging
import os
import traceback
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg2
from langchain.chat_models import BaseChatModel
from langchain.chat_models.base import _parse_model
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from ai_scientist.telemetry.event_persistence import _parse_database_url


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


database_url = _require_env("DATABASE_PUBLIC_URL")
RUN_ID = _require_env("RUN_ID")
pg_config = _parse_database_url(database_url)


def save_cost_track(
    model: str,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    ai_message: AIMessage | None = None,
    run_id: str | None = None,
) -> None:
    if run_id is None:
        run_id = RUN_ID
    run_id = None
    if (input_tokens is None or output_tokens is None) and ai_message is None:
        raise ValueError("Either input_tokens and output_tokens or ai_message must be provided")
    if ai_message:
        usage_metadata = ai_message.usage_metadata
        if input_tokens is None and usage_metadata:
            input_tokens = int(usage_metadata.get("input_tokens", 0) or 0)
        if output_tokens is None and usage_metadata:
            output_tokens = int(usage_metadata.get("output_tokens", 0) or 0)

    provider, model_name = extract_model_name_and_provider(model)
    now = datetime.now()
    try:
        save_db_cost_track(
            run_id,
            provider,
            model_name,
            input_tokens,
            output_tokens,
            now,
        )
    except Exception:
        save_file_cost_track(
            run_id,
            provider,
            model_name,
            input_tokens,
            output_tokens,
            now,
        )


def save_db_cost_track(
    run_id: str | None,
    provider: str | None,
    model_name: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    now: datetime | None,
) -> None:
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
                    %s AS output_tokens,
                    %s AS created_at,
                    %s AS updated_at
                FROM research_pipeline_runs rpr 
                INNER JOIN ideas i 
                    ON i.id=rpr.idea_id 
                WHERE rpr.id = %s 
                LIMIT 1
                RETURNING id
                """,
                (
                    provider,
                    model_name,
                    input_tokens,
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
    run_id: str | None,
    provider: str | None,
    model_name: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    now: datetime | None,
) -> None:
    if not os.path.exists("cost_track.csv"):
        with open("cost_track.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["run_id", "provider", "model_name", "input_tokens", "output_tokens", "created_at"]
            )
    with open("cost_track.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                run_id or "",
                provider or "",
                model_name or "",
                input_tokens or "",
                output_tokens or "",
                now or "",
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
                save_cost_track(
                    model=model_name,
                    ai_message=message,
                )
        except Exception:
            traceback.print_exc()
            logging.warning("Token tracking failed; continuing without tracking")


def extract_model_name_and_provider(model: str | BaseChatModel) -> tuple[str, str]:
    if isinstance(model, BaseChatModel):
        if hasattr(model, "model"):
            model_name = model.model
        elif hasattr(model, "model_name"):
            model_name = model.model_name
        else:
            raise ValueError(f"Model {model} has no model or model_name attribute")
    else:
        model_name = model
    return _parse_model(model_name, None)
