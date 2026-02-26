# Vulture whitelist - false positives for dead code detection
# These are intentionally unused or used dynamically
# Format: _.name (vulture convention for whitelisting)

# Pydantic/dataclass fields (accessed via model instances)
_.needs_more_citations  # perform_citations.py
_.should_add  # perform_citations.py
_.max_figures  # perform_plotting.py
_.plot_list  # perform_writeup.py
_.plot_descriptions  # perform_writeup.py
_.current_pdf_path  # perform_writeup.py
_.vlm_caption_review  # perform_writeup.py
_.vlm_duplicate_analysis  # perform_writeup.py
_.vlm_selection_review  # perform_writeup.py
_.final_value  # metrics_parsing.py
_.best_value  # metrics_parsing.py
_.lower_is_better  # metrics_parsing.py
_.findings  # node_summary.py
_.next_steps  # node_summary.py
_.k_fold_validation  # config.py
_.format_tb_ipython  # config.py
_.plot_model  # config.py
_.citation_model  # config.py
_.writeup_retries  # config.py
_.writeup  # config.py
_.memory_total_mib  # gpu_manager.py
_.partition  # hw_stats.py
_.to_stage  # agent_manager.py
_.config_adjustments  # agent_manager.py
_.populate_by_name  # ai_scientist/vlm/* - Pydantic Config attribute
_.overall_comments  # ai_scientist/vlm/models.py - structured response field
_.containing_sub_figures  # ai_scientist/vlm/models.py - structured response field
_.informative_review  # ai_scientist/vlm/models.py - structured response field
_.caption  # ai_scientist/vlm/review.py - NamedTuple -> _asdict() context
_.main_text_figrefs  # ai_scientist/vlm/review.py - NamedTuple -> _asdict() context

# Callback methods (called by frameworks)
_.on_llm_end  # token_tracker.py - LangChain callback
_.stop  # event_persistence.py, hw_stats.py - thread stop methods
_.close  # artifact_manager.py - context manager
_.get_source  # ai_scientist/vlm/render.py - Jinja2 loader protocol

# Classes/functions used by external code or tests
_.ArtifactPublisher  # artifact_manager.py
_.download_file  # download_manager.py
_.normalize_run_name  # latest_run_finder.py
_.set_sentry_run_context  # sentry_config.py
_.build_auto_review_context  # review_integration.py
_.ReviewResponseRecorder  # review_storage.py
_.from_webhook_client  # review_storage.py
_.insert_review  # review_storage.py
_.FigureReviewRecorder  # review_storage.py
_.insert_reviews  # review_storage.py
_.register_event_callback  # stage_control.py
_.request_stage_skip  # stage_control.py
_.load_json  # serialize.py - multiple overloads

# Telemetry methods (called dynamically)
_.publish_run_started  # event_persistence.py
_.publish_run_finished  # event_persistence.py
_.publish_initialization_progress  # event_persistence.py
_.publish_heartbeat  # event_persistence.py
_.publish_gpu_shortage  # event_persistence.py
